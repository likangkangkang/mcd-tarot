"""麦麦塔罗牌 · 牌组与麦当劳映射（纯数据 + 轻量构造，可离线单测）。

设计哲学
--------
塔罗更像一面帮你"听见自己"的镜子。我们把 78 张塔罗牌映射到麦当劳的
餐盘上：每张牌对应一种「此刻你需要的照顾方式」，再落到一道具体的麦麦食物上，
用一句情绪寄语把"该吃什么"变成"你值得被怎样对待"。

牌组结构
--------
- 大阿卡纳 Major Arcana（0~21，22 张）：手写精修，每张一个独立情绪主题。
- 小阿卡纳 Minor Arcana（56 张 = 4 花色 × 14 牌）：由「花色风味」×「牌点含义」
  自动组合生成，保证一致性与可扩展性。

花色 ↔ 麦当劳品类映射
--------------------
- 权杖 Wands（火）：辣味炸鸡 —— 行动力、热情、冲劲
- 圣杯 Cups（水）  ：饮品甜饮 —— 情感、关系、温柔
- 宝剑 Swords（风）：清爽轻盈 —— 清醒、理性、减负
- 星币 Pentacles（土）：主食汉堡薯条 —— 身体、物质、踏实
"""

from __future__ import annotations

from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# 大阿卡纳（22 张，手写精修）
# 字段：
#   id, name_cn, name_en, arcana, suit, rank
#   upright / reversed   : 牌义关键词
#   mcd_keywords         : 用于在真实菜单里匹配麦当劳单品的关键词（命中其一即可）
#   emotion_up / emotion_rev : 正位 / 逆位的情绪化寄语
# ---------------------------------------------------------------------------
MAJOR_ARCANA: List[Dict] = [
    {
        "id": 0, "name_cn": "愚者", "name_en": "The Fool", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "新的开始、自由、不设限",
        "reversed": "鲁莽、犹豫、逃避",
        "mcd_keywords": ["麦辣鸡腿汉堡", "麦辣鸡翅", "辣"],
        "emotion_up": "今天适合跳出舒适区。来点带劲的——你值得一场说走就走的小冒险，哪怕只是一口辣。",
        "emotion_rev": "别急着冲。先稳住呼吸，想清楚再出发也不迟，退一步不是认输。",
    },
    {
        "id": 1, "name_cn": "魔术师", "name_en": "The Magician", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "创造、你已拥有全部原料",
        "reversed": "自我怀疑、能量分散",
        "mcd_keywords": ["巨无霸", "双层吉士汉堡"],
        "emotion_up": "你手里其实什么都有。就像巨无霸——面包、肉、酱、菜全齐了，今天你也能把事情拼成想要的样子。",
        "emotion_rev": "不是你不行，是摊开的太多。先收一收，专注一件事就好。",
    },
    {
        "id": 2, "name_cn": "女祭司", "name_en": "The High Priestess", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "直觉、内在的甜",
        "reversed": "忽视感受、过度理性",
        "mcd_keywords": ["麦旋风", "派"],
        "emotion_up": "有些答案不用想，用感觉。来一份凉凉甜甜的，让直觉替你做主这一次。",
        "emotion_rev": "你把自己绷得太紧了。允许今天不做决定，先好好感受。",
    },
    {
        "id": 3, "name_cn": "皇后", "name_en": "The Empress", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "丰盛、滋养、舒适",
        "reversed": "自我忽略、付出过多",
        "mcd_keywords": ["薯条", "玉米杯"],
        "emotion_up": "你值得被好好喂养。热乎乎、香喷喷的，把自己当成被宠爱的人来照顾。",
        "emotion_rev": "给了别人太多，轮到你了。先把这份丰盛留一点给自己。",
    },
    {
        "id": 4, "name_cn": "皇帝", "name_en": "The Emperor", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "秩序、经典、掌控",
        "reversed": "控制欲、僵化",
        "mcd_keywords": ["双层吉士汉堡", "麦香鸡"],
        "emotion_up": "今天需要一点确定感。来份你永远信得过的经典，让胃先踏实下来，心也跟着稳。",
        "emotion_rev": "规则是为人服务的。偶尔打破一下，天不会塌。",
    },
    {
        "id": 5, "name_cn": "教皇", "name_en": "The Hierophant", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "传统、信任、安心",
        "reversed": "盲从、束缚",
        "mcd_keywords": ["麦香鸡", "麦辣鸡腿堡"],
        "emotion_up": "有些老味道之所以一直在，是因为它从没让你失望过。今天，给自己一个安心的选择。",
        "emotion_rev": "别人的建议听听就好。你比任何攻略都更懂自己的胃口。",
    },
    {
        "id": 6, "name_cn": "恋人", "name_en": "The Lovers", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "连接、选择、分享",
        "reversed": "纠结、疏离",
        "mcd_keywords": ["新地", "限定风味麦旋风"],
        "emotion_up": "好东西要有人一起才完整。今天给自己点一份甜的，也可以顺手问一句：要不要一起？",
        "emotion_rev": "不是所有的选择都要立刻做。先和自己的心待一会儿。",
    },
    {
        "id": 7, "name_cn": "战车", "name_en": "The Chariot", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "驱动、冲劲、胜利在望",
        "reversed": "失控、方向不明",
        "mcd_keywords": ["麦辣鸡翅", "辣翅"],
        "emotion_up": "油门踩下去。来点带火气的，给今天那股冲劲一点燃料。",
        "emotion_rev": "拉得太满会翻车。先减速，校准方向再出发。",
    },
    {
        "id": 8, "name_cn": "力量", "name_en": "Strength", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "温柔的力量、耐心",
        "reversed": "自我施压、焦躁",
        "mcd_keywords": ["板烧鸡腿堡", "烤"],
        "emotion_up": "真正的强不是硬撑，是温柔地稳住。今天用一份不燥不火的味道，陪你把事扛过去。",
        "emotion_rev": "对自己松一点。你已经够努力了，不必每刻都紧绷。",
    },
    {
        "id": 9, "name_cn": "隐者", "name_en": "The Hermit", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "独处、自省、安静的奖赏",
        "reversed": "孤立、逃避",
        "mcd_keywords": ["美式", "咖啡"],
        "emotion_up": "今天适合一个人。一杯黑咖啡，一段不被打扰的时间，和自己好好见个面。",
        "emotion_rev": "独处是充电，不是躲起来。需要人时，开口不丢人。",
    },
    {
        "id": 10, "name_cn": "命运之轮", "name_en": "Wheel of Fortune", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "转机、交给命运",
        "reversed": "抗拒变化",
        "mcd_keywords": ["随心配", "惊喜", "随机"],
        "emotion_up": "有些事算不出，那就别算。今天把选择权交给命运——随便点，惊喜往往在计划外。",
        "emotion_rev": "轮子在转，坏的也会过去。别死死抓住，松手反而稳。",
    },
    {
        "id": 11, "name_cn": "正义", "name_en": "Justice", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "平衡、理性之选",
        "reversed": "失衡、自欺",
        "mcd_keywords": ["板烧鸡腿堡", "玉米杯"],
        "emotion_up": "今天讲究个恰到好处。不饿着自己，也不亏待自己，一份均衡的就很好。",
        "emotion_rev": "别对自己双标。你给别人的宽容，也该留一份给自己。",
    },
    {
        "id": 12, "name_cn": "倒吊人", "name_en": "The Hanged Man", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "暂停、换个角度看",
        "reversed": "拖延、卡住",
        "mcd_keywords": ["苹果片", "沙拉", "蔬果"],
        "emotion_up": "卡住的时候，不妨倒过来看。来点清爽的，给脑子透透气，答案会自己浮上来。",
        "emotion_rev": "暂停不是放弃。允许自己停一下，电池满了再走。",
    },
    {
        "id": 13, "name_cn": "死神", "name_en": "Death", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "转化、结束即新生",
        "reversed": "恐惧改变",
        "mcd_keywords": ["限定", "新品", "季节"],
        "emotion_up": "一段该翻篇了。试试从没点过的新品或限时款，给生活一个小小的重启键。",
        "emotion_rev": "结束不代表失去。放手那个旧版本，新的才有位置坐下来。",
    },
    {
        "id": 14, "name_cn": "节制", "name_en": "Temperance", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "调和、适度、刚刚好",
        "reversed": "极端、过量",
        "mcd_keywords": ["玉米杯", "红豆派"],
        "emotion_up": "今天不宜过猛。来点温和的、小小的甜，刚好够，就是最好的分寸。",
        "emotion_rev": "哪头都不用走到尽头。回到中间，你会舒服很多。",
    },
    {
        "id": 15, "name_cn": "魔鬼", "name_en": "The Devil", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "渴望、允许自己想要更多",
        "reversed": "沉溺、被束缚",
        "mcd_keywords": ["十翅", "薯条", "可乐"],
        "emotion_up": "想要就大大方方要。今天不必自律上头——加份大的，快乐是真实的，别罪恶。",
        "emotion_rev": "爽完记得回来。被欲望牵着走时，停一下问问自己真需要吗。",
    },
    {
        "id": 16, "name_cn": "高塔", "name_en": "The Tower", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "突如其来的震动、清醒",
        "reversed": "压抑的爆发",
        "mcd_keywords": ["龙焰鸡腿堡", "辣"],
        "emotion_up": "今天有点炸。来点更冲的，让那股被压住的情绪随辣意一起散掉。",
        "emotion_rev": "别把雷压在心里。找个出口释放，比硬撑体面得多。",
    },
    {
        "id": 17, "name_cn": "星星", "name_en": "The Star", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "希望、温柔的光",
        "reversed": "失望、自我怀疑",
        "mcd_keywords": ["拿铁", "麦咖啡", "咖啡"],
        "emotion_up": "再暗的夜也有星。今天给自己一点温柔的甜暖，热拿铁捧在手里，你就没那么孤单。",
        "emotion_rev": "希望没丢，只是被云挡住了。先照顾好此刻的自己，光会回来的。",
    },
    {
        "id": 18, "name_cn": "月亮", "name_en": "The Moon", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "梦境、深夜的渴望",
        "reversed": "迷雾、焦虑",
        "mcd_keywords": ["新地", "麦旋风", "夜宵"],
        "emotion_up": "月亮下的馋，是身体在说想被哄睡。今晚允许一次小小的夜宵，安安静静宠自己。",
        "emotion_rev": "看不清的时候别乱走。先睡一觉，明天的事明天再说。",
    },
    {
        "id": 19, "name_cn": "太阳", "name_en": "The Sun", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "喜悦、简单的幸福",
        "reversed": "暂时的阴霾",
        "mcd_keywords": ["灰焰圆筒", "新地", "开心乐园餐"],
        "emotion_up": "今天就该笑。一支圆筒、一份童年味道，快乐可以这么小、这么真。",
        "emotion_rev": "太阳还在，只是云厚。给自己一点时间，晴朗会回来。",
    },
    {
        "id": 20, "name_cn": "审判", "name_en": "Judgement", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "觉醒、清晰、重新开始",
        "reversed": "自我审判、内耗",
        "mcd_keywords": ["燕麦奶铁", "早餐", "全餐"],
        "emotion_up": "是时候清醒地开始了。一份像样的早餐，是把「今天」郑重接过来的仪式。",
        "emotion_rev": "别再翻旧账审判自己。原谅那个过去的你，往前走。",
    },
    {
        "id": 21, "name_cn": "世界", "name_en": "The World", "arcana": "major",
        "suit": None, "rank": None,
        "upright": "圆满、完整、庆祝",
        "reversed": "未竟、意难平",
        "mcd_keywords": ["人气经典随心配", "全明星双人分享餐"],
        "emotion_up": "你走到一个完整的节点了。值得挑一份「全都要」的，好好庆祝这一程。",
        "emotion_rev": "还差一点点就圆满。别急，剩下的交给时间，它会补齐。",
    },
]

