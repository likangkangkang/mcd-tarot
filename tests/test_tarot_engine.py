"""麦麦塔罗牌 · 单元测试（纯标准库，无第三方依赖）。

运行: python tests/test_tarot_engine.py
"""
import os
import sys
import traceback

# 让 tests/ 能 import 到项目根目录的模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tarot_deck
import tarot_engine
import mcp_client


def test_deck_size():
    assert tarot_deck.deck_size() == 78
    majors = [c for c in tarot_deck.ALL_CARDS if c["arcana"] == "major"]
    minors = [c for c in tarot_deck.ALL_CARDS if c["arcana"] == "minor"]
    assert len(majors) == 22, f"大阿卡纳应为22，实际{len(majors)}"
    assert len(minors) == 56, f"小阿卡纳应为56，实际{len(minors)}"


def test_minor_emotion_no_placeholder():
    """小阿卡纳情绪寄语不应残留 {cat}/{_tone} 占位符。"""
    for c in tarot_deck.ALL_CARDS:
        for key in ("emotion_up", "emotion_rev"):
            msg = c[key]
            assert "{" not in msg and "}" not in msg, f"{c['name_cn']} 残留占位符: {msg}"


def test_all_cards_have_required_fields():
    for c in tarot_deck.ALL_CARDS:
        for f in ("id", "name_cn", "name_en", "arcana", "upright", "reversed",
                  "mcd_keywords", "emotion_up", "emotion_rev"):
            assert f in c and c[f] is not None, f"{c.get('name_cn')} 缺字段 {f}"


def test_deterministic_same_day():
    d = "2026-10-16"
    a = tarot_engine.draw("trinity", d)
    b = tarot_engine.draw("trinity", d)
    assert [x[0]["id"] for x in a] == [x[0]["id"] for x in b]
    assert [x[1] for x in a] == [x[1] for x in b]


def test_different_date_different_draw():
    a = tarot_engine.draw("today", "2026-10-16")[0][0]["id"]
    b = tarot_engine.draw("today", "2026-10-17")[0][0]["id"]
    # 不强制必须不同，但至少调用不报错且类型正确
    assert isinstance(a, int) and isinstance(b, int)


def test_orientation_valid():
    for _, ori, _ in tarot_engine.draw("timeline", "2026-10-16"):
        assert ori in ("up", "rev")


def test_unknown_spread_raises():
    try:
        tarot_engine.draw("nope", "2026-10-16")
        assert False, "未知牌阵应抛 ValueError"
    except ValueError:
        pass


def test_menu_fallback_without_token():
    menu = mcp_client.get_menu(None)
    assert menu is mcp_client.FALLBACK_MENU
    assert len(menu) > 0


def test_resolve_item_matches_keyword():
    menu = mcp_client.get_menu(None)
    fool = tarot_deck.find_card("愚者")
    item = mcp_client.resolve_item(fool, menu)
    assert "麦辣" in item["name"], f"愚者应映射到辣味，实际 {item['name']}"
    # 价格应来自静态菜单
    assert item["price"] is not None


def test_do_reading_markdown_offline():
    r = tarot_engine.do_reading("today", "2026-10-16", "累", token=None)
    assert r["menu_source"] == "fallback"
    assert "麦麦指引" in r["markdown"]
    assert "给你的话" in r["markdown"]
    assert r["cards"][0]["food"], "应给出具体食物"
    assert r["spread"] == "today"


def test_do_reading_all_spreads():
    for spread in ("today", "trinity", "timeline"):
        r = tarot_engine.do_reading(spread, "2026-10-16", token=None)
        assert r["cards"], f"{spread} 应至少抽到一张"
        assert len(r["cards"]) == {"today": 1, "trinity": 3, "timeline": 3}[spread]


if __name__ == "__main__":
    mod = sys.modules[__name__]
    fns = [getattr(mod, n) for n in dir(mod) if n.startswith("test_")]
    ok = 0
    for f in fns:
        try:
            f()
            ok += 1
            print(f"✓ {f.__name__}")
        except Exception:
            print(f"✗ {f.__name__}")
            traceback.print_exc()
    print(f"\nPASSED {ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
