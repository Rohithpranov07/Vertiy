import json
import logging

import httpx
import pytest
from bot.telegram_bot import HELP, MAX_TEXT, TelegramBot, _Update, format_reply
from fastapi.testclient import TestClient
from tests.conftest import DEBUNKED

from verity.api.app import create_app
from verity.pipeline import Pipeline

TOKEN = "123456:SECRET-TOKEN"

# SYNTHETIC FIXTURE: fake Telegram transport and the real API app via TestClient.


class FakeTelegram:
    def __init__(self, updates: list[dict[str, object]]) -> None:
        self.updates = updates
        self.sent: list[dict[str, object]] = []
        self.urls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.urls.append(str(request.url))
        body = json.loads(request.content)
        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(200, json={"ok": True, "result": self.updates})
        self.sent.append(body)
        return httpx.Response(200, json={"ok": True, "result": {}})


def _update(uid: int, text: str | None, chat: int = 7) -> dict[str, object]:
    msg: dict[str, object] = {"message_id": uid, "chat": {"id": chat, "type": "private"}, "date": 1}
    if text is not None:
        msg["text"] = text
    return {"update_id": uid, "message": msg}


def _bot(fake: FakeTelegram, world: Pipeline) -> TelegramBot:
    return TelegramBot(
        TOKEN,
        "http://testserver",
        telegram=httpx.Client(transport=httpx.MockTransport(fake)),
        verity=TestClient(create_app(world)),
    )


def test_poll_replies_with_verdict_reason_and_card(world: Pipeline) -> None:
    fake = FakeTelegram(
        [_update(10, DEBUNKED), _update(11, "/start"), _update(12, None), _update(13, "   ")]
    )
    bot = _bot(fake, world)
    assert bot.poll_once(None) == 14  # one greater than the highest handled update id
    texts = [str(m["text"]) for m in fake.sent]
    assert texts[0].startswith("Likely false") and "published fact-check" in texts[0]
    assert "http://f.example/lemon" in texts[0] and fake.sent[0]["chat_id"] == 7
    assert texts[1] == HELP
    assert "could not check" in texts[2]  # blank text -> 422 handled calmly
    assert len(fake.sent) == 3  # the textless update is ignored
    assert all(len(t) <= MAX_TEXT for t in texts)


def test_unsupported_language_and_unreachable_service(world: Pipeline) -> None:
    fake = FakeTelegram([_update(1, "Dies ist ein ziemlich langer deutscher Satz über das Wetter")])
    _bot(fake, world).poll_once(5)
    assert "English, Tamil and Hindi" in str(fake.sent[0]["text"])

    down = FakeTelegram([_update(2, "hello there friends")])

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    bot = TelegramBot(
        TOKEN,
        "http://x",
        telegram=httpx.Client(transport=httpx.MockTransport(down)),
        verity=httpx.Client(transport=httpx.MockTransport(refuse), base_url="http://x"),
    )
    bot.poll_once(None)
    assert "cannot reach" in str(down.sent[0]["text"])


def test_token_is_never_logged_and_text_not_stored(
    world: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeTelegram([_update(1, DEBUNKED)])
    with caplog.at_level(logging.DEBUG):
        _bot(fake, world).poll_once(None)
    assert TOKEN not in caplog.text and "SECRET" not in caplog.text
    assert any(TOKEN in u for u in fake.urls)  # the token is only in the Telegram URL path


def test_format_reply_is_bounded() -> None:
    from tests.test_ui import record

    rec = record().model_copy(update={"reply_card": "x" * 9000})
    assert len(format_reply(rec)) == MAX_TEXT
    assert _Update.model_validate({"update_id": 1}).message is None