# ---------------------------------------------------------------------------
# 小阿卡纳：花色风味 × 牌点含义 → 自动组合
# ---------------------------------------------------------------------------
SUITS: Dict[str, Dict] = {
    "wands": {
        "name_cn": "权杖", "name_en": "Wands", "element": "火",
        "mcd_category": "辣味炸鸡",
        "mcd_keywords": ["麦辣鸡腿汉堡", "麦辣鸡翅", "辣翅", "炸鸡", "辣"],
        "tone": "行动力、热情、冲劲",
        "tone_msg": "今天你需要一点火气与冲劲，让身体先热起来。",
    },
    "cups": {
        "name_cn": "圣杯", "name_en": "Cups", "element": "水",
        "mcd_category": "饮品甜饮",
        "mcd_keywords": ["可乐", "雪碧", "美式", "拿铁", "咖啡", "红豆派", "麦旋风", "派"],
        "tone": "情感、关系、温柔",
        "tone_msg": "今天你需要被温柔地对待，用一杯甜的或暖的，把情绪接住。",
    },
    "swords": {
        "name_cn": "宝剑", "name_en": "Swords", "element": "风",
        "mcd_category": "清爽轻盈",
        "mcd_keywords": ["苹果片", "沙拉", "玉米杯", "鲜煮", "蔬果", "青瓜"],
        "tone": "清醒、理性、减负",
        "tone_msg": "今天你需要清爽与通透，给身体减减负，脑子也跟着亮。",
    },
    "pentacles": {
        "name_cn": "星币", "name_en": "Pentacles", "element": "土",
        "mcd_category": "主食汉堡薯条",
        "mcd_keywords": ["巨无霸", "吉士", "薯条", "汉堡", "麦香鸡", "双层", "板烧"],
        "tone": "身体、物质、踏实",
        "tone_msg": "今天你需要落地与踏实，用一份管饱的，把底气压稳。",
    },
}

