"""No-token QQ natural-chat behavior and proactive delivery regression tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.napcat.natural_chat import split_for_qq
from nanobot.channels.napcat.proactive import (
    CheckinLedger, CheckinPolicy, choose_greeting,
)
from nanobot.channels.napcat.runtime import NapcatChannel, NapcatConfig


def private():
    config = NapcatConfig(private_only=True, owner_qq="123456", allow_from=["123456"])
    config.reply_delay_min_seconds = 0
    config.reply_delay_max_seconds = 0
    config.chunk_delay_min_seconds = 0
    config.chunk_delay_max_seconds = 0
    return NapcatChannel(config, MessageBus())


def incoming(msg_id: int, text: str = "new"):
    return {
        "message_type": "private", "user_id": 123456, "message_id": msg_id,
        "message": [{"type": "text", "data": {"text": text}}],
    }


def test_semantic_chunks_preserve_text():
    text = "诶？被你发现啦！刚刚在想，龙角能不能接 Wi-Fi。唔，好像搞错方向了 QAQ！"
    chunks = split_for_qq(text)
    assert 2 <= len(chunks) <= 3
    assert "".join("".join(chunks).split()) == "".join(text.split())
    assert "龙角" in "".join(chunks)


@pytest.mark.parametrize("text", [
    "def run():\n    return True",  # one short snippet
    "这是代码块：\n" + chr(96) * 3 + "python\nprint(1)\n" + chr(96) * 3,
    "看看 https://example.org/a?foo=x! 然后再决定。不能把链接剪开。",
    "- 第一条\n- 第二条\n- 第三条",
    '{"value": "测试。还有这段！"}',
])
def test_technical_text_kept_intact(text):
    assert split_for_qq(text) == [text]


@pytest.mark.asyncio
async def test_three_qq_messages_not_three_model_calls(monkeypatch):
    channel = private()
    channel._ws = object()
    sent = []

    async def fake_action(action, payload):
        assert action == "send_msg"
        sent.append(payload["message"])
        return {"data": {"message_id": len(sent) + 10}}

    monkeypatch.setattr(channel, "_call_action", fake_action)
    await channel.send(OutboundMessage(
        channel="napcat", chat_id="private:123456",
        content="诶？被你发现啦！刚刚在想，龙角到底能不能接 Wi-Fi。唔，好像搞错方向了！",
    ))
    assert len(sent) in (2, 3)
    assert all(len(frame) == 1 and frame[0]["type"] == "text" for frame in sent)


@pytest.mark.asyncio
async def test_owner_interrupt_aborts_remaining_chunks(tmp_path, monkeypatch):
    channel = private()
    channel._ws = object()
    channel._ledger.path = tmp_path / "dedup.db"
    sent = []

    async def fake_action(action, payload):
        sent.append(payload["message"])
        if len(sent) == 1:
            await channel._on_message(incoming(991, "我插话啦"))
        return {"data": {"message_id": len(sent)}}

    monkeypatch.setattr(channel, "_call_action", fake_action)
    await channel.send(OutboundMessage(
        channel="napcat", chat_id="private:123456",
        content="诶？你来啦！我刚刚想到了一个主意。等等，我再想想细节。现在想起来啦！",
    ))
    assert len(sent) == 1
    assert channel.bus.inbound_size == 1


@pytest.mark.asyncio
async def test_technical_message_not_split(monkeypatch):
    channel = private()
    channel._ws = object()
    frames = []

    async def fake_action(action, payload):
        frames.append(payload["message"])
        return {"data": {"message_id": 1}}

    monkeypatch.setattr(channel, "_call_action", fake_action)
    long_code = "测试一下：\n" + chr(96) * 3 + "python\nfor i in range(10): print(i)\n" + chr(96) * 3
    await channel.send(OutboundMessage(
        channel="napcat", chat_id="private:123456", content=long_code,
    ))
    assert len(frames) == 1


@pytest.mark.asyncio
async def test_partial_send_does_not_request_whole_reply_retry(monkeypatch):
    channel = private()
    channel._ws = object()
    calls = []

    async def fake_action(action, params):
        calls.append(params["message"])
        if len(calls) == 2:
            raise RuntimeError("network uncertainty on second part")
        return {"data": {"message_id": len(calls)}}

    monkeypatch.setattr(channel, "_call_action", fake_action)
    await channel.send(OutboundMessage(
        channel="napcat", chat_id="private:123456",
        content="诶？你来啦！有个新消息要说。再等一下，我要补充一点！最后还有一个问题？",
    ))
    assert len(calls) == 2


def test_checkin_is_opt_in_bounded_and_keeps_quiet_hours(tmp_path):
    policy = CheckinPolicy(
        timezone="Asia/Shanghai", start_hour=12, end_hour=20,
        min_idle_seconds=3600, probability=1.0,
    )
    noon = datetime(2026, 10, 20, 5, 0, tzinfo=timezone.utc)  # 13:00 Beijing
    night = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc) # 00:00 next day
    assert policy.eligible(noon, idle_seconds=3700, owner_qq="123456")
    assert not policy.eligible(noon, idle_seconds=300, owner_qq="123456")
    assert not policy.eligible(night, idle_seconds=3700, owner_qq="123456")
    day = policy.local_day(noon)
    ledger = CheckinLedger(tmp_path / "checkins.db")
    assert ledger.claim("123456", day)
    assert not CheckinLedger(tmp_path / "checkins.db").claim("123456", day)
    assert "?" in choose_greeting("123456", day) or "？" in choose_greeting("123456", day) or "来看看" in choose_greeting("123456", day)


@pytest.mark.asyncio
async def test_proactive_must_be_private_only():
    channel = NapcatChannel(
        NapcatConfig(proactive_checkins_enabled=True, private_only=False),
        MessageBus(),
    )
    with pytest.raises(ValueError, match="privateOnly"):
        await channel.start()
