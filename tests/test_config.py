"""配置解析：面板中文键 → 字段名、类型收敛、非法值兜底。"""

from __future__ import annotations

import pytest


def test_defaults_are_usable(core):
    cfg = core("config").PluginConfig()
    assert cfg.command == "点歌"
    assert "听歌" in cfg.alias
    assert cfg.br == 999
    assert cfg.source_label == "网易云"


def test_from_dict_none_returns_defaults(core):
    config_mod = core("config")
    assert config_mod.PluginConfig.from_dict(None) == config_mod.PluginConfig()


def test_chinese_keys_are_mapped(core):
    cfg = core("config").PluginConfig.from_dict(
        {"点歌指令": "来一首", "音源": "kuwo", "音质码率": "320"}
    )
    assert cfg.command == "来一首"
    assert cfg.source == "kuwo"
    # 面板里数字可能以字符串下发，必须收敛成 int
    assert cfg.br == 320


def test_list_fields_accept_string_and_list(core):
    config_mod = core("config")
    from_str = config_mod.PluginConfig.from_dict({"退出指令": "0, 不听了，退"})
    assert from_str.exit_cmds == ["0", "不听了", "退"]
    from_list = config_mod.PluginConfig.from_dict({"指令别名": ["点歌", " ", "music"]})
    assert from_list.alias == ["点歌", "music"]


def test_bool_field_follows_python_truthiness(core):
    config_mod = core("config")
    assert (
        config_mod.PluginConfig.from_dict({"强制转码": "false"}).force_transcode is True
    )
    assert config_mod.PluginConfig.from_dict({"强制转码": ""}).force_transcode is False


def test_unknown_keys_and_none_values_are_ignored(core):
    cfg = core("config").PluginConfig.from_dict({"不存在的键": 1, "点歌指令": None})
    assert cfg.command == "点歌"
    assert not hasattr(cfg, "不存在的键")


def test_invalid_int_falls_back_to_default(core):
    cfg = core("config").PluginConfig.from_dict({"音质码率": "很高"})
    assert cfg.br == 999


@pytest.mark.parametrize(
    ("br", "expected"),
    [
        (999, [999, 740, 320, 192, 128]),
        (320, [320, 192, 128]),
        (192, [192, 128]),
        (128, [128]),
        (256, [128]),  # 不在阶梯上的码率不猜，直接取最低档
    ],
)
def test_br_fallback_ladder(core, br, expected):
    assert core("config").br_fallback(br) == expected


def test_source_label_falls_back_to_raw_value(core):
    cfg = core("config").PluginConfig.from_dict({"音源": "unknown-src"})
    assert cfg.source_label == "unknown-src"
