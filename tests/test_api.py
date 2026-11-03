"""API 层：URL 拼装、响应解包、码率阶梯与重试。全部打桩，不出网。"""

from __future__ import annotations

import asyncio
import types

import pytest


def test_normalize_items_unwraps_common_shapes(core):
    api = core("api")
    rows = [{"id": 1, "name": "晴天", "artist": "周杰伦"}]
    for payload in (
        rows,
        {"data": rows},
        {"result": rows},
        {"data": {"songs": rows}},
        {"result": {"list": rows}},
    ):
        items = api.normalize_items(payload)
        assert [i.name for i in items] == ["晴天"]


def test_normalize_items_drops_non_dict_rows(core):
    api = core("api")
    items = api.normalize_items({"data": [{"id": "1", "name": "a"}, "junk", 3]})
    assert len(items) == 1


def test_normalize_items_handles_garbage(core):
    api = core("api")
    assert api.normalize_items(None) == []
    assert api.normalize_items("nope") == []
    assert api.normalize_items({"data": "nope"}) == []


def test_parse_tolerates_non_json(core):
    api = core("api")

    class Resp:
        def json(self):
            raise ValueError

    assert api._parse(Resp()) is None


def test_url_join_respects_existing_query(core, config):
    api = core("api").MusicApi(config)
    assert api._url({"a": 1}) == f"{config.api_base}?a=1"
    config.api_base = "https://x/api?token=t"
    assert api._url({"a": 1}).endswith("?token=t&a=1")


class _Resp:
    def __init__(self, payload=None, exc=None, content=b"", status_code=200):
        self._payload = payload
        self._exc = exc
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self._exc:
            raise self._exc

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.fixture
def client_holder(core, config, monkeypatch):
    """把 MusicApi 的 AsyncClient 换成计数器，记录请求次数。"""
    api = core("api")
    instance = api.MusicApi(config)
    state = {"calls": 0, "responses": []}

    class FakeClient:
        is_closed = False

        async def get(self, url):
            state["calls"] += 1
            state["url"] = url
            return state["responses"].pop(0)

        async def aclose(self):
            FakeClient.is_closed = True

    async def _client():
        return FakeClient()

    monkeypatch.setattr(instance, "_get_client", _client)
    return instance, state


def test_get_retries_then_succeeds(client_holder):
    instance, state = client_holder
    instance.cfg.request_retry = 1
    state["responses"] = [_Resp(exc=RuntimeError("net")), _Resp({"ok": 1})]
    assert asyncio.run(instance._get("http://x")) == {"ok": 1}
    assert state["calls"] == 2


def test_get_raises_after_all_attempts(client_holder):
    instance, state = client_holder
    instance.cfg.request_retry = 0
    state["responses"] = [_Resp(exc=RuntimeError("net"))]
    with pytest.raises(RuntimeError, match="net"):
        asyncio.run(instance._get("http://x"))


def test_get_binary_returns_content(client_holder):
    instance, state = client_holder
    state["responses"] = [_Resp(content=b"bytes")]
    assert asyncio.run(instance._get("http://x", binary=True)) == b"bytes"


def test_debug_logs_request(client_holder):
    instance, state = client_holder
    instance.cfg.debug = True
    seen = []
    # 入参顺序是 (url)：内部调用写作 self.logger.info(f"...")，单参最稳
    instance.logger = types.SimpleNamespace(info=seen.append)
    state["responses"] = [_Resp({"ok": 1})]
    asyncio.run(instance._get("http://x"))
    assert seen and "GET http://x" in seen[0]


def test_song_url_walks_down_the_bitrate_ladder(client_holder):
    instance, state = client_holder
    instance.cfg.br = 740
    state["responses"] = [
        _Resp({"url": ""}),  # 第一档没直链
        _Resp({"data": {"url": " http://a.mp3 "}}),  # 第二档命中，且去掉空白
    ]
    url, br = asyncio.run(instance.song_url("sid"))
    assert (url, br) == ("http://a.mp3", 320)
    assert state["calls"] == 2


def test_song_url_returns_none_when_all_levels_fail(client_holder):
    instance, state = client_holder
    instance.cfg.br = 320
    state["responses"] = [_Resp(exc=RuntimeError("x"))] * 3
    assert asyncio.run(instance.song_url("sid")) == (None, None)


def test_song_url_ignores_non_string_url(core):
    api = core("api")
    assert api.MusicApi._get_url_field({"data": {"url": 123}}) is None
    assert api.MusicApi._get_url_field({"url": "  "}) is None


def test_search_passes_paging_params(client_holder):
    instance, state = client_holder
    instance.cfg.source = "kuwo"
    instance.cfg.search_count = 5
    state["responses"] = [_Resp({"data": [{"id": "1", "name": "歌"}]})]
    items = asyncio.run(instance.search("晴天", 2))
    assert [i.name for i in items] == ["歌"]
    url = state["url"]
    assert "types=search" in url and "name=%E6%99%B4%E5%A4%A9" in url
    assert "pages=2" in url and "count=5" in url and "source=kuwo" in url


def test_download_returns_bytes(client_holder):
    instance, state = client_holder
    state["responses"] = [_Resp(content=b"AUDIO")]
    assert asyncio.run(instance.download("http://cdn/x.mp3")) == b"AUDIO"


def test_close_is_idempotent(core, config):
    api = core("api")
    instance = api.MusicApi(config)

    class FakeClient:
        def __init__(self):
            self.is_closed = False
            self.closed = 0

        async def aclose(self):
            self.closed += 1
            self.is_closed = True

    instance._client = FakeClient()
    asyncio.run(instance.close())
    asyncio.run(instance.close())
    assert instance._client.closed == 1


def test_get_client_rebuilds_after_close(core, config, monkeypatch):
    """客户端被关掉后要能自愈重建，而不是拿着 is_closed 的实例继续用。"""
    api = core("api")
    instance = api.MusicApi(config)
    built = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.is_closed = False
            built.append(self)

    monkeypatch.setattr(api.httpx, "AsyncClient", FakeClient)

    async def _go():
        first = await instance._get_client()
        assert await instance._get_client() is first  # 复用
        first.is_closed = True
        second = await instance._get_client()
        return first, second

    first, second = asyncio.run(_go())
    assert second is not first
    assert len(built) == 2
    client = built[0]
    assert client.kwargs["timeout"] == config.request_timeout_ms / 1000
    assert client.kwargs["follow_redirects"] is True
    assert client.kwargs["headers"]["user-agent"] == config.user_agent


def test_song_url_debug_logs_failed_level(client_holder):
    instance, state = client_holder
    instance.cfg.br = 128
    instance.cfg.debug = True
    seen = []
    instance.logger = types.SimpleNamespace(warning=seen.append)
    state["responses"] = [_Resp(exc=RuntimeError("net"))]
    assert asyncio.run(instance.song_url("sid")) == (None, None)
    assert seen and "br=128" in seen[0]
