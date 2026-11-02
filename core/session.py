"""会话状态与歌单渲染（对应 koishi 版的 pending 机制）。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Hashable, List, Optional

from .config import PluginConfig
from .models import SearchItem


@dataclass
class PendingState:
    keyword: str
    page: int
    items: List[SearchItem]
    created_at: float
    user_id: str = ""
    group_id: str = ""
    menu_message_ids: List[Any] = field(default_factory=list)

    def expired(self, seconds: int) -> bool:
        return time.time() - self.created_at >= seconds


class PendingStore:
    def __init__(self):
        self._data: Dict[Hashable, PendingState] = {}

    def key(self, cfg: PluginConfig, user_id: str, group_id: str) -> Hashable:
        if cfg.allow_group_select:
            return group_id or user_id
        return (user_id, group_id)

    def get(self, key: Hashable) -> Optional[PendingState]:
        return self._data.get(key)

    def set(self, key: Hashable, state: PendingState) -> None:
        state.created_at = time.time()
        self._data[key] = state

    def pop(self, key: Hashable) -> Optional[PendingState]:
        return self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()


def is_exit_input(text: str, cfg: PluginConfig) -> bool:
    value = text.strip()
    return bool(value) and value in [c.strip() for c in cfg.exit_cmds if c.strip()]


def render_menu(cfg: PluginConfig, keyword: str, page: int, items: List[SearchItem]) -> str:
    lines = [f"🎵 搜索：{keyword}（第 {page} 页）", ""]
    for idx, item in enumerate(items[: cfg.search_count], start=1):
        lines.append(item.menu_line(idx))
    lines.append("")
    lines.append(f"指令：{cfg.prev_page_cmd} / {cfg.next_page_cmd}")
    if cfg.show_exit_hint:
        lines.append(f"退出：{' / '.join(cfg.exit_cmds)}")
    lines.append("回复序号即可点歌。")
    return "\n".join(lines)


async def send_audio_record(ctx: Any, origin: str, path: str) -> None:
    """统一走 Record 语音组件；老版本无组件时降级为文件路径消息。"""
    try:
        from astrbot.api.message_components import Record
    except ImportError:  # pragma: no cover
        await ctx.send_message(origin, [path])
        return
    await ctx.send_message(origin, [Record(file=path)])
