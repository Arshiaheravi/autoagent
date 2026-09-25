#!/usr/bin/env python3
"""Agent Director — Claude on Telegram.

Long-running process that:
1. Listens for the operator's Telegram messages
2. Responds with full agency context (projects, sessions, agents, deploys)
3. Runs commands (status, deploy checks, backlog management)
4. Forwards agent questions and routes replies
5. Proactive: daily summaries, deploy alerts, quality warnings

Usage:
    python3 engine/director.py

Runs until Ctrl-C or machine shutdown. Designed for:
    - Background terminal: `nohup python3 engine/director.py &`
    - launchd plist for auto-start on Mac boot
    - tmux/screen session
"""
import logging
import os
import time
from datetime import datetime

import requests

from director_helpers import (
    get_agency_context,
    handle_command,
    ask_claude,
    _fallback_answer,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("director")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send(text: str, parse_mode: str = "HTML") -> bool:
    try:
        resp = requests.post(f"{API_BASE}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": text[:4096],
            "parse_mode": parse_mode,
        }, timeout=15)
        return resp.json().get("ok", False)
    except Exception as e:
        logger.warning("Send failed: %s", e)
        return False


def _download_photo(file_id: str) -> tuple[bytes, str]:
    """Download a photo from Telegram. Returns (image_bytes, mime_type)."""
    # Step 1: resolve file_id to a file_path
    resp = requests.get(f"{API_BASE}/getFile", params={"file_id": file_id}, timeout=15)
    file_path = resp.json()["result"]["file_path"]
    # Step 2: download the file
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    data = requests.get(file_url, timeout=30).content
    mime_type = "image/jpeg" if file_path.lower().endswith(".jpg") else "image/png"
    return data, mime_type


def handle_photo(photo_sizes: list) -> str:
    """Process a photo message — distill as article screenshot."""
    # Telegram sends multiple sizes; last = highest resolution
    file_id = photo_sizes[-1]["file_id"]
    send("📸 Got the screenshot. Distilling...")
    try:
        image_bytes, mime_type = _download_photo(file_id)
        from article_distiller import distill_image
        result = distill_image(image_bytes, mime_type=mime_type, source_hint="telegram-screenshot")
        return _format_distill_result(result)
    except Exception as e:
        logger.error("Photo distillation failed: %s", e)
        return f"Failed to process screenshot: {e}"


def handle_article_text(text: str) -> str:
    """Process a long text message as a pasted article."""
    send("📄 Got it. Distilling...")
    try:
        from article_distiller import distill_text
        result = distill_text(text, source_hint="telegram-paste")
        return _format_distill_result(result)
    except Exception as e:
        logger.error("Article distillation failed: %s", e)
        return f"Failed to distill article: {e}"


def _format_distill_result(result: dict) -> str:
    """Format a distillation result as a Telegram-ready HTML message."""
    score = result.get("score", 0)
    filed = result.get("filed", False)
    score_bar = "⬛" * (5 - score) + "🟩" * score if score else "⬛⬛⬛⬛⬛"

    if filed:
        tags = " ".join(f"#{t}" for t in result.get("tags", []))
        lines = [
            f"✅ <b>Filed to knowledge base</b>",
            f"Score: {score_bar} {score}/5",
            f"",
            f"<b>Claim:</b> {result['summary'].split(chr(10))[0]}",
        ]
        if result.get("rule"):
            lines.append(f"<b>Rule:</b> {result['rule']}")
        if result.get("why_practical"):
            lines.append(f"<b>Why:</b> {result['why_practical']}")
        if tags:
            lines.append(f"<i>{tags}</i>")
    else:
        reason = result.get("skip_reason", "Low practical value")
        claim = result.get("summary", "").split("\n")[0]
        lines = [
            f"📁 <b>Archived (not filed)</b>",
            f"Score: {score_bar} {score}/5",
            f"<i>Reason: {reason}</i>",
        ]
        if claim:
            lines.append(f"Claim: {claim}")

    return "\n".join(lines)


