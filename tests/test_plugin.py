"""插件入口的流程编排：搜索、翻页、序号点播、发送策略。

这里不打桩 astrbot 的事件对象，而是喂一个「够用就好」的假 event：
被测的是插件自己的判断，不是框架。
"""

from __future__ import annotations

import asyncio
import time
import types
from pathlib import Path

import pytest

PKG = "astrbot_plugin_song_voice"


@pytest.fixture
def main_mod():
    return __import__(f"{PKG}.main", fromlist=["SongVoicePlugin"])


class FakeEvent:
    def __init__(self, text, user="u1", group="g1"):
        self.message_str = text
        self.unified_msg_origin = f"{user}:{group}"
        self._user = user
        self._group = group
        self.stopped = False

    def get_sender_id(self):
        return self._user

    def get_group_id(self):
        return self._group

    def plain_result(self, text):
        return ("plain", text)

    def stop_event(self):
        self.stopped = True


def _run(coro_iter):
    async def _collect():
        return [item async for item in coro_iter]

    return asyncio.run(_collect())


def _consume(plugin, event):
    """跑一遍 on_message，返回 (产出文本列表, 是否 stop)。"""
    texts = []
    for _kind, text in _run(plugin.on_message(event)):
        texts.append(text)
    return texts, event.stopped


@pytest.fixture
def plugin(main_mod, config, monkeypatch, tmp_path):
    config.check_ffmpeg_on_start = False
    config.record_path = str(tmp_path / "record")
    instance = main_mod.SongVoicePlugin(context=types.SimpleNamespace(), config=config)
    instance.sent = []

    async def _send(_event, path):
        instance.sent.append(path)

    monkeypatch.setattr(instance, "_send_audio", _send)
    return instance


def test_config_may_be_a_plain_object(main_mod):
    """AstrBot 传入的可能是 dict / 配置对象，两种都要能吃下。"""
    obj = types.SimpleNamespace(command="来一首", br="320")
    plugin = main_mod.SongVoicePlugin(types.SimpleNamespace(), obj)
    assert plugin.config_obj.command == "来一首"
    assert plugin.config_obj.br == 320


def test_empty_message_is_ignored(plugin):
    texts, stopped = _consume(plugin, FakeEvent("   "))
    assert texts == [] and stopped is False


def test_message_without_pending_state_is_ignored(plugin):
    texts, _ = _consume(plugin, FakeEvent("随便说点啥"))
    assert texts == []


def test_empty_keyword_prompts(plugin):
    texts, stopped = _consume(plugin, FakeEvent("点歌"))
    assert texts == [plugin.config_obj.empty_keyword] and stopped


def test_search_success_renders_menu(plugin, core):
    async def _search(keyword, page):
        return [core("models").SearchItem("1", "晴天", "周杰伦", 269)]

    plugin.api.search = _search
    texts, stopped = _consume(plugin, FakeEvent("点歌 晴天"))
    assert "晴天" in texts[0] and stopped
    assert "1. 晴天 - 周杰伦  [4:29]" in texts[0]


def test_search_exception_reports_failure(plugin):
    async def _search(keyword, page):
        raise RuntimeError("boom")

    plugin.api.search = _search
    texts, _ = _consume(plugin, FakeEvent("点歌 晴天"))
    assert texts == [plugin.config_obj.get_song_failed]


def test_search_empty_reports_empty(plugin):
    async def _search(keyword, page):
        return []

    plugin.api.search = _search
    texts, _ = _consume(plugin, FakeEvent("点歌 不存在"))
    assert texts == [plugin.config_obj.empty_result]


def _seed(plugin, keyword="晴天", page=1, duration=269, song_id="1"):
    """把一条待选歌单直接塞进会话，模拟「搜索完等用户回序号」。"""
    cfg = plugin.config_obj
    state = __import__(f"{PKG}.core.session", fromlist=["PendingState"]).PendingState(
        keyword=keyword,
        page=page,
        items=[
            __import__(f"{PKG}.core.models", fromlist=["SearchItem"]).SearchItem(
                song_id, "晴天", "周杰伦", duration
            )
        ],
        created_at=time.time(),
    )
    plugin.pending.set(plugin.pending.key(cfg, "u1", "g1"), state)
    return state


