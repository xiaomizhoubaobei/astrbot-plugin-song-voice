"""ffmpeg 转码与音频发送格式选择。"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Optional

WMA_HINT = (".wma",)


def is_likely_wma(url: Optional[str]) -> bool:
    if not url:
        return False
    path = url.split("?", 1)[0].lower()
    return path.endswith(WMA_HINT)


def ffmpeg_available(binary: str) -> bool:
    return shutil.which(binary) is not None


async def _run_ffmpeg(binary: str, args: list[str], data: bytes, timeout_ms: int) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        binary,
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(data), timeout=max(3, timeout_ms // 1000) + 30
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("ffmpeg 超时")
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode("utf-8", "ignore").strip() or f"ffmpeg exit {proc.returncode}")
    if not stdout:
        raise RuntimeError("ffmpeg 输出为空")
    return stdout


async def to_wav(binary: str, data: bytes, timeout_ms: int) -> bytes:
    """输出 24kHz / 单声道 / s16 wav，兼容大多数语音接口。"""
    args = [
        "-hide_banner", "-loglevel", "error",
        "-i", "pipe:0",
        "-ac", "1", "-ar", "24000",
        "-f", "wav", "pipe:1",
    ]
    return await _run_ffmpeg(binary, args, data, timeout_ms)


async def to_aac(binary: str, data: bytes, timeout_ms: int, bitrate: str = "128k") -> bytes:
    args = [
        "-hide_banner", "-loglevel", "error",
        "-i", "pipe:0",
        "-vn", "-c:a", "aac", "-b:a", bitrate,
        "-f", "adts", "pipe:1",
    ]
    return await _run_ffmpeg(binary, args, data, timeout_ms)


async def transcode(binary: str, data: bytes, fmt: str, timeout_ms: int) -> tuple[bytes, str, str]:
    """返回 (音频字节, 文件名, mime)。silk 无编码器时回退 wav。"""
    fmt = (fmt or "aac").lower()
    if fmt == "aac":
        return await to_aac(binary, data, timeout_ms), "song.aac", "audio/aac"
    if fmt == "silk":
        # 纯 Python 环境无 silk 编码器，统一回退 wav，仍可被多数适配器播放
        pass
    wav = await to_wav(binary, data, timeout_ms)
    return wav, "song.wav", "audio/wav"


def write_temp(path_dir: str, filename: str, data: bytes) -> Path:
    directory = Path(path_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    target.write_bytes(data)
    return target
