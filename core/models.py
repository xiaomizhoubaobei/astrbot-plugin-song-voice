"""搜索结果的统一数据模型与字段兼容。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


def _first(*values: Any) -> Optional[Any]:
    for v in values:
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v
    return None


def pick_duration_sec(raw: dict) -> Optional[int]:
    value = _first(raw.get("duration"), raw.get("time"), raw.get("interval"))
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    # 部分源返回毫秒
    if seconds > 10000:
        seconds = seconds / 1000
    return int(seconds)


def fmt_duration(sec: Optional[int]) -> str:
    if not sec or sec <= 0:
        return ""
    return f"{sec // 60}:{sec % 60:02d}"


@dataclass
class SearchItem:
    song_id: Optional[str]
    name: str
    artist: str
    duration: Optional[int]

    @classmethod
    def from_raw(cls, raw: dict) -> "SearchItem":
        song_id = _first(raw.get("id"), raw.get("songid"), raw.get("song_id"))
        name = _first(raw.get("name"), raw.get("title"), raw.get("song"))
        artist = _first(
            raw.get("artist"),
            raw.get("author"),
            raw.get("singer"),
            raw.get("artists"),
        )
        if isinstance(artist, list):
            artist = " / ".join(
                str(a.get("name", a)) if isinstance(a, dict) else str(a) for a in artist
            )
        return cls(
            song_id=str(song_id).strip() if song_id is not None else None,
            name=str(name) if name else "未知歌曲",
            artist=str(artist).strip() if artist else "",
            duration=pick_duration_sec(raw),
        )

    def menu_line(self, index: int) -> str:
        text = f"{index}. {self.name}"
        if self.artist:
            text += f" - {self.artist}"
        dur = fmt_duration(self.duration)
        if dur:
            text += f"  [{dur}]"
        return text
