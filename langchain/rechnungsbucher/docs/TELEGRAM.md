# Telegram Integration for the Rechnungsbücher Agent

This guide wires the `langchain/rechnungsbucher` LangChain agent to a Telegram bot so you can trigger invoice booking from your phone or desktop without opening a terminal.

---

## Architecture

```
You (Telegram) ──▶ Bot API ──▶ telegram_bot.py
                                      │
                                      ▼
                              LangGraph ReAct agent
                              (agent.py / main.py logic)
                                      │
                              ┌───────┴────────┐
                              ▼                ▼
                         Collmex API     Nextcloud WebDAV
```

`telegram_bot.py` is a thin wrapper around the existing agent. It maintains per-chat conversation state so the agent's multi-turn confirmation flow (scan → confirm table → upload) works naturally over Telegram messages.

---

## Step 1 — Create a Telegram Bot

1. Open Telegram and start a chat with **@BotFather**.
2. Send `/newbot`.
3. Choose a name, e.g. `Rechnungsbucher`.
4. Choose a username, e.g. `rechnungsbucher_bot` (must end in `bot`).
5. BotFather replies with a **bot token** — looks like `123456789:AABBcc...`.  
   Copy it; you will need it in Step 3.

---

## Step 2 — Find Your Telegram User ID

You need your numeric user ID to restrict the bot to yourself (or a team).

1. Start a chat with **@userinfobot**.
2. Send `/start` — it replies with `Id: 123456789`.
3. Copy the number. This is your `TELEGRAM_ALLOWED_USERS` value.

For a team add multiple IDs comma-separated: `111,222,333`.

---

## Step 3 — Configure Environment Variables

Add the following to `langchain/rechnungsbucher/.env`:

```dotenv
# ─── Telegram Bot ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=123456789:AABBcc...

# Comma-separated Telegram user IDs who may use the bot.
# Leave empty to allow everyone (NOT recommended for production).
TELEGRAM_ALLOWED_USERS=123456789
```

All existing variables (`COLLMEX_*`, `NEXTCLOUD_*`, `LLM_*`) remain unchanged.

---

## Step 4 — Install the Additional Dependency

```bash
cd langchain/rechnungsbucher
source .venv/bin/activate
pip install "python-telegram-bot>=21.0,<22.0"
```

Or add it to `requirements.txt` permanently:

```
python-telegram-bot>=21.0,<22.0
```

---

## Step 5 — Create `telegram_bot.py`

Create the file `langchain/rechnungsbucher/telegram_bot.py` with the following content:

```python
#!/usr/bin/env python3
"""
Telegram interface for the Rechnungsbücher LangChain agent.

Usage:
    python telegram_bot.py

Commands available in the chat:
    /start  — greet and reset conversation
    /reset  — clear conversation history for this chat
    /help   — show available commands
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import load_agent_config, load_collmex_config, load_llm_config, load_nextcloud_config
from tools.collmex_tools import init_collmex_tools
from tools.nextcloud_tools import init_nextcloud_tools
from agent import create_agent

# ── Bootstrap ────────────────────────────────────────────────────────────────

load_dotenv()
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

_raw_allowed = os.environ.get("TELEGRAM_ALLOWED_USERS", "").strip()
ALLOWED_USER_IDS: set[int] = (
    {int(uid.strip()) for uid in _raw_allowed.split(",") if uid.strip()}
    if _raw_allowed
    else set()
)

# ── Agent (initialised once at startup) ───────────────────────────────────────

_agent: Any = None


def _init_agent() -> None:
    global _agent
    logger.info("Initialising Rechnungsbücher agent …")
    collmex_cfg = load_collmex_config()
    nextcloud_cfg = load_nextcloud_config()
    llm_cfg = load_llm_config()
    agent_cfg = load_agent_config()

    init_collmex_tools(collmex_cfg)
    init_nextcloud_tools(nextcloud_cfg)

    _agent = create_agent(llm_cfg, agent_cfg)
    logger.info("Agent ready.")


# ── Per-chat state ────────────────────────────────────────────────────────────

# Maps chat_id → LangGraph state dict {"messages": [...]}
_chat_states: dict[int, dict] = {}


def _get_state(chat_id: int) -> dict:
    if chat_id not in _chat_states:
        _chat_states[chat_id] = {"messages": []}
    return _chat_states[chat_id]


def _reset_state(chat_id: int) -> None:
    _chat_states[chat_id] = {"messages": []}


# ── Authorization ─────────────────────────────────────────────────────────────


def _is_authorized(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        logger.warning(
            "TELEGRAM_ALLOWED_USERS is not set — the bot is open to everyone. "
            "Set it to restrict access."
        )
        return True
    return user_id in ALLOWED_USER_IDS


# ── Helpers ───────────────────────────────────────────────────────────────────

_MAX_MSG_LEN = 4000  # Telegram hard limit is 4096; leave headroom


async def _send_long(update: Update, text: str) -> None:
    """Send text, splitting into chunks if it exceeds the Telegram limit."""
    while text:
        chunk, text = text[:_MAX_MSG_LEN], text[_MAX_MSG_LEN:]
        await update.message.reply_text(chunk)


async def _keep_typing(bot, chat_id: int, stop_event: asyncio.Event) -> None:
    """Repeatedly send 'typing' action every 4 seconds until stop_event is set."""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(asyncio.shield(stop_event.wait()), timeout=4)
        except asyncio.TimeoutError:
            pass


# ── Handlers ──────────────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("Nicht autorisiert.")
        return
    _reset_state(update.effective_chat.id)
    await update.message.reply_text(
        "Rechnungsbücher Agent bereit.\n\n"
        "Sende einen Befehl, z.\u2009B.:\n"
        "  Rechnungen buchen\n\n"
        "/reset — Konversation zurücksetzen\n"
        "/help  — Hilfe anzeigen"
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("Nicht autorisiert.")
        return
    _reset_state(update.effective_chat.id)
    await update.message.reply_text("Konversation zurückgesetzt.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("Nicht autorisiert.")
        return
    await update.message.reply_text(
        "Verfügbare Befehle:\n"
        "/start — Agent starten / Konversation zurücksetzen\n"
        "/reset — Konversation zurücksetzen\n"
        "/help  — Diese Hilfe anzeigen\n\n"
        "Beispiel-Nachrichten:\n"
        "  Rechnungen buchen\n"
        "  Nur Rechnungen aus dem Ordner Eingang/Test buchen\n"
        "  ja  (Buchung bestätigen, nachdem der Agent eine Tabelle gezeigt hat)"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not _is_authorized(user_id):
        await update.message.reply_text("Nicht autorisiert.")
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text or ""
    if not user_text.strip():
        return

    state = _get_state(chat_id)
    state["messages"].append({"role": "user", "content": user_text})

    # Show typing indicator for the duration of the agent run
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(context.bot, chat_id, stop_typing)
    )

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _agent.invoke, state)
        _chat_states[chat_id] = result

        reply = ""
        for msg in reversed(result.get("messages", [])):
            if msg.type == "ai" and msg.content:
                reply = msg.content
                break

        if reply:
            await _send_long(update, reply)
        else:
            await update.message.reply_text("(Keine Antwort vom Agenten)")

    except Exception as exc:
        logger.exception("Agent error for chat %s", chat_id)
        await update.message.reply_text(f"Fehler: {exc}")
    finally:
        stop_typing.set()
        typing_task.cancel()


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    _init_agent()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot polling for updates. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
```

