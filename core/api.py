"""GD 音乐台 API 请求层，兼容多种返回结构。"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from .config import PluginConfig, br_fallback
from .models import SearchItem


def _parse(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return None


def _unwrap(payload: Any) -> Any:
    """接口偶尔把真实内容塞在 data / result 里。"""
    if isinstance(payload, dict):
        inner = payload.get("data")
        if isinstance(inner, (dict, list)):
            return inner
        inner = payload.get("result")
        if isinstance(inner, (dict, list)):
            return inner
    return payload


def normalize_items(payload: Any) -> List[SearchItem]:
    body = _unwrap(payload)
    if isinstance(body, dict):
        for key in ("data", "result", "songs", "list"):
            if isinstance(body.get(key), list):
                body = body[key]
                break
    if not isinstance(body, list):
        return []
    return [SearchItem.from_raw(i) for i in body if isinstance(i, dict)]


class MusicApi:
    def __init__(self, cfg: PluginConfig, logger=None):
        self.cfg = cfg
        self.logger = logger
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.cfg.request_timeout_ms / 1000,
                headers={
                    "user-agent": self.cfg.user_agent,
                    "accept": "application/json,text/plain,*/*",
                },
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    def _url(self, params: Dict[str, Any]) -> str:
        joiner = "&" if "?" in self.cfg.api_base else "?"
        return f"{self.cfg.api_base}{joiner}{urlencode(params)}"

    async def _get(self, url: str, binary: bool = False):
        client = await self._get_client()
        last_err: Exception | None = None
        for attempt in range(max(0, self.cfg.request_retry) + 1):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                if self.cfg.debug:
                    self.logger.info(f"[song-voice] GET {url} -> {resp.status_code}")
                return resp.content if binary else _parse(resp)
            except Exception as e:  # noqa: BLE001 网络层异常统一重试
                last_err = e
                if attempt < self.cfg.request_retry:
                    await asyncio.sleep(0.25 * (attempt + 1))
        raise last_err if last_err else RuntimeError("request failed")

    async def search(self, keyword: str, page: int = 1) -> List[SearchItem]:
        url = self._url(
            {
                "types": "search",
                "source": self.cfg.source,
                "name": keyword,
                "count": self.cfg.search_count,
                "pages": page,
            }
        )
        payload = await self._get(url)
        return normalize_items(payload)

    async def song_url(self, song_id: str) -> tuple[str | None, int | None]:
        """按码率阶梯取直链，返回 (url, br)。"""
        for br in br_fallback(self.cfg.br):
            url = self._url(
                {"types": "url", "id": song_id, "source": self.cfg.source, "br": br}
            )
            try:
                payload = self._get_url_field(await self._get(url))
            except Exception as e:  # noqa: BLE001
                if self.cfg.debug:
                    self.logger.warning(f"[song-voice] br={br} 请求失败: {e}")
                continue
            if payload:
                return payload, br
        return None, None

    @staticmethod
    def _get_url_field(payload: Any) -> str | None:
        body = _unwrap(payload)
        if isinstance(body, dict):
            url = body.get("url")
            if isinstance(url, str) and url.strip():
                return url.strip()
        return None

    async def download(self, url: str) -> bytes:
        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content
