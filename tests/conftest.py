"""测试基座：让纯逻辑层在**不装插件运行依赖**的环境下可测。

CI 刻意不安装 requirements.txt（aiohttp / httpx），也没有 astrbot 包：
插件在 AstrBot 里以目录形式加载、本仓库根目录名又不等于包名，
所以这里做两件事：

1. 把仓库根登记为顶层包 ``astrbot_plugin_song_voice``（与 coverage.yml 的
   ``--source`` 口径一致，覆盖率才数得到 core/ 下的文件）；
2. 仅在 ``astrbot`` 缺失时注入最小 stub，足以支撑 ``import main``。
   真实环境装了 astrbot 就不覆盖，避免把 stub 当成被测行为。

httpx 同理：仅用于 ``core.api`` 的类型与客户端构造，测试里全部打桩。
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PKG_NAME = "astrbot_plugin_song_voice"


def _ensure_package_view() -> None:
    """把仓库根映射成顶层包，使 `from .core.config import ...` 可解析。"""
    if PKG_NAME in sys.modules:
        return
    # 本仓库是「平铺式」布局，根目录没有 __init__.py（AstrBot 的目录加载器
    # 直接导入 main.py），所以这里手工造一个命名空间包，不执行任何仓库代码。
    module = types.ModuleType(PKG_NAME)
    module.__path__ = [str(REPO_ROOT)]
    module.__package__ = PKG_NAME
    module.__file__ = str(REPO_ROOT / "__init__.py")
    sys.modules[PKG_NAME] = module


def _install_astrbot_stub() -> None:
    if importlib.util.find_spec("astrbot") is not None:
        return

    # 动态挂在模块上的属性 mypy 不认得，故统一放宽到 Any 再赋值
    astrbot: Any = types.ModuleType("astrbot")
    api: Any = types.ModuleType("astrbot.api")
    api.logger = types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
        exception=lambda *a, **k: None,
        debug=lambda *a, **k: None,
    )

    event: Any = types.ModuleType("astrbot.api.event")

    class AstrMessageEvent:  # noqa: D101 - stub
        pass

    # filter 只要求「装饰器原样返回被装饰函数」
    event.filter = types.SimpleNamespace(
        event_message_type=lambda *a, **k: (lambda fn: fn),
        EventMessageType=types.SimpleNamespace(ALL="all"),
    )
    event.AstrMessageEvent = AstrMessageEvent

    star: Any = types.ModuleType("astrbot.api.star")

    class Context:  # noqa: D101 - stub
        pass

    class Star:  # noqa: D101 - stub
        def __init__(self, context=None):
            self.context = context

    def register(*args, **kwargs):
        return lambda cls: cls

    star.Context = Context
    star.Star = Star
    star.register = register

    components: Any = types.ModuleType("astrbot.api.message_components")

    class Plain:  # noqa: D101 - stub
        def __init__(self, text=""):
            self.text = text

    class Record:  # noqa: D101 - stub
        def __init__(self, file=""):
            self.file = file

    components.Plain = Plain
    components.Record = Record

    for name, mod in {
        "astrbot": astrbot,
        "astrbot.api": api,
        "astrbot.api.event": event,
        "astrbot.api.star": star,
        "astrbot.api.message_components": components,
    }.items():
        sys.modules[name] = mod
    astrbot.api = api
    astrbot.event = event
    astrbot.star = star


def _install_httpx_stub() -> None:
    if importlib.util.find_spec("httpx") is not None:
        return

    httpx: Any = types.ModuleType("httpx")

    class Response:  # noqa: D101 - stub
        pass

    class AsyncClient:  # noqa: D101 - stub
        def __init__(self, *args, **kwargs):
            self.is_closed = False

        async def get(self, *args, **kwargs):  # pragma: no cover - 测试中必被打桩
            raise AssertionError("测试不应发起真实网络请求")

        async def aclose(self):
            self.is_closed = True

    httpx.Response = Response
    httpx.AsyncClient = AsyncClient
    sys.modules["httpx"] = httpx


_ensure_package_view()
_install_astrbot_stub()
_install_httpx_stub()


@pytest.fixture
def core():
    """按需导入 core 子模块的便捷入口。"""

    def _load(name: str):
        return importlib.import_module(f"{PKG_NAME}.core.{name}")

    return _load


@pytest.fixture
def config(core):
    return core("config").PluginConfig()