def test_timeout_drops_state(plugin):
    state = _seed(plugin)
    state.created_at = time.time() - 999
    texts, _ = _consume(plugin, FakeEvent("1"))
    assert texts == [plugin.config_obj.prompt_timeout]
    assert plugin.pending.get(("u1", "g1")) is None


def test_exit_clears_state(plugin):
    _seed(plugin)
    texts, _ = _consume(plugin, FakeEvent("0"))
    assert texts == [plugin.config_obj.exit_prompt]
    assert plugin.pending.get(("u1", "g1")) is None


def test_paging_moves_to_next_page(plugin, core):
    _seed(plugin)
    pages = []

    async def _search(keyword, page):
        pages.append(page)
        return [core("models").SearchItem("1", "晴天", "", None)]

    plugin.api.search = _search
    texts, _ = _consume(plugin, FakeEvent("下一页"))
    assert pages == [2] and "第 2 页" in texts[0]
    _consume(plugin, FakeEvent("上一页"))
    assert pages == [2, 1]


def test_prev_page_never_goes_below_one(plugin, core):
    _seed(plugin, page=1)
    pages = []

    async def _search(keyword, page):
        pages.append(page)
        return [core("models").SearchItem("1", "歌", "", None)]

    plugin.api.search = _search
    _consume(plugin, FakeEvent("上一页"))
    assert pages == [1]


def test_non_numeric_input_is_ignored(plugin):
    _seed(plugin)
    texts, stopped = _consume(plugin, FakeEvent("来点别的"))
    assert texts == [] and stopped is False


def test_index_out_of_range(plugin):
    _seed(plugin)
    texts, stopped = _consume(plugin, FakeEvent("9"))
    assert texts == [plugin.config_obj.invalid_number] and stopped


def test_song_without_id_reports_failure(plugin):
    _seed(plugin, song_id=None)
    texts, _ = _consume(plugin, FakeEvent("1"))
    assert texts == [plugin.config_obj.get_song_failed]


def test_direct_link_is_sent_without_transcode(plugin, monkeypatch, core):
    _seed(plugin)
    audio = core("audio")

    async def _url(_sid):
        return "http://cdn/a.mp3", 192

    async def _download(_url):
        return b"MP3"

    monkeypatch.setattr(audio, "ffmpeg_available", lambda b: True)
    plugin.api.song_url = _url
    plugin.api.download = _download

    texts, _ = _consume(plugin, FakeEvent("1"))
    assert texts == [plugin.config_obj.generation_tip]
    assert Path(plugin.sent[0]).read_bytes() == b"MP3"
    assert Path(plugin.sent[0]).suffix == ".mp3"


def test_wma_link_without_ffmpeg_falls_back_to_file(plugin, monkeypatch, core):
    _seed(plugin)
    audio = core("audio")

    async def _url(_sid):
        return "http://cdn/a.wma", 128

    async def _download(_url):
        return b"WMA"

    monkeypatch.setattr(audio, "ffmpeg_available", lambda b: False)
    plugin.api.song_url = _url
    plugin.api.download = _download
    texts, _ = _consume(plugin, FakeEvent("1"))
    # 无 ffmpeg 时裸文件发不出去属于已知边界：上报 send_failed，而不是抛异常
    assert texts[-1] == plugin.config_obj.send_failed
    assert plugin.sent == []


