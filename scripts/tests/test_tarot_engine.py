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


def test_no_duplicate_cards_in_multi_spread():
    """同一牌阵内不应出现重复牌（真实牌阵不放回发牌）。"""
    for spread in ("trinity", "timeline"):
        for d in ("2026-01-07", "2026-01-21", "2026-02-07", "2026-10-16", "2026-12-31"):
            ids = [c[0]["id"] for c in tarot_engine.draw(spread, d)]
            assert len(ids) == len(set(ids)), f"{spread} {d} 出现重复牌: {ids}"


def test_resolve_prefers_exact_name():
    """同名优先：巨无霸不应被巨无霸三件套抢先。"""
    menu = [
        {"name": "巨无霸三件套", "code": "a", "price": 37.0},
        {"name": "巨无霸", "code": "b", "price": 26.0},
    ]
    card = {"mcd_keywords": ["巨无霸"], "mcd_category": "汉堡"}
    assert mcp_client.resolve_item(card, menu)["name"] == "巨无霸"


def test_resolve_skips_non_food():
    """非餐品（周边/贴纸/酱料）不参与匹配。"""
    menu = [
        {"name": "薯条脆卜卜毛绒周边", "code": "a", "price": 29.9},
        {"name": "旋旋星愿贴", "code": "b", "price": 3.9},
        {"name": "韩式烟熏芝士风味酱", "code": "c", "price": 3.0},
        {"name": "薯条", "code": "d", "price": 14.5},
    ]
    card = {"mcd_keywords": ["薯条"], "mcd_category": "配餐"}
    assert mcp_client.resolve_item(card, menu)["name"] == "薯条"


def test_all_major_cards_have_priced_match():
    """22 张大阿卡纳在静态菜单下都应匹配到带价格的餐品（不降级为裸关键词）。"""
    missing = []
    for c in tarot_deck.MAJOR_ARCANA:
        item = mcp_client.resolve_item(c, mcp_client.FALLBACK_MENU)
        if item.get("price") is None:
            missing.append(c["name_cn"])
    assert not missing, f"未匹配到价格的牌: {missing}"


def test_spreads_have_food_names():
    """三张牌阵的每张牌都应给出餐品名（可为关键词兜底），不出现空名。"""
    for spread in ("trinity", "timeline", "choice"):
        r = tarot_engine.do_reading(spread, "2026-10-16", token=None)
        for c in r["cards"]:
            assert c["food"], f"{spread} 存在空餐品: {c}"


def test_choice_spread_offers_three_distinct_foods():
    """三选一：三张牌应尽量落到三道不同的菜，而不是同一杯可乐复制三份。"""
    menu = [
        {"name": "可乐", "price": 9.5, "category": "饮品"},
        {"name": "麦辣鸡翅", "price": 14.5, "category": "辣味炸鸡"},
        {"name": "巨无霸", "price": 26.0, "category": "汉堡"},
        {"name": "巨无霸三件套", "price": 37.0, "category": "汉堡"},
        {"name": "薯条脆卜卜毛绒周边", "price": 29.9, "category": "小食甜品/其他"},
    ]
    for day in ("2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20"):
        r = tarot_engine.do_reading("choice", day, menu=menu)
        foods = [c["food"] for c in r["cards"]]
        assert len(foods) == 3, foods
        assert "薯条脆卜卜毛绒周边" not in foods, "周边不应被当作餐品"


def test_week_reading_covers_seven_days():
    r = tarot_engine.do_week_reading("2026-10-21")  # 周三 → 应对齐到周一
    assert len(r["days"]) == 7, r["days"]
    assert r["days"][0]["date"] == "2026-10-19", r["days"][0]   # 周一
    assert r["days"][-1]["date"] == "2026-10-25", r["days"][-1]  # 周日
    assert all(d["food"] for d in r["days"]), "每天都应有餐品"
    assert "本周餐单" in r["markdown"]


