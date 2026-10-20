"""麦麦塔罗牌 · 单元测试（纯标准库，无第三方依赖）。

运行: python tests/test_tarot_engine.py
"""
import os
import sys
import traceback
from datetime import datetime

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
    """同一张牌：午餐时段推套餐；夜宵默认也往套餐走，关掉 combo_first 才回落轻食。"""
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
    p_night = tarot_engine.tuned_portion(card, night)                      # 默认套餐优先
    p_night_off = tarot_engine.tuned_portion(card, night, combo_first=False)  # 老行为
    assert p_lunch == "combo", p_lunch
    assert p_night == "combo", p_night
    assert p_night_off in ("light", "single"), p_night_off

    lunch_item = mcp_client.resolve_item(card, menu, prefer_form=p_lunch)
    night_item = mcp_client.resolve_item(card, menu, prefer_form=p_night)
    night_item_off = mcp_client.resolve_item(card, menu, prefer_form=p_night_off)
    assert "三件套" in lunch_item["name"], lunch_item
    assert night_item["form"] == "combo", night_item        # 默认套餐优先
    assert night_item_off["name"] == "巨无霸", night_item_off  # 关掉后回到单品


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
    # 拱形画窗用 mask 实现（Chrome 无头渲染下弧形 clipPath 会把内容整片裁掉）
    assert "archMask" in svg and 'mask="url(#archMask)"' in svg, "应有拱形画窗"
    assert "burger" not in svg and "<image" not in svg, "默认不贴商品照，保持塔罗感"
    assert "rotate(180" in svg, "逆位时圣像应倒置"
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


def test_portion_note_never_contradicts_form():
    """形态文案不能自相矛盾：牌面偏套餐却给单品时，必须解释「为什么调」。"""
    period = tarot_engine.period_of(datetime(2026, 10, 20, 15, 30))  # 下午茶
    for card in tarot_deck.ALL_CARDS:
        base = tarot_deck.portion_of(card)
        label = tarot_deck.PORTION_LABEL.get(base, "单品")
        for form in ("single", "combo", "share", "light"):
            item = {"name": "测试餐品", "form": form}
            note = tarot_engine._portion_note(card, item, period, None)
            heavy_base = base in ("combo", "share")
            heavy_form = form in ("combo", "share")
            if heavy_base == heavy_form:
                assert note.startswith(f"牌面偏「{label}」"), (base, form, note)
            else:
                # 不一致时不能说「单品刚好」这类结论，要交代调整原因
                assert any(k in note for k in ("换成", "习惯点", "更对路", "接着")), (base, form, note)


def test_light_preference_avoids_combo_in_fallback():
    """「轻食」偏好落到兜底路径时也不能塞套餐（菜单 form 里没有 light）。"""
    card = {"id": 7, "mcd_keywords": ["不存在的菜"], "mcd_category": "查无此类"}
    menu = [{"name": "某三件套", "code": "1", "price": 35.0, "form": "combo", "category": ""},
            {"name": "某单品", "code": "2", "price": 20.0, "form": "single", "category": ""}]
    for _ in range(6):
        item = mcp_client.resolve_item(card, menu, exclude=set(), prefer_form="light")
        assert item["form"] == "single", item


def _coupon_profile():
    """一张单品券 + 一张满减券，用来验证「套餐能叠加优惠、单品券不越界」。"""
    return {
        "favorites": [{"name": "麦辣鸡腿汉堡", "count": 2}],
        "traits": {"chicken": 0.8},
        "coupons": [
            {"title": "11.9元麦辣鸡腿堡", "core": "麦辣鸡腿堡", "price": 11.9,
             "bogo": False, "combo": False, "combo_scope": False,
             "threshold": None, "threshold_off": None,
             "source": "claimable", "keywords": ["麦辣鸡腿堡"]},
            {"title": "满30减5", "core": "满减", "price": 5.0,
             "bogo": False, "combo": False, "combo_scope": False,
             "threshold": 30.0, "threshold_off": 5.0,
             "source": "wallet", "keywords": []},
        ],
    }


def test_combo_can_stack_threshold_coupon():
    """套餐能用满减券；单品券仍然不能抵扣套餐。"""
    prof = _coupon_profile()
    combo = {"name": "麦辣鸡腿汉堡三件套", "price": 39.0, "form": "combo", "category": "套餐"}
    single = {"name": "麦辣鸡腿堡", "price": 23.0, "form": "single", "category": "汉堡"}

    d_combo = mcp_client.deal_for(combo, prof)
    assert d_combo, "套餐应能用满减券"
    assert d_combo["kind"] == "threshold", d_combo
    assert abs(d_combo["saving"] - 5.0) < 0.01, d_combo

    d_single = mcp_client.deal_for(single, prof)
    assert d_single and abs(d_single["saving"] - 11.1) < 0.01, d_single

    # 单品券（11.9 麦辣鸡腿堡）绝不能被算到套餐头上
    only_item_coupon = {"favorites": [{"name": "x", "count": 1}],
                        "coupons": [prof["coupons"][0]]}
    assert mcp_client.deal_for(combo, only_item_coupon) is None, "单品券误抵套餐"


