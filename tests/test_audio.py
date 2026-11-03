"""转码与发送格式选择：不调真实 ffmpeg，只验决策与失败路径。"""

from __future__ import annotations

import asyncio

import pytest


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://x/a.wma", True),
        ("https://x/a.WMA?sig=1", True),
        ("https://x/a.mp3", False),
        ("https://x/a.mp3?f=.wma", False),
        ("", False),
        (None, False),
    ],
)
def test_is_likely_wma(core, url, expected):
    assert core("audio").is_likely_wma(url) is expected


def test_ffmpeg_available_reads_path(core, monkeypatch):
    audio = core("audio")
    monkeypatch.setattr(audio.shutil, "which", lambda b: "/usr/bin/ffmpeg")
    assert audio.ffmpeg_available("ffmpeg") is True
    monkeypatch.setattr(audio.shutil, "which", lambda b: None)
    assert audio.ffmpeg_available("ffmpeg") is False


def _fake_proc(returncode=0, out=b"", err=b""):
    class Proc:
        def __init__(self):
            self.returncode = returncode

        async def communicate(self, data=None):
            return out, err

        def kill(self):
            self.killed = True

    return Proc()


@pytest.fixture
def fake_exec(core, monkeypatch):
    """把 create_subprocess_exec 换成可编排的假进程，并记录参数。"""
    audio = core("audio")
    calls = {}

    def _install(proc, hang=False):
        async def _exec(binary, *args, **kwargs):
            calls["binary"] = binary
            calls["args"] = args
            if hang:

                async def _never(data=None):
                    await asyncio.sleep(3600)

                proc.communicate = _never
            return proc

        monkeypatch.setattr(audio.asyncio, "create_subprocess_exec", _exec)
        return calls

    return _install


def test_transcode_aac_returns_aac(core, fake_exec):
    audio = core("audio")
    calls = fake_exec(_fake_proc(out=b"AAC"))
    data, name, mime = asyncio.run(audio.transcode("ffmpeg", b"raw", "aac", 1000))
    assert (data, name, mime) == (b"AAC", "song.aac", "audio/aac")
    assert calls["binary"] == "ffmpeg"
    assert "-c:a" in calls["args"] and "128k" in calls["args"]


def test_transcode_silk_falls_back_to_wav(core, fake_exec):
    audio = core("audio")
    fake_exec(_fake_proc(out=b"WAV"))
    data, name, mime = asyncio.run(audio.transcode("ffmpeg", b"raw", "silk", 1000))
    assert (data, name, mime) == (b"WAV", "song.wav", "audio/wav")


@pytest.mark.parametrize(("fmt", "expected"), [("", "song.aac"), ("wav", "song.wav")])
def test_transcode_format_dispatch(core, fake_exec, fmt, expected):
    # 未配置格式时按默认 aac 处理（`(fmt or "aac")`），配置成 wav 才走 wav 分支
    audio = core("audio")
    fake_exec(_fake_proc(out=b"WAV"))
    assert asyncio.run(audio.transcode("ffmpeg", b"", fmt, 1000))[1] == expected


def test_wav_args_are_voice_friendly(core, fake_exec):
    audio = core("audio")
    calls = fake_exec(_fake_proc(out=b"WAV"))
    asyncio.run(audio.to_wav("ffmpeg", b"raw", 1000))
    args = calls["args"]
    assert args[args.index("-ar") + 1] == "24000"
    assert args[args.index("-ac") + 1] == "1"
    assert args[args.index("-f") + 1] == "wav"


def test_empty_output_is_an_error(core, fake_exec):
    audio = core("audio")
    fake_exec(_fake_proc(out=b""))
    with pytest.raises(RuntimeError, match="输出为空"):
        asyncio.run(audio.to_wav("ffmpeg", b"raw", 1000))


def test_nonzero_exit_reports_stderr(core, fake_exec):
    audio = core("audio")
    fake_exec(_fake_proc(returncode=1, err=b"boom"))
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(audio.to_wav("ffmpeg", b"raw", 1000))


def test_timeout_kills_process(core, fake_exec):
    audio = core("audio")
    proc = _fake_proc()
    fake_exec(proc, hang=True)

    async def _short_wait(coro, timeout):
        # 让 wait_for 立刻超时，同时关掉未被消费的协程，避免 "never awaited" 噪音
        coro.close()
        raise asyncio.TimeoutError

    monkey = pytest.MonkeyPatch()
    monkey.setattr(audio.asyncio, "wait_for", _short_wait)
    try:
        with pytest.raises(RuntimeError, match="超时"):
            asyncio.run(audio.to_wav("ffmpeg", b"raw", 1000))
    finally:
        monkey.undo()
    assert proc.killed is True


def test_write_temp_creates_dir_and_file(core, tmp_path):
    audio = core("audio")
    target = audio.write_temp(str(tmp_path / "record"), "song.aac", b"data")
    assert target.read_bytes() == b"data"
    assert target.parent.name == "record"