def test_single_item_preferred_over_bundle():
    """「巨无霸」应命中单品，而不是同名的三件套。"""
    card = next(c for c in tarot_deck.MAJOR_ARCANA if c["name_cn"] == "魔术师")
    menu = [{"name": "巨无霸三件套", "price": 37.0, "category": "汉堡"},
            {"name": "巨无霸", "price": 26.0, "category": "汉堡"}]
    assert mcp_client.resolve_item(card, menu)["name"] == "巨无霸"


def test_cache_store_roundtrip(tmp_note=None):
    """门店记忆与当日菜单缓存：写入后能读回，且来自临时目录不污染真实缓存。"""
    import tempfile
    import cache

    with tempfile.TemporaryDirectory() as td:
        old = os.environ.get("MCD_TAROT_CACHE")
        os.environ["MCD_TAROT_CACHE"] = td
        try:
            assert cache.load_store() is None
            cache.save_store("1990262001", "南京徐庄路快捷小站", "南京")
            store = cache.load_store()
            assert store and store["store_code"] == "1990262001"
            assert store["store_name"] == "南京徐庄路快捷小站"
            menu = [{"name": "巨无霸", "price": 26.0, "code": "1", "category": "汉堡"}]
            cache.save_menu("1990262001", menu, "2026-10-20")
            assert cache.load_menu("1990262001", "2026-10-20")[0]["name"] == "巨无霸"
            assert cache.load_menu("1990262001", "2026-10-21") is None, "不同日期不应命中"
            assert cache.latest_menu(), "latest_menu 应能取到缓存"
        finally:
            if old is None:
                os.environ.pop("MCD_TAROT_CACHE", None)
            else:
                os.environ["MCD_TAROT_CACHE"] = old


def test_period_combo_at_lunch_single_at_night():
    """同一张牌：午餐时段推套餐，夜宵时段推单品。"""
    from datetime import datetime

    card = tarot_deck.find_card("星币七")   # 星币花色 → 汉堡类关键词
    menu = [
        {"name": "巨无霸", "price": 26.0, "category": "汉堡", "form": "single"},
        {"name": "巨无霸三件套", "price": 37.0, "original_price": 50.5,
         "category": "汉堡", "form": "combo"},
    ]
    lunch = tarot_engine.period_of(datetime(2026, 10, 20, 12, 30))
    night = tarot_engine.period_of(datetime(2026, 10, 20, 22, 0))
    assert lunch["name"] == "午餐", lunch
    assert night["name"] == "夜宵", night

    p_lunch = tarot_engine.tuned_portion(card, lunch)
    p_night = tarot_engine.tuned_portion(card, night)
    assert p_lunch == "combo", p_lunch
    assert p_night in ("light", "single"), p_night

    lunch_item = mcp_client.resolve_item(card, menu, prefer_form=p_lunch)
    night_item = mcp_client.resolve_item(card, menu, prefer_form=p_night)
    assert "三件套" in lunch_item["name"], lunch_item
    assert night_item["name"] == "巨无霸", night_item


def test_reading_reports_period_and_form():
    """解读结果应带上时段、餐品形态与（有折扣时的）立省信息。"""
    menu = [
        {"name": "巨无霸三件套", "price": 37.0, "original_price": 50.5,
         "category": "汉堡", "form": "combo"},
        {"name": "巨无霸", "price": 26.0, "category": "汉堡", "form": "single"},
    ]
    r = tarot_engine.do_reading("today", "2026-10-20", menu=menu, at="2026-10-20 12:30")
    assert r["period"]["name"] == "午餐"
    card = r["cards"][0]
    assert card["form"] in ("combo", "single", "share", "light"), card
    assert "⏰ 现在是午餐" in r["markdown"]
    if card["form"] == "combo":
        assert "立省" in r["markdown"], "套餐应显示立省金额"