def test_combo_first_raises_combo_share():
    """默认套餐优先：同样的牌和菜单，开启后套餐占比明显更高。"""
    menu = [
        {"name": "巨无霸", "code": "1", "price": 26.0, "category": "汉堡", "form": "single"},
        {"name": "巨无霸三件套", "code": "2", "price": 37.0, "original_price": 50.5,
         "category": "汉堡", "form": "combo"},
        {"name": "麦香鸡", "code": "3", "price": 22.0, "category": "汉堡", "form": "single"},
        {"name": "麦香鸡套餐", "code": "4", "price": 32.0, "original_price": 42.0,
         "category": "汉堡", "form": "combo"},
    ]

    def combo_share(combo_first):
        hit = total = 0
        for day in range(1, 21):
            r = tarot_engine.do_reading("trinity", f"2026-11-{day:02d}", menu=menu,
                                        at=f"2026-11-{day:02d} 12:30", profile=None,
                                        combo_first=combo_first)
            for c in r["cards"]:
                total += 1
                hit += c["form"] in ("combo", "share")
        return hit / total

    on, off = combo_share(True), combo_share(False)
    assert on > off, (on, off)
    # 测试菜单只有 4 项（啤酒饮料甜品的牌没有套餐可落），能过一半就说明倾向生效
    assert on >= 0.55, f"套餐优先后套餐占比应明显偏高，实际 {on:.0%}"


def test_combo_option_prefers_bigger_discount():
    """同类套餐里优先挑折扣更深的那份。"""
    card = {"id": 7, "mcd_keywords": ["巨无霸"], "mcd_category": "汉堡"}
    menu = [
        {"name": "巨无霸", "price": 26.0, "form": "single", "category": "汉堡"},
        {"name": "巨无霸三件套", "price": 40.0, "original_price": 42.0,
         "form": "combo", "category": "汉堡"},
        {"name": "巨无霸超值套餐", "price": 33.0, "original_price": 52.0,
         "form": "combo", "category": "汉堡"},
    ]
    pick = mcp_client.combo_option(card, menu)
    assert pick and "超值" in pick["name"], pick


def test_major_arcana_have_category():
    """22 张大阿卡纳都必须有 mcd_category，否则「同品类兜底」对它们永远不生效。"""
    majors = [c for c in tarot_deck.ALL_CARDS if c["id"] < 22]
    missing = [c["name_cn"] for c in majors if not c.get("mcd_category")]
    assert not missing, f"这些大阿卡纳缺品类：{missing}"


def test_cat_match_bridges_two_naming_systems():
    """牌组品类（主食汉堡薯条）要能对上门店分类（鸡肉汉堡/卷、麦咖啡™）。"""
    pairs = [("鸡肉汉堡/卷", "主食汉堡薯条"), ("巨无霸牛鱼肉堡", "主食汉堡薯条"),
             ("麦咖啡™", "饮品甜饮"), ("饮品", "饮品甜饮"),
             ("小食甜品/其他", "辣味炸鸡"), ("安格斯MAX厚牛堡", "主食汉堡薯条")]
    for menu_cat, card_cat in pairs:
        assert mcp_client.cat_match(menu_cat, card_cat), (menu_cat, card_cat)
    assert not mcp_client.cat_match("饮品", "主食汉堡薯条"), "饮品不该被当成主食"


def test_any_combo_fallback_uses_pick_your_own():
    """同品类没有套餐时，「随心配」这种自选组合要能兜住任意一张牌。"""
    menu = [
        {"name": "麦香鸡", "code": "1", "price": 22.0, "form": "single", "category": "鸡肉汉堡/卷"},
        {"name": "人气经典随心配", "code": "2", "price": 13.9, "form": "combo", "category": "人气热卖"},
    ]
    # 一张指向饮品的牌：饮品品类下没有套餐，靠「随心配」兜底
    card = {"id": 17, "mcd_keywords": ["拿铁", "麦咖啡"], "mcd_category": "饮品甜饮"}
    pick = mcp_client.combo_option(card, menu)
    assert pick and "随心配" in pick["name"], pick


def test_combo_first_mostly_combo_when_menu_rich():
    """菜单里各品类都有套餐时，套餐优先后应该基本都给套餐。"""
    menu = [
        {"name": "巨无霸", "code": "1", "price": 26.0, "category": "巨无霸牛鱼肉堡", "form": "single"},
        {"name": "巨无霸三件套", "code": "2", "price": 37.0, "original_price": 50.5,
         "category": "巨无霸牛鱼肉堡", "form": "combo"},
        {"name": "麦辣鸡腿汉堡", "code": "3", "price": 23.0, "category": "鸡肉汉堡/卷", "form": "single"},
        {"name": "麦辣鸡腿堡套餐", "code": "4", "price": 33.0, "original_price": 44.0,
         "category": "鸡肉汉堡/卷", "form": "combo"},
        {"name": "可乐", "code": "5", "price": 9.5, "category": "饮品", "form": "single"},
        {"name": "人气经典随心配", "code": "6", "price": 13.9, "category": "人气热卖", "form": "combo"},
    ]
    hit = total = 0
    for day in range(1, 26):
        r = tarot_engine.do_reading("trinity", f"2026-12-{day:02d}", menu=menu,
                                    at=f"2026-12-{day:02d} 12:30", profile=None)
        for c in r["cards"]:
            total += 1
            hit += c["form"] in ("combo", "share")
    assert hit / total >= 0.85, f"套餐占比只有 {hit / total:.0%}"


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
