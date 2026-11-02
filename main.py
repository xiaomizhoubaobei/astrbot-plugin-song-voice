"""点歌语音插件入口（AstrBot）。

搜索 → 歌单 → 翻页 → 序号点播 → 可选 ffmpeg 转码发送语音。
数据来源：GD 音乐台 API。
"""

from __future__ import annotations

import time
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .core.api import MusicApi
from .core.audio import ffmpeg_available, is_likely_wma, transcode, write_temp
from .core.config import PluginConfig
from .core.session import (
    PendingState,
    PendingStore,
    is_exit_input,
    render_menu,
    send_audio_record,
)

try:  # AstrBot 4.x 的消息组件
    from astrbot.api.message_components import Plain
except ImportError:  # pragma: no cover - 兼容旧版
    Plain = None  # type: ignore


@register(
    "astrbot_plugin_song_voice",
    "qixiaoxin",
    "音乐聚合点播语音插件：搜索歌曲、翻页选择、序号点播，可选 ffmpeg 转码发送语音。",
    "1.0.0",
)
class SongVoicePlugin(Star):
    def __init__(self, context: Context, config: Any = None):
        super().__init__(context)
        data = config if isinstance(config, dict) else getattr(config, "__dict__", None)
        self.config_obj = PluginConfig.from_dict(data if isinstance(data, dict) else None)
        self.api = MusicApi(self.config_obj, logger)
        self.pending = PendingStore()

        if self.config_obj.check_ffmpeg_on_start:
            if ffmpeg_available(self.config_obj.ffmpeg_bin):
                logger.info(f"[song-voice] ffmpeg 可用：{self.config_obj.ffmpeg_bin}")
            else:
                logger.warning(
                    f"[song-voice] 未找到 ffmpeg（{self.config_obj.ffmpeg_bin}），"
                    "高码率/强制转码场景可能发送失败。"
                )

    # ---------- 事件辅助 ----------

    @staticmethod
    def _who(event: AstrMessageEvent) -> tuple[str, str]:
        user_id = str(getattr(event, "get_sender_id", lambda: "")() or "")
        group_id = str(getattr(event, "get_group_id", lambda: "")() or "")
        return user_id, group_id

    async def _send_audio(self, event: AstrMessageEvent, path: str) -> None:
        await send_audio_record(self.context, event.unified_msg_origin, path)

    # ---------- 核心流程 ----------

    async def _do_search(self, event: AstrMessageEvent, key: Any, keyword: str, page: int):
        """搜索并渲染歌单，返回 (文本, 是否成功)。"""
        try:
            items = await self.api.search(keyword, page)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[song-voice] 搜索失败：{e}")
            return self.config_obj.get_song_failed, False
        if not items:
            return self.config_obj.empty_result, False

        state = self.pending.get(key) or PendingState(
            keyword=keyword, page=page, items=items, created_at=time.time()
        )
        state.keyword, state.page, state.items = keyword, page, items
        self.pending.set(key, state)
        return render_menu(self.config_obj, keyword, page, items), True

    async def _play(self, event: AstrMessageEvent, state_key: Any, index: int):
        """点播第 index 首，逐条产出提示文本。"""
        cfg = self.config_obj
        state = self.pending.get(state_key)
        if state is None:
            yield cfg.get_song_failed
            return
        if index < 1 or index > len(state.items):
            self.pending.pop(state_key)
            yield cfg.invalid_number
            return

        chosen = state.items[index - 1]
        if not chosen.song_id:
            self.pending.pop(state_key)
            yield cfg.get_song_failed
            return

        yield cfg.generation_tip

        try:
            url, br = await self.api.song_url(chosen.song_id)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[song-voice] 取直链异常：{e}")
            url, br = None, None

        if not url:
            self.pending.pop(state_key)
            yield cfg.get_song_failed
            return

        if (
            cfg.max_song_duration_min > 0
            and chosen.duration
            and chosen.duration > cfg.max_song_duration_min * 60
        ):
            self.pending.pop(state_key)
            yield cfg.duration_exceeded
            return

        need_transcode = (
            cfg.force_transcode
            or is_likely_wma(url)
            or (br is not None and br >= 320)
            or not ffmpeg_available(cfg.ffmpeg_bin)
        )

        try:
            if need_transcode and ffmpeg_available(cfg.ffmpeg_bin):
                raw = await self.api.download(url)
                try:
                    data, filename, _mime = await transcode(
                        cfg.ffmpeg_bin, raw, cfg.transcode_format, cfg.ffmpeg_timeout_ms
                    )
                except Exception as e:  # noqa: BLE001 转码失败退 wav
                    logger.warning(f"[song-voice] 转码失败，回退 wav：{e}")
                    from .core.audio import to_wav

                    data = await to_wav(cfg.ffmpeg_bin, raw, cfg.ffmpeg_timeout_ms)
                    filename = "song.wav"
                path = write_temp(cfg.record_path, filename, data)
            else:
                # 无 ffmpeg 或直链可播：下载落盘后按音频文件发送
                raw = await self.api.download(url)
                suffix = ".wma" if is_likely_wma(url) else ".mp3"
                path = write_temp(cfg.record_path, f"song{suffix}", raw)

            await self._send_audio(event, str(path))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[song-voice] 发送失败：{e}")
            if cfg.debug:
                logger.exception(e)
            yield cfg.send_failed
        finally:
            self.pending.pop(state_key)

    # ---------- 消息入口 ----------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        cfg = self.config_obj
        raw = str(event.message_str or "").strip()
        if not raw:
            return

        trigger = {"点歌", cfg.command, *cfg.alias}
        head = raw.split(maxsplit=1)[0]
        is_command = head in trigger

        user_id, group_id = self._who(event)
        key = self.pending.key(cfg, user_id, group_id)
        state = self.pending.get(key)

        # 1) 新点歌
        if is_command:
            keyword = raw[len(head):].strip()
            if not keyword:
                yield event.plain_result(cfg.empty_keyword)
                event.stop_event()
                return
            text, _ok = await self._do_search(event, key, keyword, 1)
            yield event.plain_result(text)
            event.stop_event()
            return

        if state is None:
            return

        # 2) 选择态：超时即作废
        if state.expired(cfg.prompt_timeout_sec):
            self.pending.pop(key)
            yield event.plain_result(cfg.prompt_timeout)
            event.stop_event()
            return

        if is_exit_input(raw, cfg):
            self.pending.pop(key)
            yield event.plain_result(cfg.exit_prompt)
            event.stop_event()
            return

        if raw == cfg.next_page_cmd or raw == cfg.prev_page_cmd:
            page = state.page + (1 if raw == cfg.next_page_cmd else -1)
            page = max(1, page)
            state.page = page
            text, _ok = await self._do_search(event, key, state.keyword, page)
            yield event.plain_result(text)
            event.stop_event()
            return

        # 3) 序号点播
        try:
            index = int(raw)
        except ValueError:
            return
        async for text in self._play(event, key, index):
            yield event.plain_result(text)
        event.stop_event()

    async def terminate(self):
        await self.api.close()
        self.pending.clear()
