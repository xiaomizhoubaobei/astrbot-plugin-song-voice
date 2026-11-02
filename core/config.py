"""插件配置项定义与默认值。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

SOURCE_LABELS = {
    "netease": "网易云",
    "tencent": "QQ音乐",
    "kugou": "酷狗",
    "kuwo": "酷我",
    "migu": "咪咕",
    "ximalaya": "喜马拉雅",
    "apple": "Apple Music",
    "spotify": "Spotify",
    "ytmusic": "YouTube Music",
    "tidal": "Tidal",
    "qobuz": "Qobuz",
    "joox": "JOOX",
    "deezer": "Deezer",
}


# 码率降级顺序：优先请求配置值，失败时逐级下调
def br_fallback(br: int) -> List[int]:
    ladder = [999, 740, 320, 192, 128]
    if br not in ladder:
        return [128]
    return ladder[ladder.index(br) :]


@dataclass
class PluginConfig:
    # 基础
    command: str = "点歌"
    alias: List[str] = field(default_factory=lambda: ["听歌", "music"])
    api_base: str = "https://music-api.gdstudio.xyz/api.php"

    # 文案
    generation_tip: str = "生成语音中…"
    prompt_timeout_sec: int = 45
    prompt_timeout: str = "输入超时，已取消点歌。"
    exit_prompt: str = "已退出歌曲选择。"
    invalid_number: str = "序号输入错误，已退出歌曲选择。"
    duration_exceeded: str = "歌曲时长超出限制，已取消发送。"
    get_song_failed: str = "获取歌曲失败，请稍后再试。"
    empty_keyword: str = "请输入关键词。"
    empty_result: str = "没有搜索到结果。"
    send_failed: str = (
        "获取/发送失败：\n"
        "1) 320k 以上常返回 wma，建议把码率改为 192/128；\n"
        "2) 或开启【强制转码】，走下载 → ffmpeg → 语音发送。"
    )

    # 歌单
    search_count: int = 20
    next_page_cmd: str = "下一页"
    prev_page_cmd: str = "上一页"
    exit_cmds: List[str] = field(default_factory=lambda: ["0", "不听了"])
    show_exit_hint: bool = True
    allow_group_select: bool = False
    max_song_duration_min: int = 30

    # 请求
    source: str = "netease"
    br: int = 999
    request_timeout_ms: int = 15000
    request_retry: int = 1
    user_agent: str = "astrbot-plugin-song-voice/1.0"

    # 发送
    force_transcode: bool = False
    transcode_format: str = "aac"  # wav / aac / silk(回退 wav)
    ffmpeg_bin: str = "ffmpeg"
    ffmpeg_timeout_ms: int = 20000
    check_ffmpeg_on_start: bool = True
    record_path: str = "record"

    # 撤回
    recall_generation_tip: bool = True
    recall_song_list: bool = True
    tip_recall_sec: int = 10
    menu_recall_sec: int = 60
    recall_only_after_success: bool = True
    keep_menu_if_send_failed: bool = True

    debug: bool = False

    # 配置项中文名 → 字段名（_conf_schema.json 使用中文键，便于用户在面板中阅读）
    ALIASES = {
        "点歌指令": "command",
        "指令别名": "alias",
        "API 地址": "api_base",
        "音源": "source",
        "音质码率": "br",
        "歌单数量": "search_count",
        "下一页指令": "next_page_cmd",
        "上一页指令": "prev_page_cmd",
        "退出指令": "exit_cmds",
        "展示退出提示": "show_exit_hint",
        "允许群友代选": "allow_group_select",
        "最长时长(分钟)": "max_song_duration_min",
        "等待序号超时(秒)": "prompt_timeout_sec",
        "强制转码": "force_transcode",
        "转码格式": "transcode_format",
        "ffmpeg 路径": "ffmpeg_bin",
        "ffmpeg 超时(毫秒)": "ffmpeg_timeout_ms",
        "启动时检测 ffmpeg": "check_ffmpeg_on_start",
        "语音保存目录": "record_path",
        "请求超时(毫秒)": "request_timeout_ms",
        "请求重试次数": "request_retry",
        "撤回生成提示": "recall_generation_tip",
        "撤回歌单": "recall_song_list",
        "提示撤回秒数": "tip_recall_sec",
        "歌单撤回秒数": "menu_recall_sec",
        "仅成功后撤回": "recall_only_after_success",
        "发送失败保留歌单": "keep_menu_if_send_failed",
        "调试日志": "debug",
        "文案-生成中": "generation_tip",
        "文案-超时": "prompt_timeout",
        "文案-退出": "exit_prompt",
        "文案-序号错误": "invalid_number",
        "文案-时长超限": "duration_exceeded",
        "文案-获取失败": "get_song_failed",
        "文案-发送失败": "send_failed",
    }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any] | None) -> "PluginConfig":
        cfg = cls()
        if not raw:
            return cfg
        for key, value in raw.items():
            key = cls.ALIASES.get(key, key)
            if not hasattr(cfg, key) or value is None:
                continue
            current = getattr(cfg, key)
            try:
                if isinstance(current, bool):
                    setattr(cfg, key, bool(value))
                elif isinstance(current, int):
                    setattr(cfg, key, int(value))
                elif isinstance(current, list):
                    if isinstance(value, str):
                        items = [v.strip() for v in value.replace("，", ",").split(",")]
                        setattr(cfg, key, [v for v in items if v])
                    elif isinstance(value, list):
                        setattr(
                            cfg, key, [str(v).strip() for v in value if str(v).strip()]
                        )
                else:
                    setattr(cfg, key, str(value))
            except (TypeError, ValueError):
                continue
        return cfg

    @property
    def source_label(self) -> str:
        return SOURCE_LABELS.get(self.source, self.source)
