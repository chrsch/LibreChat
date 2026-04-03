# Security Assessment — Rechnungsbucher Telegram Bot

Last reviewed: 2026-04-03

## Overview

The Rechnungsbucher bot connects a Telegram interface to a LangChain agent that has
read/write access to a Nextcloud account and a Collmex financial API. This document
catalogues known security risks and proposed mitigations.

---

## 1. LLM Prompt Injection → Arbitrary Nextcloud Access

**Severity: CRITICAL**

The Telegram user sends free-text messages that are forwarded to the LangChain agent.
The agent has tools for `nextcloud_list_files`, `nextcloud_download_file`,
`nextcloud_delete_file`, `nextcloud_move_file`, `nextcloud_create_folder`, and
`nextcloud_rename_file` — all of which accept **arbitrary paths** within the
Nextcloud user's home directory.

The system prompt suggests a default working folder
(`Dokumente/Freiberuflich/Finanzen/Buchhaltung/Eingang`), but this is **not
enforced in code**. A crafted prompt could instruct the agent to read, move, or
delete files anywhere in the account.

### Proposed measures

- **Code-level path allowlist** — validate in every Nextcloud tool that the
  resolved path starts with an allowed prefix (e.g.
  `Dokumente/Freiberuflich/Finanzen/Buchhaltung/`). Reject all other paths
  before making WebDAV calls.
- **Remove or gate destructive tools** — consider removing `nextcloud_delete_file`
  and `nextcloud_move_file` from the agent's toolset, or require explicit user
  confirmation before execution.
- **Dedicated Nextcloud service account** — use a restricted account (e.g.
  `rechnungsbucher_agent`) that only has access to the invoice folder via
  Nextcloud group folders / sharing. *(Already partially addressed — the `.env`
  now references `rechnungsbucher_agent`.)*

---

## 2. Broad Nextcloud Credential Scope

**Severity: HIGH**

The WebDAV credentials give the bot access to the **entire home directory** of the
configured Nextcloud user. Even with a dedicated account, any files shared _into_
that account are also reachable.

### Proposed measures

- Ensure the Nextcloud service account has **no additional shares** beyond the
  invoice working directory.
- Periodically audit which folders are shared with the service account.

---

## 3. Unrestricted Agent Tools (Delete, Move, Rename)

**Severity: HIGH**

The agent can invoke destructive operations (delete, move) without confirmation.
A single hallucinated or injected tool call could permanently destroy data.

### Proposed measures

- Add a **confirmation step** for destructive actions — e.g. the bot asks the
  Telegram user "Delete X — are you sure? (yes/no)" before executing.
- Log every tool invocation (path + action) to an immutable audit log.
- Enable Nextcloud **Trash / Versions** for the service account so deletions
  and overwrites are recoverable.

---

## 4. Telegram Open-by-Default When `TELEGRAM_ALLOWED_USERS` Is Unset

**Severity: HIGH**

If `TELEGRAM_ALLOWED_USERS` is empty or missing, `_is_authorized()` returns
`True` for every Telegram user, making the bot publicly accessible.

### Proposed measures

- **Fail closed** — if `TELEGRAM_ALLOWED_USERS` is empty, deny all requests
  instead of allowing all.
- Add a startup check that refuses to launch when the variable is unset.

---

## 5. Collmex API Credential Exposure

**Severity: MEDIUM**

The bot holds Collmex credentials that allow creating and modifying invoices
and retrieving financial data. Compromise of the bot process would grant access
to the bookkeeping system.

### Proposed measures

- Use a **Collmex sub-user** with the minimum required permissions (e.g.
  create supplier invoices only, no payment or export rights).
- Rotate credentials regularly.

---

## 6. Credentials in Docker Image Layers

**Severity: MEDIUM**

The Dockerfile `COPY . .` copies the entire build context, potentially
including `.env`. Even if `.env` is later deleted in a subsequent layer,
it remains in the image history.

### Proposed measures

- Add `.env` to `.dockerignore`.
- Pass secrets at runtime via `docker compose` environment variables or
  Docker secrets — never bake them into the image.

---

## 7. Single Telegram User as Sole Access Control

**Severity: MEDIUM**

Access control relies entirely on a single Telegram user ID. If that
account is compromised, the attacker gets full bot access.

### Proposed measures

- Consider adding a **secondary authentication factor** (e.g. a PIN or
  passphrase the bot asks for at session start).
- Support multiple allowed users so access is auditable per person.

---

## Status Tracker

| # | Finding                              | Severity | Status       |
|---|--------------------------------------|----------|--------------|
| 1 | Prompt injection → arbitrary paths   | CRITICAL | Open         |
| 2 | Broad Nextcloud credential scope     | HIGH     | In progress  |
| 3 | Unrestricted destructive tools       | HIGH     | Open         |
| 4 | Open-by-default Telegram auth        | HIGH     | Open         |
| 5 | Collmex credential exposure          | MEDIUM   | Open         |
| 6 | Credentials in Docker image layers   | MEDIUM   | Open         |
| 7 | Single-user access control           | MEDIUM   | Open         |
