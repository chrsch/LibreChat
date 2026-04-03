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