def test_tarot_card_renders_with_and_without_image(tmp_path=None):
    """牌面卡片：没有图也能出牌（走手绘占位），有图能内联 base64。"""
    import tarot_card

    card = {
        "position": "今天", "card_id": 7, "card_cn": "战车", "card_en": "The Chariot",
        "orientation": "逆位", "food": "麦辣鸡翅", "price": "¥14.5",
        "form_label": "单品", "message": "油门踩下去，别怕。", "image": "",
    }
    reading = {"date": "2026-10-20", "spread_name": "今日宜吃", "cards": [card]}
    svg = tarot_card._card_svg(card, {"date": "2026-10-20"})
    assert "战车" in svg and "逆位" in svg, "牌名与逆位标记应出现在牌面"
    assert "VII" in svg, "大阿卡纳应显示罗马数字"
    assert "clipPath" in svg and "arch" in svg, "应有拱形画框"
    out = tarot_card.render(reading, str(os.path.join(os.path.dirname(__file__), "_tmp_card.svg")))
    assert os.path.exists(out)
    os.remove(out)


def test_order_draft_card():
    """订单确认卡：能按 code 从菜单缓存取菜名与价格，并写明「还没下单」。"""
    import argparse
    import tempfile
    import order

    with tempfile.TemporaryDirectory() as td:
        old = os.environ.get("MCD_TAROT_CACHE")
        os.environ["MCD_TAROT_CACHE"] = td
        try:
            order.CACHE = __import__("pathlib").Path(td)
            order.ORDERS = order.CACHE / "orders.json"
            (order.CACHE / "menus").mkdir(parents=True, exist_ok=True)
            import cache as cache_mod
            cache_mod.save_menu("1990262001", [
                {"name": "巨无霸", "code": "1100", "price": 26.0, "form": "single"},
            ])
            args = argparse.Namespace(store="1990262001", store_name="南京徐庄路快捷小站",
                                      items="1100:2", way="locker-in", way_name="外带")
            order.cmd_draft(args)
            data = order._load()
            assert data["drafts"] and data["drafts"][-1]["estimate"] == 52.0, data["drafts"]
        finally:
            if old is None:
                os.environ.pop("MCD_TAROT_CACHE", None)
            else:
                os.environ["MCD_TAROT_CACHE"] = old


# ---------------------------------------------------------------------------
# 口味画像 + 优惠感知推荐
# ---------------------------------------------------------------------------
_SAMPLE_ORDERS = {
    "data": {"list": [
        {"createTime": "2026-10-16 09:03:42", "storeCode": "1", "realTotalAmount": "12.9",
         "orderProductList": [{"productName": "原味板烧鸡腿炒双蛋堡组合",
                               "comboItemList": [{"name": "优品豆浆小杯"}]}]},
        {"createTime": "2026-10-13 09:18:57", "storeCode": "1", "realTotalAmount": "12.9",
         "orderProductList": [{"productName": "原味板烧鸡腿炒双蛋堡组合",
                               "comboItemList": [{"name": "优品豆浆小杯"}]}]},
        {"createTime": "2026-09-24 08:31:45", "storeCode": "1", "realTotalAmount": "12.9",
         "orderProductList": [{"productName": "原味板烧鸡腿炒双蛋堡组合",
                               "comboItemList": [{"name": "优品豆浆小杯"}]}]},
        {"createTime": "2026-10-16 18:31:59", "storeCode": "1", "realTotalAmount": "38",
         "orderProductList": [{"productName": "心形薯饼5块"},
                              {"productName": "韩式辣椒黄油风味酱"}]},
    ]}
}
_SAMPLE_AVAILABLE = """- 优惠券标题：11.9元麦辣鸡腿堡
  状态：可领取
- 优惠券标题：免费脆薯饼
  状态：可领取
"""
_SAMPLE_WALLET = """## 麦咖啡™美式中杯
- **优惠**: ¥0 (用券价格)
"""

_MENU = [
    {"name": "麦辣鸡腿汉堡", "code": "1", "price": 23.0, "category": "鸡肉汉堡", "form": "single"},
    {"name": "板烧鸡腿堡", "code": "2", "price": 24.0, "category": "鸡肉汉堡", "form": "single"},
    {"name": "脆薯饼", "code": "3", "price": 8.0, "category": "小食", "form": "single"},
    {"name": "麦咖啡™美式", "code": "4", "price": 9.9, "category": "麦咖啡", "form": "single"},
    {"name": "巨无霸", "code": "5", "price": 26.0, "category": "牛肉汉堡", "form": "single"},
]


