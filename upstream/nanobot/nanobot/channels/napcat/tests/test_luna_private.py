"""Luna owner-only QQ, audio and durable replay contract tests."""

from __future__ import annotations

import base64
import json

import pytest

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.napcat.ledger import MessageLedger
from nanobot.channels.napcat.media_audio import RecordMediaError, resolve_record
from nanobot.channels.napcat.runtime import NapcatChannel, NapcatConfig


def private_channel():
    return NapcatChannel(
        NapcatConfig(private_only=True, owner_qq="123456", allow_from=["123456"]),
        MessageBus(),
    )


def message(sender="123456", kind="private", message_id=10, segments=None):
    return {
        "post_type": "message",
        "message_id": message_id,
        "user_id": sender,
        "group_id": 54321 if kind == "group" else None,
        "message_type": kind,
        "message": segments or [{"type": "text", "data": {"text": "hello"}}],
    }


@pytest.mark.asyncio
async def test_owner_private_chat_allowed(tmp_path):
    channel = private_channel()
    channel._ledger = MessageLedger(tmp_path / "processed.db")
    await channel._on_message(message())
    assert channel.bus.inbound_size == 1
    inbound = await channel.bus.consume_inbound()
    assert inbound.chat_id == "private:123456"
    assert inbound.content == "hello"


@pytest.mark.asyncio
async def test_unauthorized_media_never_downloaded(tmp_path, monkeypatch):
    channel = private_channel()
    channel._ledger = MessageLedger(tmp_path / "processed.db")
    calls = []

    async def download(_info):
        calls.append(True)
        raise AssertionError("media MUST NOT download")

    monkeypatch.setattr(channel, "_download_image", download)
    image = [{"type": "image", "data": {"url": "https://example.org/test.png"}}]
    await channel._on_message(message(sender="999999", segments=image))
    await channel._on_message(message(kind="group", segments=image))
    assert not calls
    assert channel.bus.inbound_size == 0


@pytest.mark.asyncio
async def test_owner_group_mention_blocked(tmp_path):
    channel = private_channel()
    channel._ledger = MessageLedger(tmp_path / "processed.db")
    channel._self_id = 42
    await channel._on_message(message(kind="group", segments=[
        {"type": "at", "data": {"qq": 42}},
        {"type": "text", "data": {"text": "Luna?"}},
    ]))
    assert channel.bus.inbound_size == 0


@pytest.mark.asyncio
async def test_dedup_survives_new_channel_instance(tmp_path):
    db = tmp_path / "processed.db"
    first = private_channel()
    first._ledger = MessageLedger(db)
    await first._on_message(message(message_id=99))
    assert first.bus.inbound_size == 1

    second = private_channel()
    second._ledger = MessageLedger(db)
    await second._on_message(message(message_id=99))
    assert second.bus.inbound_size == 0


@pytest.mark.asyncio
async def test_audio_record_transcribed_and_cleaned(tmp_path, monkeypatch):
    channel = private_channel()
    channel.config.enable_voice_input = True
    channel._ledger = MessageLedger(tmp_path / "processed.db")
    channel._media_root = tmp_path

    async def fake_action(action, params):
        assert action == "get_record"
        assert params["out_format"] == "mp3"
        return {"data": {"base64": base64.b64encode(b"audio-content").decode()}}

    async def fake_asr(audio_path):
        assert audio_path.is_file()
        return "我有个问题"

    monkeypatch.setattr(channel, "_call_action", fake_action)
    monkeypatch.setattr(channel, "transcribe_audio", fake_asr)

    await channel._on_message(message(segments=[
        {"type": "record", "data": {"file": "voice_id.silk", "file_size": 13}}
    ]))
    msg = await channel.bus.consume_inbound()
    assert "[语音转写] 我有个问题" in msg.content
    assert not list(tmp_path.glob("record-*.mp3"))


@pytest.mark.asyncio
async def test_voice_reply_requires_explicit_opt_in(tmp_path, monkeypatch):
    channel = private_channel()
    channel._ws = object()
    channel._media_root = tmp_path
    channel.config.tts_model_path = "/not/actually/a/model.onnx"
    sent = []

    async def fake_action(action, params):
        sent.append((action, params))
        return {"data": {"message_id": 42}}

    async def fake_synthesize(*_args):
        return b"small audio file"

    monkeypatch.setattr(channel, "_call_action", fake_action)
    monkeypatch.setattr("nanobot.channels.napcat.runtime.synthesize_voice", fake_synthesize)

    await channel.send(OutboundMessage(channel="napcat", chat_id="private:123456", content="hello"))
    assert sent[0][1]["message"][0]["type"] == "text"

    channel._voice_reply_on.add("private:123456")
    await channel.send(OutboundMessage(channel="napcat", chat_id="private:123456", content="hello"))
    assert sent[1][1]["message"][0]["type"] == "record"
    assert sent[1][1]["message"][0]["data"]["file"].startswith("base64://")


@pytest.mark.asyncio
async def test_audio_refuses_outside_shared_root(tmp_path):
    outside = tmp_path / "not-in-root.mp3"
    outside.write_bytes(b"audio")
    root = tmp_path / "share"
    root.mkdir()

    async def fake_action(*_):
        return {"data": {"file": str(outside)}}

    with pytest.raises(RecordMediaError, match="outside shared"):
        await resolve_record(
            {"file": "voice.silk"}, fake_action, None, tmp_path,
            max_bytes=1024, shared_root=str(root),
        )


def test_configuration_aliases():
    cfg = NapcatConfig.model_validate({
        "privateOnly": True, "ownerQq": "123456",
        "enableVoiceInput": True, "maxAudioBytes": 2000000,
        "allowFrom": ["123456"],
    })
    assert cfg.private_only and cfg.owner_qq == "123456"
    assert cfg.enable_voice_input and cfg.max_audio_bytes == 2000000