def test_high_bitrate_triggers_transcode(plugin, main_mod, monkeypatch, core):
    _seed(plugin)
    audio = core("audio")
    # transcode 在 main.py 里是位置参数调用，这里的假实现也保持位置参数签名
    seen = {}

    async def _url(_sid):
        return "http://cdn/a.mp3", 999

    async def _download(_url):
        return b"RAW"

    async def _transcode(binary, data, fmt, timeout_ms):
        seen["fmt"] = fmt
        return b"AAC", "song.aac", "audio/aac"

    monkeypatch.setattr(audio, "ffmpeg_available", lambda b: True)
    monkeypatch.setattr(audio, "transcode", _transcode)
    # main.py 里对 write_temp 是位置参数调用：打桩签名必须与之对齐，
    # 否则会静默 TypeError → 走到 send_failed，测试「绿了但没测到转码」。
    real_write_temp = audio.write_temp
    monkeypatch.setattr(
        audio,
        "write_temp",
        lambda path_dir, filename, data: real_write_temp(path_dir, filename, data),
    )
    # ⚠️ main.py 在导入时就把 transcode / ffmpeg_available 绑到了本模块命名空间，
    #    只打桩 core.audio 不会被看到；这里连同模块级名字一起替换。
    monkeypatch.setattr(main_mod, "transcode", _transcode)
    monkeypatch.setattr(main_mod, "ffmpeg_available", lambda b: True)
    plugin.api.song_url = _url
    plugin.api.download = _download

    texts, _ = _consume(plugin, FakeEvent("1"))
    assert texts == [plugin.config_obj.generation_tip], texts
    assert seen["fmt"] == plugin.config_obj.transcode_format
    assert Path(plugin.sent[0]).name == "song.aac"


def test_transcode_failure_retries_as_wav(plugin, main_mod, monkeypatch, core):
    _seed(plugin)
    audio = core("audio")

    async def _url(_sid):
        return "http://cdn/a.wma", 128

    async def _download(_url):
        return b"RAW"

    async def _boom(*a, **k):
        raise RuntimeError("bad codec")

    async def _wav(binary, data, timeout_ms):
        return b"WAV"

    monkeypatch.setattr(audio, "transcode", _boom)
    monkeypatch.setattr(audio, "to_wav", _wav)
    # 模块级绑定：见上一个用例的说明
    monkeypatch.setattr(main_mod, "transcode", _boom)
    monkeypatch.setattr(main_mod, "ffmpeg_available", lambda b: True)
    plugin.api.song_url = _url
    plugin.api.download = _download

    texts, _ = _consume(plugin, FakeEvent("1"))
    assert texts == [plugin.config_obj.generation_tip], texts
    assert Path(plugin.sent[0]).name == "song.wav"


def test_missing_direct_link_reports_failure(plugin):
    _seed(plugin)

    async def _url(_sid):
        return None, None

    plugin.api.song_url = _url
    texts, _ = _consume(plugin, FakeEvent("1"))
    assert plugin.config_obj.get_song_failed in texts


def test_song_url_exception_reports_failure(plugin):
    _seed(plugin)

    async def _url(_sid):
        raise RuntimeError("net down")

    plugin.api.song_url = _url
    texts, _ = _consume(plugin, FakeEvent("1"))
    assert plugin.config_obj.get_song_failed in texts


def test_duration_limit_blocks_long_songs(plugin):
    _seed(plugin, duration=99 * 60)

    async def _url(_sid):
        return "http://cdn/a.mp3", 128

    plugin.api.song_url = _url
    texts, _ = _consume(plugin, FakeEvent("1"))
    assert plugin.config_obj.duration_exceeded in texts


def test_send_failure_is_reported(plugin, monkeypatch, core):
    _seed(plugin)
    audio = core("audio")

    async def _url(_sid):
        return "http://cdn/a.mp3", 128

    async def _download(_url):
        raise RuntimeError("404")

    monkeypatch.setattr(audio, "ffmpeg_available", lambda b: True)
    plugin.api.song_url = _url
    plugin.api.download = _download
    texts, _ = _consume(plugin, FakeEvent("1"))
    assert plugin.config_obj.send_failed in texts
    assert plugin.sent == []


def test_state_is_cleared_after_play(plugin, monkeypatch, core):
    _seed(plugin)
    audio = core("audio")

    async def _url(_sid):
        return "http://cdn/a.mp3", 128

    async def _download(_url):
        return b"MP3"

    monkeypatch.setattr(audio, "ffmpeg_available", lambda b: True)
    plugin.api.song_url = _url
    plugin.api.download = _download

    _consume(plugin, FakeEvent("1"))
    assert plugin.pending.get(("u1", "g1")) is None