# 牌点含义（正位 / 逆位 短句）+ 在该花色下的情绪化表达模板
RANKS: Dict[str, Dict] = {
    "ace": {
        "name_cn": "Ace", "name_en": "Ace",
        "upright": "纯粹的起始能量", "reversed": "能量未打开、空想",
        "msg_up": "一个清爽的开头。带着{_tone}，从今天这第一口开始，刚刚好。",
        "msg_rev": "想法还在壳里。先动一小口，能量就来了。",
    },
    "2": {
        "name_cn": "二", "name_en": "Two",
        "upright": "选择、二元、伙伴", "reversed": "犹豫、拉扯",
        "msg_up": "面前有两样都想要？今天不妨让直觉替你选——选让你心安的那份。",
        "msg_rev": "别在两份之间反复横跳。跟着直觉，落子无悔。",
    },
    "3": {
        "name_cn": "三", "name_en": "Three",
        "upright": "创造、初步成果", "reversed": "拖延、不成形",
        "msg_up": "小事开始有模样了。用一份实在的犒劳，给正在发芽的努力一点甜头。",
        "msg_rev": "还没成形没关系。先吃口东西，灵感往往在饱腹后回来。",
    },
    "4": {
        "name_cn": "四", "name_en": "Four",
        "upright": "稳定、巩固、休息", "reversed": "停滞、守旧",
        "msg_up": "今天适合稳住。一份熟悉的味道，给奔波的自己一个歇脚处。",
        "msg_rev": "别停在舒适区太久。换个小花样，局面就活了。",
    },
    "5": {
        "name_cn": "五", "name_en": "Five",
        "upright": "冲突、挑战、失落", "reversed": "从低谷回升",
        "msg_up": "今天有点难，但你会过去。先喂饱自己，才有力气扛。",
        "msg_rev": "最难那段已经过了。补一口元气，把亏掉的慢慢找回来。",
    },
    "6": {
        "name_cn": "六", "name_en": "Six",
        "upright": "和谐、疗愈、调和", "reversed": "失衡、勉强",
        "msg_up": "今天需要被抚平。让一份温柔的甜，轻轻顺了顺你皱着的眉。",
        "msg_rev": "别硬凑和谐。先照顾真实感受，调和才来得真。",
    },
    "7": {
        "name_cn": "七", "name_en": "Seven",
        "upright": "评估、坚持、内省", "reversed": "自我消耗、散焦",
        "msg_up": "默默坚持的你值得被看见。用一份喜欢的，给坚持一点甜头。",
        "msg_rev": "别把自己耗干了。今天少做一点，也是种智慧。",
    },
    "8": {
        "name_cn": "八", "name_en": "Eight",
        "upright": "行动、掌控、加速", "reversed": "忙碌失序",
        "msg_up": "节奏起来了！用今天这一口，给加速度加点燃料。",
        "msg_rev": "忙不等于有效。先停一口，重新排下序。",
    },
    "9": {
        "name_cn": "九", "name_en": "Nine",
        "upright": "接近圆满、收获前夕", "reversed": "焦虑、临门一脚",
        "msg_up": "就快到了。先预支一点庆祝，给即将达成的事。",
        "msg_rev": "越接近越慌？正常。先吃口东西，把心放回肚子里。",
    },
    "10": {
        "name_cn": "十", "name_en": "Ten",
        "upright": "完成、顶点、循环", "reversed": "重负、难以承受",
        "msg_up": "一个阶段圆满收尾。用今天这一口，给这段路画个温柔的句号。",
        "msg_rev": "担子有点重。分一口给别人，也分一口轻松给自己。",
    },
    "page": {
        "name_cn": "侍从", "name_en": "Page",
        "upright": "探索、学习、新鲜消息", "reversed": "分心、幼稚",
        "msg_up": "今天有点好奇宝宝。试试没点过的新搭配，让味蕾也去探险。",
        "msg_rev": "别东张西望。先把手头这口尝明白。",
    },
    "knight": {
        "name_cn": "骑士", "name_en": "Knight",
        "upright": "行动、推进、专注能量", "reversed": "冲动、偏航",
        "msg_up": "目标明确就冲。今天这道该吃的，就是给你这股劲的燃料。",
        "msg_rev": "冲太快容易歪。先喘口气，校准再上路。",
    },
    "queen": {
        "name_cn": "王后", "name_en": "Queen",
        "upright": "丰盈、滋养、成熟掌控", "reversed": "过度付出、情绪化",
        "msg_up": "今天你是被宠爱的主角。慢慢享用，你配得上这份丰盛。",
        "msg_rev": "给了太多忘了自己。先把这份滋养留一点给自己。",
    },
    "king": {
        "name_cn": "国王", "name_en": "King",
        "upright": "掌控、权威、稳定输出", "reversed": "掌控欲、冷硬",
        "msg_up": "今天你稳得住。这道踏实的选择，就是你的底气。",
        "msg_rev": "别把弦绷成铁。偶尔松一点，掌控反而更自在。",
    },
}

