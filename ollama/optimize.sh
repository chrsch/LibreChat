#!/usr/bin/env bash
set -euo pipefail

# -------- settings (override via env or args if you like) ----------
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-11434}"
MODEL="${MODEL:-llama3.2-3b-local}"
CTX="${CTX:-512}"

# start gpu_layers here (safe for 4GB cards), will auto-increase
L_START="${L_START:-24}"

# batch tuning range
B_START="${B_START:-128}"
B_STEP="${B_STEP:-32}"
B_MAX="${B_MAX:-224}"   # push higher if VRAM allows

# inference length for timing
NPRED="${NPRED:-256}"

# prompt (avoid jq concat quirks; build in bash)
PROMPT="Benchmark prompt $(printf 'A%.0s' $(seq 1 200))"
# -------------------------------------------------------------------

die() { echo "ERROR: $*" >&2; exit 1; }

json() { jq -n "$@"; }

# quick ping
curl -sS "http://$HOST:$PORT/api/tags" >/dev/null || die "Ollama not reachable at $HOST:$PORT"

# discover model block_count (fallback 32)
MAX_LAYERS="$(
  curl -sS "http://$HOST:$PORT/api/show" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"$MODEL\"}" \
  | jq -r '(..|.["block_count","phi3.block_count","llama.block_count"]?|select(.)) // 32'
)"

echo "Model: $MODEL  max_layers: $MAX_LAYERS  ctx: $CTX  host: $HOST:$PORT"

# warmup
curl -sS -X POST "http://$HOST:$PORT/api/generate" \
  -H 'Content-Type: application/json' \
  -d "$(json --arg m "$MODEL" --arg p "$PROMPT" '
      {model:$m, prompt:$p,
       options:{temperature:0, seed:1, num_predict:64},
       stream:false }')" >/dev/null || true

# run one attempt; prints a TSV line or returns non-zero on failure
attempt() {
  local L="$1" B="$2"

  # build request body safely via jq
  local req
  req="$(json --arg m "$MODEL" --arg p "$PROMPT" \
              --argjson L "$L" --argjson C "$CTX" \
              --argjson B "$B" --argjson NP "$NPRED" '
    { model:$m, prompt:$p,
      options:{ temperature:0, seed:1, num_predict:$NP,
                gpu_layers:$L, num_ctx:$C, num_batch:$B },
      stream:false }')"

  # run request
  local out
  set +e
  out="$(curl -sS -f -m 180 -X POST "http://$HOST:$PORT/api/generate" \
          -H 'Content-Type: application/json' -d "$req")"
  local rc=$?
  set -e

  if [[ $rc -ne 0 ]]; then
    return 2  # likely OOM / HTTP error
  fi

  # compute tokens/sec robustly
  # prefer eval_duration; fall back to total_duration
  # print: L, B, eval_count, eval_ns, toks_per_s
  local line
  line="$(jq -r '
      def dur: (.eval_duration // .total_duration);
      if (.eval_count != null and (dur|type)=="number" and dur > 0)
      then
        [.eval_count, (dur|tonumber), (.eval_count / (dur/1e9))]
        | @tsv
      else
        empty
      end
    ' <<<"$out")"

  [[ -n "$line" ]] || return 3

  echo -e "$L\t$B\t$line"
}

best_tps=0
best_L=0
best_B=0

# main tuning: grow L, for each L grow B; stop on first OOM at base B
for ((L = L_START; L <= MAX_LAYERS; L++)); do
  echo "=== gpu_layers=$L ==="
  ok_at_L=false

  for ((B = B_START; B <= B_MAX; B += B_STEP)); do
    if line=$(attempt "$L" "$B"); then
      ok_at_L=true
      # parse TSV line
      IFS=$'\t' read -r _L _B eval_count eval_ns toks_ps <<<"$line"
      printf 'L=%s B=%s  eval_count=%s  eval_ns=%s  toks/s=%.2f\n' "$_L" "$_B" "$eval_count" "$eval_ns" "$toks_ps"

      # track best
      # shellcheck disable=SC2072
      if (( $(awk -v a="$toks_ps" -v b="$best_tps" 'BEGIN{print (a>b)}') )); then
        best_tps="$toks_ps"; best_L="$L"; best_B="$B"
      fi
    else
      echo "OOM or failure at L=$L B=$B -> backing off this B"
      # if first (baseline) B fails at this L, we went too far on L
      if [[ $B -eq $B_START && $ok_at_L == false ]]; then
        echo "Hit limit at gpu_layers=$L. Stopping L growth."
        L=$((L-1))  # step back one for clarity
        break 2     # exit both loops
      fi
      break        # try next L
    fi
    sleep 0.3
  done
done

echo
echo ">>> Recommended settings (best measured): gpu_layers=$best_L  num_batch=$best_B  num_ctx=$CTX"
echo "    Observed throughput: ${best_tps} toks/s"