def test_play_without_state_reports_failure(plugin):
    texts = [t for t in _run(plugin._play(FakeEvent("1"), "nokey", 1))]
    assert texts == [plugin.config_obj.get_song_failed]


def test_alias_triggers_search(plugin, core):
    async def _search(keyword, page):
        return [core("models").SearchItem("1", keyword, "", None)]

    plugin.api.search = _search
    texts, _ = _consume(plugin, FakeEvent("music 稻香"))
    assert "稻香" in texts[0]


def test_who_falls_back_when_event_lacks_getters(plugin):
    event = types.SimpleNamespace()
    assert plugin._who(event) == ("", "")


def test_startup_logs_ffmpeg_state(main_mod, monkeypatch, core):
    audio = core("audio")
    monkeypatch.setattr(audio, "ffmpeg_available", lambda b: True)
    cfg = core("config").PluginConfig()
    cfg.check_ffmpeg_on_start = True
    main_mod.SongVoicePlugin(types.SimpleNamespace(), cfg)  # 不抛即通过


def test_terminate_clears_state(plugin):
    _seed(plugin)
    closed = []

    async def _close():
        closed.append(True)

    plugin.api.close = _close
    asyncio.run(plugin.terminate())
    assert closed == [True]
    assert plugin.pending.get(("u1", "g1")) is None


def test_who_reads_sender_and_group(plugin):
    assert plugin._who(FakeEvent("x", user="42", group="7")) == ("42", "7")


def test_send_audio_delegates_to_session(plugin, main_mod, monkeypatch):
    """_send_audio 必须把 origin 透传给统一发送入口。"""
    seen = {}

    async def _record(ctx, origin, path):
        seen.update(ctx=ctx, origin=origin, path=path)

    # main.py 导入时已把 send_audio_record 绑到自身命名空间
    monkeypatch.setattr(main_mod, "send_audio_record", _record)
    monkeypatch.setattr(
        plugin, "_send_audio", main_mod.SongVoicePlugin._send_audio.__get__(plugin)
    )
    event = FakeEvent("x")
    asyncio.run(plugin._send_audio(event, "/tmp/a.mp3"))
    assert seen["origin"] == event.unified_msg_origin
    assert seen["path"] == "/tmp/a.mp3"


def test_debug_mode_logs_exception(plugin, main_mod, monkeypatch, core):
    _seed(plugin)
    plugin.config_obj.debug = True
    logged = []
    monkeypatch.setattr(
        main_mod,
        "logger",
        types.SimpleNamespace(
            warning=lambda *a: None,
            info=lambda *a: None,
            exception=logged.append,
            debug=lambda *a: None,
        ),
    )

    async def _url(_sid):
        return "http://cdn/a.mp3", 128

    async def _download(_url):
        raise RuntimeError("404")

    monkeypatch.setattr(main_mod, "ffmpeg_available", lambda b: True)
    plugin.api.song_url = _url
    plugin.api.download = _download

    texts, _ = _consume(plugin, FakeEvent("1"))
    assert texts[-1] == plugin.config_obj.send_failed
    assert logged  # debug 打开时应留下堆栈


def test_startup_warns_when_ffmpeg_missing(main_mod, monkeypatch, core):
    warned = []
    monkeypatch.setattr(
        main_mod,
        "logger",
        types.SimpleNamespace(
            info=lambda *a: None,
            warning=lambda *a: warned.append(a),
            exception=lambda *a: None,
            debug=lambda *a: None,
        ),
    )
    monkeypatch.setattr(main_mod, "ffmpeg_available", lambda b: False)
    cfg = core("config").PluginConfig()
    cfg.check_ffmpeg_on_start = True
    main_mod.SongVoicePlugin(types.SimpleNamespace(), cfg)
    assert warned
