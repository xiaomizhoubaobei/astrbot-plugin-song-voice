"""会话状态与歌单渲染。"""

from __future__ import annotations

import asyncio
import time

import pytest


def test_key_depends_on_allow_group_select(core, config):
    session = core("session")
    store = session.PendingStore()
    assert store.key(config, "u1", "g1") == ("u1", "g1")
    config.allow_group_select = True
    assert store.key(config, "u1", "g1") == "g1"
    assert store.key(config, "u1", "") == "u1"  # 私聊退化为用户维度


def test_set_refreshes_created_at(core):
    session = core("session")
    store = session.PendingStore()
    old = session.PendingState("k", 1, [], created_at=time.time() - 999)
    store.set("key", old)
    assert not old.expired(45)


def test_pop_and_clear(core):
    session = core("session")
    store = session.PendingStore()
    state = session.PendingState("k", 1, [], created_at=time.time())
    store.set("a", state)
    store.set("b", state)
    assert store.pop("a") is state
    assert store.pop("a") is None
    store.clear()
    assert store.get("b") is None


def test_expired_boundary(core):
    session = core("session")
    assert session.PendingState("k", 1, [], created_at=time.time() - 45).expired(45)
    assert not session.PendingState("k", 1, [], created_at=time.time()).expired(45)


@pytest.mark.parametrize(
    ("text", "expected"), [("0", True), (" 不听了 ", True), ("1", False), ("", False)]
)
def test_is_exit_input(core, config, text, expected):
    assert core("session").is_exit_input(text, config) is expected


def test_render_menu(core, config):
    models = core("models")
    items = [models.SearchItem(str(i), f"歌{i}", "歌手", 100) for i in range(1, 4)]
    text = core("session").render_menu(config, "晴天", 2, items)
    assert "🎵 搜索：晴天（第 2 页）" in text
    assert "1. 歌1 - 歌手  [1:40]" in text
    assert "指令：上一页 / 下一页" in text
    assert "退出：0 / 不听了" in text
    assert text.endswith("回复序号即可点歌。")


def test_render_menu_respects_search_count_and_exit_hint(core, config):
    models = core("models")
    items = [models.SearchItem(str(i), f"歌{i}", "", None) for i in range(1, 11)]
    config.search_count = 3
    text = core("session").render_menu(config, "k", 1, items)
    assert "3. 歌3" in text and "4. 歌4" not in text
    config.show_exit_hint = False
    assert "退出：" not in core("session").render_menu(config, "k", 1, items)


def test_send_audio_record_uses_record_component(core):
    session = core("session")
    sent = []

    class Ctx:
        async def send_message(self, origin, message):
            sent.append((origin, message))

    asyncio.run(session.send_audio_record(Ctx(), "origin", "/tmp/a.mp3"))
    origin, message = sent[0]
    assert origin == "origin"
    assert message[0].file == "/tmp/a.mp3"


def test_send_audio_record_falls_back_without_component(core, monkeypatch):
    """老版本 AstrBot 没有 Record 组件时，降级为文件路径消息。"""
    session = core("session")
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "astrbot.api.message_components":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    sent = []

    class Ctx:
        async def send_message(self, origin, message):
            sent.append(message)

    asyncio.run(session.send_audio_record(Ctx(), "origin", "/tmp/a.mp3"))
    assert sent == [["/tmp/a.mp3"]]