# 小阿卡纳生成：4 花色 × 14 牌点
_MINOR_RANKS = [
    "ace", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "page", "knight", "queen", "king",
]


def _build_minor() -> List[Dict]:
    cards: List[Dict] = []
    mid = 22  # 大阿卡纳占 0~21
    for suit_key, suit in SUITS.items():
        for rank_key in _MINOR_RANKS:
            rank = RANKS[rank_key]
            cat = suit["mcd_category"]
            tone = suit["tone"]
            card = {
                "id": mid,
                "name_cn": f"{suit['name_cn']}{rank['name_cn']}",
                "name_en": f"{rank['name_en']} of {suit['name_en']}",
                "arcana": "minor",
                "suit": suit_key,
                "rank": rank_key,
                "element": suit["element"],
                "mcd_category": cat,
                "mcd_keywords": list(suit["mcd_keywords"]),
                "upright": rank["upright"],
                "reversed": rank["reversed"],
                "emotion_up": rank["msg_up"].format(cat=cat, _tone=tone),
                "emotion_rev": rank["msg_rev"].format(cat=cat, _tone=tone),
            }
            cards.append(card)
            mid += 1
    return cards


MINOR_ARCANA: List[Dict] = _build_minor()

# 全牌组（78 张），按 id 排序
ALL_CARDS: List[Dict] = sorted(MAJOR_ARCANA + MINOR_ARCANA, key=lambda c: c["id"])

# 便于按 id / 名称查找
_BY_ID: Dict[int, Dict] = {c["id"]: c for c in ALL_CARDS}
_BY_NAME: Dict[str, Dict] = {c["name_cn"]: c for c in ALL_CARDS}


def get_card(card_id: int) -> Optional[Dict]:
    return _BY_ID.get(card_id)


def find_card(name: str) -> Optional[Dict]:
    return _BY_NAME.get(name)


def deck_size() -> int:
    return len(ALL_CARDS)


if __name__ == "__main__":
    print(f"牌组总数: {deck_size()}")
    print(f"大阿卡纳: {len(MAJOR_ARCANA)} 张, 小阿卡纳: {len(MINOR_ARCANA)} 张")
    print("示例 - 愚者:", find_card("愚者")["emotion_up"])
    print("示例 - 权杖骑士:", find_card("权杖骑士")["emotion_up"])
