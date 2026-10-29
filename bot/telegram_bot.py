"""Telegram bot: forward a message, get the verdict, top reason and reply card.

Uses the Telegram Bot API over HTTPS long polling (verified against core.telegram.org/bots/api):
  POST https://api.telegram.org/bot<token>/getUpdates   {offset, timeout, allowed_updates}
  POST https://api.telegram.org/bot<token>/sendMessage  {chat_id, text}  (text 1-4096 chars)
  every response: {"ok": bool, "result": ..., "description": str}

It calls POST /check on the VERITY API and nothing else: no engine imports, no storage of
message text, and the bot token is never logged (it is part of Telegram request URLs).
"""

import logging
import os
import sys
import time

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from verity.schemas import CheckRequest, VerdictRecord

TELEGRAM_BASE = "https://api.telegram.org"
LONG_POLL_S = 30
MAX_TEXT = 4096  # sendMessage limit
VERITY_TIMEOUT_S = 60.0
ERROR_BACKOFF_S = 5.0

VERDICT_TEXT = {
    "likely_false": "Likely false",
    "unverified": "Unverified",
    "likely_true": "Likely true",
}
HELP = (
    "Send or forward me a message (English, Tamil or Hindi) and I will check it. "
    "I reply with a verdict, how sure I am, the main reason and a short reply you can pass on. "
    "I do not store your message; phone numbers and similar details are removed before checking."
)

log = logging.getLogger("verity.bot")


class _Chat(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int


class _Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    chat: _Chat
    text: str | None = None


class _Update(BaseModel):
    model_config = ConfigDict(extra="ignore")
    update_id: int
    message: _Message | None = None


class _Updates(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ok: bool
    result: list[_Update] = []
    description: str | None = None


def format_reply(record: VerdictRecord) -> str:
    head = f"{VERDICT_TEXT[record.verdict]} (about {round(record.p_true * 100)}% chance it is true)"
    return f"{head}\n\n{record.reply_card}"[:MAX_TEXT]


class TelegramBot:
    def __init__(
        self,
        token: str,
        verity_base: str,
        *,
        telegram: httpx.Client | None = None,
        verity: httpx.Client | None = None,
    ) -> None:
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        # httpx logs full request URLs at INFO, and Telegram URLs contain the token
        logging.getLogger("httpx").setLevel(logging.WARNING)
        self._url = f"{TELEGRAM_BASE}/bot{token}"
        self._tg = telegram or httpx.Client(timeout=LONG_POLL_S + 10)
        self._verity = verity or httpx.Client(base_url=verity_base, timeout=VERITY_TIMEOUT_S)

    def _send(self, chat_id: int, text: str) -> None:
        resp = self._tg.post(f"{self._url}/sendMessage", json={"chat_id": chat_id, "text": text})
        if not resp.json().get("ok"):
            log.warning("sendMessage rejected")  # never log the response or URL (token)

    def handle(self, update: _Update) -> None:
        msg = update.message
        if msg is None or not msg.text:
            return
        chat_id = msg.chat.id
        if msg.text.strip().lower() in ("/start", "/help"):
            self._send(chat_id, HELP)
            return
        try:
            resp = self._verity.post("/check", json=CheckRequest(text=msg.text).model_dump())
        except httpx.HTTPError:
            self._send(chat_id, "I cannot reach the checking service right now. Please try later.")
            return
        if resp.status_code == 200:
            try:
                self._send(chat_id, format_reply(VerdictRecord.model_validate_json(resp.content)))
            except ValidationError:
                self._send(chat_id, "I got an unexpected answer from the service.")
        elif resp.status_code == 422:
            code = resp.json().get("error", {}).get("code", "")
            note = (
                "I read English, Tamil and Hindi messages only."
                if code == "unsupported_language"
                else "I could not check that message. Please send the text of a forward."
            )
            self._send(chat_id, note)
        else:
            self._send(chat_id, "Something went wrong while checking. Please try again later.")

    def poll_once(self, offset: int | None) -> int | None:
        """Fetch and handle one batch of updates; returns the next offset."""
        payload: dict[str, object] = {"timeout": LONG_POLL_S, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        resp = self._tg.post(f"{self._url}/getUpdates", json=payload)
        parsed = _Updates.model_validate_json(resp.content)
        if not parsed.ok:
            raise RuntimeError("getUpdates was rejected")
        for update in parsed.result:
            self.handle(update)
            offset = update.update_id + 1  # one greater than the highest handled id
        return offset

    def run(self) -> None:
        offset: int | None = None
        while True:
            try:
                offset = self.poll_once(offset)
            except (httpx.HTTPError, RuntimeError, ValidationError) as exc:
                log.warning("polling error: %s", type(exc).__name__)
                time.sleep(ERROR_BACKOFF_S)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN (from @BotFather) and run `make api` first.", file=sys.stderr)
        return 1
    base = os.environ.get("API_BASE", "http://localhost:8000")
    TelegramBot(token, base).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