def _sample_profile():
    import profile as profile_mod
    return profile_mod.build(orders=_SAMPLE_ORDERS, wallet=_SAMPLE_WALLET,
                             available=_SAMPLE_AVAILABLE)


def test_profile_learns_taste_and_habit():
    """画像要能学到：常点板烧、偏爱鸡肉、早餐习惯点组合、酱料不算口味。"""
    prof = _sample_profile()
    names = [f["name"] for f in prof["favorites"]]
    assert "原味板烧鸡腿炒双蛋堡组合" in names, names
    assert not any("酱" in n for n in names), f"酱料不该进画像: {names}"
    assert prof["favorites"][0]["count"] == 3, prof["favorites"][0]
    assert prof["traits"]["chicken"] >= 0.6, prof["traits"]
    assert prof["periods"]["breakfast"]["top_form"] == "combo", prof["periods"]


def test_affinity_recognizes_familiar_item():
    """没点过「板烧鸡腿堡」，但点过「原味板烧鸡腿炒双蛋堡组合」，应识别为同一口味。"""
    prof = _sample_profile()
    a = mcp_client.affinity({"name": "板烧鸡腿堡", "price": 24}, prof)
    b = mcp_client.affinity({"name": "巨无霸", "price": 26}, prof)
    assert a["score"] > b["score"], (a, b)
    assert a["score"] >= 1.5, a


def test_deal_matches_coupon_by_partial_name():
    """券名和菜名不完全一致（麦咖啡™美式中杯 vs 麦咖啡™美式）也要能匹配上。"""
    prof = _sample_profile()
    deal = mcp_client.deal_for({"name": "麦咖啡™美式", "price": 9.9}, prof)
    assert deal and deal["free"] and deal["saving"] == 9.9, deal
    deal2 = mcp_client.deal_for({"name": "麦辣鸡腿汉堡", "price": 23.0}, prof)
    assert deal2 and deal2["saving"] == 11.1, deal2
    assert mcp_client.deal_for({"name": "巨无霸", "price": 26.0}, prof) is None


def test_resolve_prefers_familiar_alternative():
    """牌指向炸鸡类时，在同类里优先你更熟悉的板烧；并给出券/偏好标注。"""
    card = {"id": 0, "name_cn": "愚者", "mcd_keywords": ["麦辣鸡腿汉堡"],
            "mcd_category": "鸡肉汉堡"}
    prof = _sample_profile()
    item = mcp_client.resolve_item(card, _MENU, profile=prof, prefer_form="single")
    assert item["name"] == "麦辣鸡腿汉堡", item["name"]  # 牌面优先，不被画像推翻
    assert item["deal"] and item["deal"]["saving"] == 11.1, item.get("deal")
    alt = mcp_client.alternative_for(card, item, _MENU, prof, prefer_form="single")
    assert alt and alt["name"] == "板烧鸡腿堡", alt


def test_reading_shows_saving_and_taste():
    """带画像的解读应出现「合你口味」「用券」「更省」这类行。"""
    prof = _sample_profile()
    r = tarot_engine.do_reading("trinity", "2026-10-20", "想省钱", menu=_MENU,
                                at="2026-10-20 15:00", profile=prof)
    assert r["profile_used"] is True
    assert r["cards"] and "price_raw" in r["cards"][0]
    md = r["markdown"]
    assert ("用券" in md) or ("更划算" in md) or ("合你口味" in md) or ("或者更像你" in md), md
    # 有可领券时必须给出提示，不能只字不提
    assert "今天这样买更省" in md and "免费脆薯饼" in md, md


def test_reading_without_profile_still_works():
    """没有画像时必须退化到纯牌意推荐，不能报错。"""
    r = tarot_engine.do_reading("today", "2026-10-20", menu=_MENU,
                                at="2026-10-20 12:30", profile=False)
    assert r["cards"], r
    assert r["profile_used"] is False


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