def handle_message(text: str) -> str:
    """Process a message from the operator and return a response.

    Uses Claude CLI for complex questions, built-in handlers for commands.
    """
    text_lower = text.strip().lower()

    # Check if intake is active — route answers to intake flow
    try:
        from telegram_intake import is_intake_active, process_intake_answer, cancel_intake
        if is_intake_active(CHAT_ID):
            if text_lower in ("/cancel", "cancel"):
                return cancel_intake(CHAT_ID)
            return process_intake_answer(CHAT_ID, text.strip())
    except Exception:
        pass

    # Quick commands (no Claude needed)
    if text_lower.startswith("/"):
        return handle_command(text_lower)

    # Long text (>200 chars, not a command) → treat as article paste
    if len(text.strip()) > 200:
        return handle_article_text(text)

    # Conversational message → intelligent response with full agency context
    try:
        from director_intelligence import respond
        return respond(text)
    except Exception as e:
        logger.warning("Intelligence layer unavailable: %s", e)
        return _fallback_answer(text)


def _check_digests(sent_digests: set) -> set:
    """Fire morning (8am) and evening (10pm) digests if not yet sent today."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    morning_key = f"{today}-morning"
    evening_key = f"{today}-evening"

    if now.hour == 8 and morning_key not in sent_digests:
        try:
            from digest import morning_digest
            text = morning_digest()
            send(f"Good morning.\n\n{text}")
            sent_digests.add(morning_key)
            logger.info("Morning digest sent.")
        except Exception as e:
            logger.error("Morning digest error: %s", e)

    if now.hour == 22 and evening_key not in sent_digests:
        try:
            from digest import evening_digest
            text = evening_digest()
            send(f"Day wrap.\n\n{text}")
            sent_digests.add(evening_key)
            logger.info("Evening digest sent.")
        except Exception as e:
            logger.error("Evening digest error: %s", e)

    return sent_digests


def main():
    """Main loop — long-poll Telegram and respond to messages."""
    logger.info("Director starting...")
    send("Director online.")

    last_update_id = 0
    sent_digests: set = set()
    last_message_time = time.time()

    # Skip old messages on startup
    try:
        resp = requests.get(f"{API_BASE}/getUpdates", params={"limit": 1, "offset": -1}, timeout=15)
        data = resp.json()
        if data.get("ok") and data.get("result"):
            last_update_id = data["result"][-1]["update_id"]
    except Exception:
        pass

    logger.info("Listening for Telegram messages (Ctrl-C to stop)...")

    while True:
        try:
            # Check digest schedule each loop iteration
            sent_digests = _check_digests(sent_digests)

            resp = requests.get(f"{API_BASE}/getUpdates", params={
                "offset": last_update_id + 1,
                "timeout": 30,
            }, timeout=35)
            data = resp.json()

            if data.get("ok"):
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    photo = msg.get("photo")  # list of photo sizes, or None
                    chat_id = msg.get("chat", {}).get("id")
                    sender = msg.get("from", {}).get("first_name", "")

                    if chat_id != CHAT_ID:
                        continue  # Ignore messages from other users
                    if not text and not photo:
                        continue

                    # Reset conversation history if the operator hasn't messaged in 2+ hours
                    idle_seconds = time.time() - last_message_time
                    if idle_seconds > 7200:
                        try:
                            from director_intelligence import clear_history
                            clear_history()
                        except Exception:
                            pass
                    last_message_time = time.time()

                    # Generate response
                    if photo:
                        logger.info("Photo message from %s", sender)
                        response = handle_photo(photo)
                    else:
                        logger.info("Message from %s: %s", sender, text[:80])
                        response = handle_message(text)

                    # Send response
                    send(response)
                    logger.info("Responded: %s", response[:80])

                    # Log to DB
                    try:
                        from agency_db import log_message
                        log_message("inbound", text or "[photo]", "chat")
                        log_message("outbound", response, "chat")
                    except Exception:
                        pass

        except requests.exceptions.ReadTimeout:
            continue  # Normal for long-polling
        except KeyboardInterrupt:
            logger.info("Director shutting down.")
            send("🔌 Director going offline.")
            break
        except Exception as e:
            logger.error("Error: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
