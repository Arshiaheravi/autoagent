"""Tests for comms.py — Telegram reply threading security fix."""
import threading
from unittest.mock import patch, MagicMock
import comms


def test_send_returns_message_id_on_success():
    """_send() should return the message_id (int) on success, None on failure."""
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"ok": True, "result": {"message_id": 42}}

    with patch("comms.requests.post", return_value=fake_resp):
        result = comms._send("hello")

    assert result == 42


def test_send_returns_none_on_failure():
    """_send() should return None when Telegram API fails."""
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"ok": False}

    with patch("comms.requests.post", return_value=fake_resp):
        result = comms._send("hello")

    assert result is None


def test_send_returns_none_on_exception():
    """_send() should return None when request throws."""
    with patch("comms.requests.post", side_effect=Exception("network")):
        result = comms._send("hello")

    assert result is None


def test_reply_routing_requires_thread():
    """_poll_for_reply only accepts messages that reply to the specific question message_id."""
    # Simulate: question was sent as message_id=100
    # An unrelated message (no reply_to) arrives → should be IGNORED
    # A reply to message_id=100 arrives → should be ACCEPTED

    comms._pending_question = {"question": "test?"}
    comms._reply_event = threading.Event()
    comms._reply_text = ""
    comms._question_message_id = 100

    unrelated_update = {
        "update_id": 1001,
        "message": {
            "text": "random message",
            "chat": {"id": comms.CHAT_ID},
            # No reply_to_message — this is NOT a reply
        },
    }
    reply_update = {
        "update_id": 1002,
        "message": {
            "text": "yes, do it",
            "chat": {"id": comms.CHAT_ID},
            "reply_to_message": {"message_id": 100},  # Reply to our question
        },
    }

    # First poll returns unrelated, second returns the reply
    responses = [
        _fake_get_updates_response([unrelated_update]),
        _fake_get_updates_response([reply_update]),
    ]

    with patch("comms.requests.get", side_effect=[
        _fake_get_updates_response([]),  # initial offset fetch
        responses[0],
        responses[1],
    ]), patch("comms._send"), patch("comms.time.sleep"):
        comms._poll_for_reply()

    assert comms._reply_text == "yes, do it"
    assert comms._reply_event.is_set()


def test_ask_returns_none_for_unrelated_message():
    """Unrelated messages (not replies to the question) are ignored during polling."""
    comms._pending_question = {"question": "test?"}
    comms._reply_event = threading.Event()
    comms._reply_text = ""
    comms._question_message_id = 200

    # Only unrelated messages arrive — no reply_to_message matching 200
    wrong_reply = {
        "update_id": 2001,
        "message": {
            "text": "replying to wrong msg",
            "chat": {"id": comms.CHAT_ID},
            "reply_to_message": {"message_id": 999},  # Wrong message
        },
    }

    with patch("comms.requests.get", side_effect=[
        _fake_get_updates_response([]),  # initial offset fetch
        _fake_get_updates_response([wrong_reply]),
    ]), patch("comms._send"), patch("comms.time.sleep"):
        # Set pending to None after first poll to break loop
        original_poll = comms._poll_for_reply.__wrapped__ if hasattr(comms._poll_for_reply, '__wrapped__') else None

        # Run poll with limited iterations — after 2 polls, stop
        call_count = [0]
        original_get = None

        def limited_get(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _fake_get_updates_response([])  # offset
            if call_count[0] == 2:
                return _fake_get_updates_response([wrong_reply])
            # Stop polling by clearing pending question
            comms._pending_question = None
            return _fake_get_updates_response([])

        with patch("comms.requests.get", side_effect=limited_get), \
             patch("comms._send"), patch("comms.time.sleep"):
            comms._poll_for_reply()

    # Should NOT have accepted the wrong reply
    assert comms._reply_text == ""
    assert not comms._reply_event.is_set()


def test_notify_still_returns_bool():
    """notify() should still return bool for backward compat."""
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"ok": True, "result": {"message_id": 1}}

    with patch("comms.requests.post", return_value=fake_resp):
        result = comms.notify("test", project="p")

    assert result is True


# ── Helpers ──────────────────────────────────────────────────────

def _fake_get_updates_response(updates):
    resp = MagicMock()
    resp.json.return_value = {"ok": True, "result": updates}
    return resp
