"""搜索结果归一化：不同音源返回结构千奇百怪，这里守住字段兼容。"""

from __future__ import annotations

import pytest


def test_first_skips_blank_strings(core):
    models = core("models")
    assert models._first(None, "  ", "v") == "v"
    assert models._first(None, "") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"duration": 269}, 269),
        ({"time": "269"}, 269),
        ({"interval": 269000}, 269),  # 毫秒 → 秒
        ({"duration": 0}, None),
        ({"duration": -5}, None),
        ({"duration": "abc"}, None),
        ({}, None),
    ],
)
def test_pick_duration_sec(core, raw, expected):
    assert core("models").pick_duration_sec(raw) == expected


@pytest.mark.parametrize(
    ("sec", "text"),
    [(269, "4:29"), (60, "1:00"), (0, ""), (None, ""), (-1, "")],
)
def test_fmt_duration(core, sec, text):
    assert core("models").fmt_duration(sec) == text


def test_from_raw_normalizes_id_and_artist_list(core):
    item = core("models").SearchItem.from_raw(
        {"songid": 42, "title": "晴天", "artists": [{"name": "周杰伦"}, "杨瑞代"]}
    )
    assert item.song_id == "42"
    assert item.name == "晴天"
    assert item.artist == "周杰伦 / 杨瑞代"


def test_from_raw_gives_unknown_title(core):
    item = core("models").SearchItem.from_raw({"id": "1"})
    assert item.name == "未知歌曲"
    assert item.artist == ""


def test_menu_line_composition(core):
    models = core("models")
    with_artist = models.SearchItem("1", "晴天", "周杰伦", 269)
    assert with_artist.menu_line(3) == "3. 晴天 - 周杰伦  [4:29]"
    bare = models.SearchItem("2", "无名", "", None)
    assert bare.menu_line(1) == "1. 无名"