---

## Step 6 — Run the Bot

```bash
cd langchain/rechnungsbucher
source .venv/bin/activate
python telegram_bot.py
```

Open Telegram, find your bot by its username, and send `/start`.  
Then type **Rechnungen buchen** — the agent will scan Nextcloud, extract invoice data, and reply with a confirmation table.  
Reply **ja** (or any confirmation text) to trigger the upload and renaming.

---

## Step 7 — Keep the Bot Running (systemd)

Create `/etc/systemd/system/rechnungsbucher-bot.service`:

```ini
[Unit]
Description=Rechnungsbücher Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<your-unix-user>
WorkingDirectory=/root/docker/ai.ixc-tools.de/langchain/rechnungsbucher
Environment=PATH=/root/docker/ai.ixc-tools.de/langchain/rechnungsbucher/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/root/docker/ai.ixc-tools.de/langchain/rechnungsbucher/.venv/bin/python telegram_bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rechnungsbucher-bot
sudo journalctl -u rechnungsbucher-bot -f
```

---

## Conversation Flow Example

```
You:    Rechnungen buchen
Agent:  Ich scanne den Eingangsordner …
        [processes PDFs, calls Collmex/Nextcloud tools]
        Hier ist die Bestätigungstabelle:

        | # | Lieferant       | Rechnungs-Nr | Datum      | Brutto  | … |
        |---|-----------------|-------------|------------|---------|---|
        | 1 | OpenAI (9001)   | INV-2026-03 | 2026-03-01 | 119,00€ | … |
        | 2 | Hetzner (9002)  | R-987654    | 2026-03-05 |  41,65€ | … |

        Soll ich diese Rechnungen jetzt buchen?

You:    ja

Agent:  Rechnungen werden gebucht …
        [uploads, fetches booking numbers, renames, moves to archive]
        Fertig. 2 Rechnungen erfolgreich gebucht:
        • 00123_2026-03-01_OpenAI_Rechnung_INV-2026-03.pdf → Buchhaltung/2026/
        • 00124_2026-03-05_Hetzner_Rechnung_R-987654.pdf   → Buchhaltung/2026/
```

---

## Notes

- **Authorization is enforced** via `TELEGRAM_ALLOWED_USERS`. If the variable is empty the bot logs a warning and accepts messages from anyone — do not use this in production.
- **Conversation state** is kept in memory per chat. Restarting the bot clears all history; use `/reset` explicitly if you want a fresh run without restarting.
- **Long messages** (confirmation tables with many invoices) are automatically split into multiple Telegram messages to stay within the 4 096-character limit.
- **Typing indicator** is kept alive during long agent runs (which can take several minutes for large invoice batches) so the chat does not appear stalled.
- The agent's `max_iterations` and LLM model are controlled by the same `.env` variables as the CLI (`AGENT_MAX_ITERATIONS`, `LLM_MODEL`, etc.).
