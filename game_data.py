"""修仙世界数据：境界、灵根、功法、经脉、地点、妖兽、物品、炼器"""

import random
from events import FORTUNE_EVENTS, SURPRISE_EVENTS

# ═══════════════ 境界系统 ═══════════════
REALMS = {
    1:  ("练气期", "初期"), 2:  ("练气期", "中期"), 3:  ("练气期", "后期"),
    4:  ("筑基期", "初期"), 5:  ("筑基期", "中期"), 6:  ("筑基期", "后期"),
    7:  ("结丹期", "初期"), 8:  ("结丹期", "中期"), 9:  ("结丹期", "后期"),
    10: ("元婴期", "初期"), 11: ("元婴期", "后期"),
    12: ("化神期", ""), 13: ("炼虚期", ""), 14: ("合体期", ""), 15: ("大乘期", ""),
}

EXP_PER_LEVEL = [0, 0, 50, 120, 220, 360, 550, 800, 1120, 1520, 2020, 2620, 3360, 4240, 5300, 6600]
MAX_LEVEL = 15

BREAKTHROUGH_CHANCE = {
    1: 1.0, 2: 1.0, 3: 0.95, 4: 0.9, 5: 0.9, 6: 0.85,
    7: 0.8, 8: 0.75, 9: 0.7, 10: 0.6, 11: 0.5,
    12: 0.4, 13: 0.3, 14: 0.2, 15: 1.0,
}

def realm_name(level):
    if level <= 0: return "凡人"
    lv = min(level, 15)
    name, stage = REALMS[lv]
    return f"{name}{stage}" if stage else name

# ═══════════════ 灵根系统 ═══════════════
SPIRIT_ROOTS = {
    "fei":      {"name": "废灵根",   "desc": "灵根斑驳，修炼极慢",   "cultivation_mult": 0.5, "element": None, "weight": 15},
    "zashuang": {"name": "杂灵根",   "desc": "双属性灵根，修炼较慢", "cultivation_mult": 0.8, "element": None, "weight": 20},
    "ling":     {"name": "灵根",     "desc": "单属性灵根，修炼正常", "cultivation_mult": 1.0, "element": None, "weight": 30},
    "jin":      {"name": "金灵根",   "desc": "金属性灵根，攻伐凌厉", "cultivation_mult": 1.1, "element": "金", "weight": 8},
    "mu":       {"name": "木灵根",   "desc": "木属性灵根，生机旺盛", "cultivation_mult": 1.1, "element": "木", "weight": 8},
    "shui":     {"name": "水灵根",   "desc": "水属性灵根，灵力绵长", "cultivation_mult": 1.1, "element": "水", "weight": 8},
    "huo":      {"name": "火灵根",   "desc": "火属性灵根，攻势霸道", "cultivation_mult": 1.1, "element": "火", "weight": 8},
    "tu":       {"name": "土灵根",   "desc": "土属性灵根，防御坚固", "cultivation_mult": 1.1, "element": "土", "weight": 8},
    "tian":     {"name": "天灵根",   "desc": "百年难遇，修炼神速",   "cultivation_mult": 1.5, "element": None, "weight": 3},
    "huntian":  {"name": "混沌灵根", "desc": "万年一遇，天赋异禀",   "cultivation_mult": 2.0, "element": None, "weight": 1},
}

# 五行相克：key 克 value
ELEMENT_COUNTER = {"金": "木", "木": "土", "土": "水", "水": "火", "火": "金"}

def roll_spirit_root():
    pool = []
    for rid, r in SPIRIT_ROOTS.items():
        pool.extend([rid] * r["weight"])
    return random.choice(pool)

# ═══════════════ 放置修炼 ═══════════════
# 每秒修为收益（基础值，乘以灵根倍率）
IDLE_EXP_PER_SEC = 0.15
IDLE_MAX_HOURS = 24

# ═══════════════ 功法系统 ═══════════════
TECHNIQUES = {
    "jichu_tuna":  {"name": "基础吐纳术", "tier": "黄阶", "desc": "最基础的吐纳之法",       "bonus_hp": 0,  "bonus_atk": 0,  "bonus_def": 0,  "bonus_exp_pct": 0.05, "req_realm": 1},
    "lingxi_jue":  {"name": "灵息诀",     "tier": "黄阶", "desc": "感应天地灵气的法诀",     "bonus_hp": 10, "bonus_atk": 1,  "bonus_def": 0,  "bonus_exp_pct": 0.0,  "req_realm": 1},
    "huntie_gong": {"name": "混铁功",     "tier": "黄阶", "desc": "锤炼肉身的炼体功法",     "bonus_hp": 20, "bonus_atk": 0,  "bonus_def": 2,  "bonus_exp_pct": 0.0,  "req_realm": 2},
    "qingyun_jue": {"name": "青云诀",     "tier": "玄阶", "desc": "青云镇不传之秘",         "bonus_hp": 15, "bonus_atk": 3,  "bonus_def": 1,  "bonus_exp_pct": 0.1,  "req_realm": 4},
    "xuantian_gong":{"name": "玄天功",   "tier": "玄阶", "desc": "玄天正宗的镇派功法",     "bonus_hp": 30, "bonus_atk": 5,  "bonus_def": 3,  "bonus_exp_pct": 0.05, "req_realm": 4},
    "pozhen_jianfa":{"name": "破阵剑法",  "tier": "玄阶", "desc": "以力破巧的刚猛剑法",     "bonus_hp": 0,  "bonus_atk": 8,  "bonus_def": 0,  "bonus_exp_pct": 0.0,  "req_realm": 5},
    "jiuyang_gong":{"name": "九阳功",     "tier": "地阶", "desc": "至阳至刚的绝世功法",     "bonus_hp": 50, "bonus_atk": 8,  "bonus_def": 2,  "bonus_exp_pct": 0.15, "req_realm": 7},
    "taiyi_jue":   {"name": "太乙诀",     "tier": "地阶", "desc": "道门正宗的无上法诀",     "bonus_hp": 40, "bonus_atk": 4,  "bonus_def": 8,  "bonus_exp_pct": 0.1,  "req_realm": 7},
    "tianmo_gong": {"name": "天魔功",     "tier": "地阶", "desc": "魔道至高功法，威力惊人", "bonus_hp": 30, "bonus_atk": 12, "bonus_def": 0,  "bonus_exp_pct": 0.0,  "req_realm": 8},
    "hundun_jue":  {"name": "混沌诀",     "tier": "天阶", "desc": "上古大能遗留的无上功法", "bonus_hp": 80, "bonus_atk": 15, "bonus_def": 10, "bonus_exp_pct": 0.2,  "req_realm": 10},
}

# ═══════════════ 经脉系统 ═══════════════
MERIDIANS = {
    "ren_mai":  {"name": "任脉",   "desc": "主血，打通后气血充盈",       "cost": 80,   "bonus_hp": 20, "bonus_atk": 0,  "bonus_def": 2,  "req_realm": 2},
    "du_mai":   {"name": "督脉",   "desc": "主气，打通后灵力大增",       "cost": 80,   "bonus_hp": 10, "bonus_atk": 3,  "bonus_def": 0,  "req_realm": 2},
    "chong_mai":{"name": "冲脉",   "desc": "十二经之海，攻守兼备",       "cost": 200,  "bonus_hp": 15, "bonus_atk": 2,  "bonus_def": 2,  "req_realm": 4},
    "dai_mai":  {"name": "带脉",   "desc": "约束诸经，防御大增",         "cost": 200,  "bonus_hp": 10, "bonus_atk": 0,  "bonus_def": 5,  "req_realm": 4},
    "yinwei":   {"name": "阴维脉", "desc": "维系阴经，灵力绵长",         "cost": 500,  "bonus_hp": 25, "bonus_atk": 3,  "bonus_def": 3,  "req_realm": 6},
    "yangwei":  {"name": "阳维脉", "desc": "维系阳经，攻势凌厉",         "cost": 500,  "bonus_hp": 15, "bonus_atk": 6,  "bonus_def": 0,  "req_realm": 6},
    "yinqiao":  {"name": "阴跷脉", "desc": "主静，打通后心如止水",       "cost": 1200, "bonus_hp": 30, "bonus_atk": 0,  "bonus_def": 6,  "req_realm": 8},
    "yangqiao": {"name": "阳跷脉", "desc": "主动，打通后身法如电",       "cost": 1200, "bonus_hp": 20, "bonus_atk": 8,  "bonus_def": 2,  "req_realm": 8},
}

# ═══════════════ 炼丹配方 ═══════════════
RECIPES = {
    "huiqi_dan":   {"name": "回气丹",     "ingredients": {"lingcao": 3},                                  "output": "huiqi_dan",   "output_count": 1, "req_realm": 1},
    "huichun_dan": {"name": "回春丹",     "ingredients": {"lingcao": 2, "bingling_cao": 1},               "output": "huichun_dan", "output_count": 1, "req_realm": 3},
    "xuming_dan":  {"name": "续命丹",     "ingredients": {"bingling_cao": 2, "huoling_hua": 1, "lingcao": 2}, "output": "xuming_dan", "output_count": 1, "req_realm": 5},
    "peiyuan_dan": {"name": "培元丹",     "ingredients": {"huoling_hua": 2, "lingcao": 1},               "output": "peiyuan_dan", "output_count": 1, "req_realm": 4},
    "juling_dan":  {"name": "聚灵丹",     "ingredients": {"wanling_guo": 1, "huoling_hua": 2, "bingling_cao": 1}, "output": "juling_dan", "output_count": 1, "req_realm": 6},
    "wudao_dan":   {"name": "悟道丹",     "ingredients": {"wanling_guo": 2, "jiuhuan_cao": 1},           "output": "wudao_dan",   "output_count": 1, "req_realm": 8},
    "pojing_dan":  {"name": "破境丹",     "ingredients": {"wanling_guo": 3, "bingling_cao": 2, "huoling_hua": 2}, "output": "pojing_dan", "output_count": 1, "req_realm": 7},
    "jiuzhuan_dan":{"name": "九转还魂丹", "ingredients": {"jiuhuan_cao": 2, "longxian_cao": 1, "fengxue_hua": 1, "wanling_guo": 2}, "output": "jiuzhuan_dan", "output_count": 1, "req_realm": 10},
}

# ═══════════════ 炼器配方（锻造装备）═══════════════
FORGE_RECIPES = {
    "forge_t1_weapon":    {"name": "锻造·凡器武器", "slot": "weapon", "tier": 1, "ingredients": {"hantie_kuang": 2, "yaogu": 1}, "success_rate": 0.95, "req_realm": 1},
    "forge_t1_armor":     {"name": "锻造·凡器护甲", "slot": "armor",  "tier": 1, "ingredients": {"yaopimo": 2, "lingcao": 3}, "success_rate": 0.95, "req_realm": 1},
    "forge_t2_weapon":    {"name": "锻造·法器武器", "slot": "weapon", "tier": 2, "ingredients": {"hantie_kuang": 3, "yaogu": 2, "yaodan": 1}, "success_rate": 0.85, "req_realm": 3},
    "forge_t2_armor":     {"name": "锻造·法器护甲", "slot": "armor",  "tier": 2, "ingredients": {"hantie_kuang": 2, "yaopimo": 3, "yaodan": 1}, "success_rate": 0.85, "req_realm": 3},
    "forge_t3_weapon":    {"name": "锻造·法器武器★", "slot": "weapon", "tier": 3, "ingredients": {"xuanjin_shi": 3, "yaodan": 2, "yaogu": 3}, "success_rate": 0.70, "req_realm": 5},
    "forge_t3_armor":     {"name": "锻造·法器护甲★", "slot": "armor",  "tier": 3, "ingredients": {"xuanjin_shi": 3, "yaopimo": 4, "yaodan": 2}, "success_rate": 0.70, "req_realm": 5},
    "forge_t3_accessory": {"name": "锻造·法器饰品", "slot": "accessory", "tier": 3, "ingredients": {"xuanjin_shi": 2, "yaodan": 2, "wanling_guo": 1}, "success_rate": 0.75, "req_realm": 4},
    "forge_t4_weapon":    {"name": "锻造·灵器武器", "slot": "weapon", "tier": 4, "ingredients": {"tianwai_yuntie": 2, "yaodan": 4, "longxian_cao": 1}, "success_rate": 0.55, "req_realm": 7},
    "forge_t4_armor":     {"name": "锻造·灵器护甲", "slot": "armor",  "tier": 4, "ingredients": {"tianwai_yuntie": 2, "yaopimo": 5, "yaodan": 3, "longxian_cao": 1}, "success_rate": 0.55, "req_realm": 7},
    "forge_t4_accessory": {"name": "锻造·灵器饰品", "slot": "accessory", "tier": 4, "ingredients": {"tianwai_yuntie": 2, "yaodan": 4, "wanling_guo": 2}, "success_rate": 0.60, "req_realm": 6},
    "forge_t5_weapon":    {"name": "锻造·灵器武器★", "slot": "weapon", "tier": 5, "ingredients": {"tianwai_yuntie": 3, "zijin_kuang": 2, "yaodan": 5, "fengxue_hua": 1}, "success_rate": 0.40, "req_realm": 9},
    "forge_t5_armor":     {"name": "锻造·灵器护甲★", "slot": "armor",  "tier": 5, "ingredients": {"tianwai_yuntie": 3, "zijin_kuang": 2, "yaopimo": 5, "yaodan": 4}, "success_rate": 0.40, "req_realm": 9},
    "forge_t5_accessory": {"name": "锻造·灵器饰品★", "slot": "accessory", "tier": 5, "ingredients": {"zijin_kuang": 2, "yaodan": 5, "fengxue_hua": 1, "wanling_guo": 2}, "success_rate": 0.45, "req_realm": 8},
    "forge_t6_weapon":    {"name": "锻造·仙器武器", "slot": "weapon", "tier": 6, "ingredients": {"zijin_kuang": 5, "tianwai_yuntie": 4, "fengxue_hua": 2, "longxian_cao": 2}, "success_rate": 0.25, "req_realm": 11},
    "forge_t6_armor":     {"name": "锻造·仙器护甲", "slot": "armor",  "tier": 6, "ingredients": {"zijin_kuang": 5, "tianwai_yuntie": 4, "fengxue_hua": 2, "jiuhuan_cao": 1}, "success_rate": 0.25, "req_realm": 11},
    "forge_t6_accessory": {"name": "锻造·仙器饰品", "slot": "accessory", "tier": 6, "ingredients": {"zijin_kuang": 4, "fengxue_hua": 2, "longxian_cao": 2, "jiuhuan_cao": 1}, "success_rate": 0.30, "req_realm": 10},
    "forge_t7_weapon":    {"name": "锻造·神器武器", "slot": "weapon", "tier": 7, "ingredients": {"zijin_kuang": 8, "tianwai_yuntie": 6, "fengxue_hua": 3, "longxian_cao": 3, "jiuhuan_cao": 2}, "success_rate": 0.12, "req_realm": 13},
    "forge_t7_armor":     {"name": "锻造·神器护甲", "slot": "armor",  "tier": 7, "ingredients": {"zijin_kuang": 8, "tianwai_yuntie": 6, "fengxue_hua": 3, "longxian_cao": 3, "jiuhuan_cao": 2}, "success_rate": 0.12, "req_realm": 13},
}
FORGE_REALM_BONUS_PER_LV = 0.03

# ═══════════════ 装备随机生成系统 ═══════════════
EQUIP_PREFIXES = {
    1: [("破风", {"atk": 1}), ("坚毅", {"def": 1}), ("粗犷", {"bonus_hp": 5})],
    2: [("寒铁", {"atk": 2}), ("灵纹", {"def": 2}), ("蕴灵", {"bonus_hp": 10})],
    3: [("破甲", {"atk": 4}), ("玄铁", {"def": 3}), ("蕴灵", {"bonus_hp": 15}), ("锐利", {"atk": 3, "def": 1})],
    4: [("噬魂", {"atk": 6}), ("玄冰", {"def": 5}), ("龙血", {"bonus_hp": 25}), ("烈焰", {"atk": 5, "bonus_hp": 10})],
    5: [("天罡", {"atk": 8}), ("地煞", {"def": 7}), ("九幽", {"bonus_hp": 40}), ("星辰", {"atk": 6, "def": 4})],
    6: [("诛仙", {"atk": 12}), ("混元", {"def": 10}), ("太古", {"bonus_hp": 60}), ("混沌", {"atk": 8, "def": 6, "bonus_hp": 20})],
    7: [("鸿蒙", {"atk": 18}), ("造化", {"def": 15}), ("万古", {"bonus_hp": 100}), ("无极", {"atk": 12, "def": 10, "bonus_hp": 40})],
}
EQUIP_MATERIALS = {
    "weapon": {1: ["铁木","青石","榆木"], 2: ["寒铁","玄铁","黑铁"], 3: ["青钢","陨铁","星铁"], 4: ["灵晶","玄玉","紫金"], 5: ["天外陨铁","九天玄铁","龙骨"], 6: ["仙灵石","太古神铁","星辰石"], 7: ["鸿蒙神铁","造化神石","混沌玄金"]},
    "armor":  {1: ["粗布","麻衣","兽皮"], 2: ["灵纹","藤甲","铁叶"], 3: ["玄铁","银丝","蛟皮"], 4: ["灵蚕丝","龙鳞","玄晶"], 5: ["星辰砂","凤羽","天蚕丝"], 6: ["仙灵锦","混沌丝","太古龙鳞"], 7: ["鸿蒙仙锦","造化神丝","无极天衣"]},
    "accessory": {3: ["青玉","灵石","碧晶"], 4: ["紫玉","龙牙","凤血石"], 5: ["天蚕丝","龙骨","星辰珠"], 6: ["仙灵玉","混沌珠","太古龙珠"]},
}
WEAPON_SUFFIXES = ["剑","刀","刃","枪","戟","刺"]
ARMOR_SUFFIXES = ["甲","袍","衣","铠","裳","罩"]
ACCESSORY_SUFFIXES = ["佩","符","环","珠","铃","令"]
EQUIP_TIERS = {
    1: {"grade": "凡器", "base_atk": 5, "base_def": 4, "base_hp": 0, "bonus_exp_pct": 0},
    2: {"grade": "法器·下品", "base_atk": 10, "base_def": 8, "base_hp": 10, "bonus_exp_pct": 0},
    3: {"grade": "法器·上品", "base_atk": 18, "base_def": 15, "base_hp": 20, "bonus_exp_pct": 0},
    4: {"grade": "灵器·下品", "base_atk": 30, "base_def": 25, "base_hp": 35, "bonus_exp_pct": 0},
    5: {"grade": "灵器·上品", "base_atk": 48, "base_def": 40, "base_hp": 55, "bonus_exp_pct": 0.03},
    6: {"grade": "仙器", "base_atk": 75, "base_def": 65, "base_hp": 80, "bonus_exp_pct": 0.05},
    7: {"grade": "神器", "base_atk": 120, "base_def": 100, "base_hp": 130, "bonus_exp_pct": 0.08},
}
STAT_VARIANCE = 0.10

def generate_equip(slot, tier):
    """生成一件随机组合装备，返回 (item_id, item_dict)"""
    uid = random.randint(10000, 99999)
    rng = random.Random(uid)
    prefix_pool = EQUIP_PREFIXES.get(tier, [("无名", {})])
    prefix_name, prefix_stats = rng.choice(prefix_pool)
    mat_pool = EQUIP_MATERIALS.get(slot, {}).get(tier, ["灵物"])
    material_name = rng.choice(mat_pool)
    suffix = rng.choice({"weapon": WEAPON_SUFFIXES, "armor": ARMOR_SUFFIXES, "accessory": ACCESSORY_SUFFIXES}[slot])
    full_name = f"{prefix_name}·{material_name}{suffix}"
    tier_info = EQUIP_TIERS[tier]
    def vary(base):
        return max(1, int(base * rng.uniform(1 - STAT_VARIANCE, 1 + STAT_VARIANCE)))
    item = {"name": full_name, "type": "equip", "slot": slot, "tier": tier, "grade": tier_info["grade"], "price": 0}
    if slot == "weapon":
        item["atk"] = vary(tier_info["base_atk"]) + prefix_stats.get("atk", 0)
        item["desc"] = f"{tier_info['grade']}  攻击+{item['atk']}"
    elif slot == "armor":
        item["def"] = vary(tier_info["base_def"]) + prefix_stats.get("def", 0)
        item["desc"] = f"{tier_info['grade']}  防御+{item['def']}"
    else:
        item["atk"] = vary(tier_info["base_atk"] // 3) + prefix_stats.get("atk", 0)
        item["def"] = vary(tier_info["base_def"] // 3) + prefix_stats.get("def", 0)
        item["bonus_hp"] = vary(tier_info["base_hp"]) + prefix_stats.get("bonus_hp", 0)
        if tier_info["bonus_exp_pct"] > 0:
            item["bonus_exp_pct"] = tier_info["bonus_exp_pct"]
        parts = [tier_info["grade"]]
        if item["atk"]: parts.append(f"攻+{item['atk']}")
        if item["def"]: parts.append(f"防+{item['def']}")
        if item.get("bonus_hp"): parts.append(f"气血+{item['bonus_hp']}")
        if item.get("bonus_exp_pct"): parts.append(f"修炼+{int(item['bonus_exp_pct']*100)}%")
        item["desc"] = "  ".join(parts)
    item_id = f"gen_{slot}_{tier}_{uid}"
    return item_id, item

def lookup_item(item_id):
    """查询物品，支持固定物品和随机生成物品"""
    if item_id.startswith("gen_"):
        return _decode_gen_item(item_id)
    return ITEMS.get(item_id)

def _decode_gen_item(item_id):
    """从gen_物品ID解码出属性（用于向后兼容已有存档）"""
    parts = item_id.split("_")
    if len(parts) != 4: return None
    slot = parts[1]
    try:
        tier = int(parts[2])
    except ValueError:
        return None
    tier_info = EQUIP_TIERS.get(tier)
    if not tier_info: return None
    # 从ID中的随机数生成一个稳定的前缀
    seed = int(parts[3])
    rng = random.Random(seed)
    prefix_pool = EQUIP_PREFIXES.get(tier, [("无名", {})])
    pn, ps = rng.choice(prefix_pool)
    mp = EQUIP_MATERIALS.get(slot, {}).get(tier, ["灵物"])
    mn = rng.choice(mp)
    sf = rng.choice({"weapon": WEAPON_SUFFIXES, "armor": ARMOR_SUFFIXES, "accessory": ACCESSORY_SUFFIXES}[slot])
    name = f"{pn}·{mn}{sf}"
    item = {"name": name, "type": "equip", "slot": slot, "tier": tier, "grade": tier_info["grade"], "price": 0}
    base = lambda: rng.randint(int(1 - STAT_VARIANCE * 100), int(1 + STAT_VARIANCE * 100)) / 100
    if slot == "weapon":
        item["atk"] = max(1, int(tier_info["base_atk"] * base()) + ps.get("atk", 0))
        item["desc"] = f"{tier_info['grade']}  攻击+{item['atk']}"
    elif slot == "armor":
        item["def"] = max(1, int(tier_info["base_def"] * base()) + ps.get("def", 0))
        item["desc"] = f"{tier_info['grade']}  防御+{item['def']}"
    else:
        item["atk"] = max(0, int(tier_info["base_atk"] // 3 * base()) + ps.get("atk", 0))
        item["def"] = max(0, int(tier_info["base_def"] // 3 * base()) + ps.get("def", 0))
        item["bonus_hp"] = max(0, int(tier_info["base_hp"] * base()) + ps.get("bonus_hp", 0))
        if tier_info["bonus_exp_pct"]: item["bonus_exp_pct"] = tier_info["bonus_exp_pct"]
        parts2 = [tier_info["grade"]]
        if item["atk"]: parts2.append(f"攻+{item['atk']}")
        if item["def"]: parts2.append(f"防+{item['def']}")
        if item.get("bonus_hp"): parts2.append(f"气血+{item['bonus_hp']}")
        if item.get("bonus_exp_pct"): parts2.append(f"修炼+{int(item['bonus_exp_pct']*100)}%")
        item["desc"] = "  ".join(parts2)
    return item


# ═══════════════ 地点 ═══════════════
LOCATIONS = {
    "qingyun_town": {
        "name": "青云镇", "desc": "一座依山傍水的小镇，灵气氤氲。镇口立着一块石碑，上书「修仙路远，道心为上」。街道上修士来来往往，偶有灵鹤飞过屋檐。",
        "connections": ["luoxia_plains", "fallenwood_forest"], "safe": True,
        "npc": "接引长老", "npc_dialog": "小友，既然踏上了修仙之路，便不可懈怠。东边的落霞林灵气充裕，却也妖兽横行；北边的苍茫草原上散修出没。去历练吧，唯有历经磨难方能证道！",
    },
    "fallenwood_forest": {
        "name": "落霞林", "desc": "古木参天，灵雾弥漫。林间偶见灵草摇曳，远处传来妖兽的低吼声。落叶铺满小径，空气中弥漫着淡淡的灵气。",
        "connections": ["qingyun_town", "yaoshou_deepwood", "spirit_cave"], "safe": False,
        "monster_pool": ["green_wolf", "spirit_slime", "poison_snake", "wild_boar", "fire_rat", "blood_bat", "ironback_centipede", "rogue_cultivator"],
        "level_mod": 0,
    },
    "luoxia_plains": {
        "name": "苍茫草原", "desc": "一望无际的草原上微风拂过，远处可见几只妖兽在游荡。偶有散修在此修行，神情警觉。",
        "connections": ["qingyun_town", "cangyun_mountain"], "safe": False,
        "monster_pool": ["wild_boar", "rogue_cultivator", "fire_rat", "green_wolf", "blood_bat", "rock_beast"],
        "level_mod": 1,
    },
    "yaoshou_deepwood": {
        "name": "妖兽密林", "desc": "浓密的树冠遮天蔽日，几乎不见天光。妖气冲天，阴风阵阵。地上散落着破碎的法器残片和妖兽骨骸。",
        "connections": ["fallenwood_forest", "youming_altar"], "safe": False,
        "monster_pool": ["wolf_king", "soul_spider", "ancient_tree_demon", "stone_bear", "wind_yao", "purple_eagle", "cave_troll_yao"],
        "level_mod": 2,
    },
    "spirit_cave": {
        "name": "灵矿洞穴", "desc": "洞壁上镶嵌着微光闪烁的灵石矿脉，空气中灵气浓郁。深处传来金属敲击般的回声，偶尔夹杂妖兽的咆哮。",
        "connections": ["fallenwood_forest", "mine_depth"], "safe": False,
        "monster_pool": ["blood_bat", "stone_bear", "ironback_centipede", "cave_troll_yao", "mine_demon_chief"],
        "level_mod": 2,
    },
    "cangyun_mountain": {
        "name": "苍云山", "desc": "崎岖的山路上罡风呼啸，脚下的碎石不断滑落。远处山峰被云雾笼罩，隐约可见雷光闪烁。灵气在此汇聚，形成肉眼可见的灵雾。",
        "connections": ["luoxia_plains", "tribulation_peak"], "safe": False,
        "monster_pool": ["rock_beast", "wind_yao", "purple_eagle", "mine_demon_chief", "demonic_cultivator", "flood_dragon"],
        "level_mod": 3,
    },
    "mine_depth": {
        "name": "矿脉深处", "desc": "矿脉深处有一个巨大的地下溶洞，钟乳石上凝结着灵液，地上散落着灵石碎片和妖兽内丹。空气中杀机四伏。",
        "connections": ["spirit_cave"], "safe": False,
        "monster_pool": ["mine_demon_chief", "cave_troll_yao", "demonic_cultivator", "shadow_demon"],
        "level_mod": 3,
    },
    "youming_altar": {
        "name": "幽冥祭坛", "desc": "一座被遗忘的远古祭坛，周围飘浮着诡异的幽冥鬼火。石柱上刻满了上古魔纹，空气中弥漫着浓烈的魔气。",
        "connections": ["yaoshou_deepwood"], "safe": False,
        "monster_pool": ["demonic_cultivator", "shadow_demon", "cave_troll_yao", "mine_demon_chief"],
        "level_mod": 4,
    },
    "tribulation_peak": {
        "name": "天劫峰", "desc": "传说中渡劫飞升之地，山巅被天雷轰得焦黑，硫磺气息弥漫。地面布满雷纹，空气中电弧噼啪作响。唯有大能修士方敢踏足此地。",
        "connections": ["cangyun_mountain"], "safe": False,
        "monster_pool": ["flood_dragon", "ancient_true_dragon", "shadow_demon", "demonic_cultivator"],
        "level_mod": 5,
    },
}

# ═══════════════ 妖兽 ═══════════════
MONSTERS = {
    "green_wolf":        {"name": "青狼",       "hp": 20,  "atk": 5,  "def": 2,  "exp": 10,  "gold": 5,   "level": 1,  "level_range": (1, 3),  "element": "木"},
    "spirit_slime":      {"name": "灵液怪",     "hp": 15,  "atk": 4,  "def": 1,  "exp": 8,   "gold": 4,   "level": 1,  "level_range": (1, 2),  "element": "水"},
    "poison_snake":      {"name": "毒蟒",       "hp": 18,  "atk": 7,  "def": 1,  "exp": 12,  "gold": 6,   "level": 1,  "level_range": (1, 3),  "element": "木"},
    "fire_rat":          {"name": "火鼠",       "hp": 12,  "atk": 6,  "def": 1,  "exp": 8,   "gold": 4,   "level": 1,  "level_range": (1, 2),  "element": "火"},
    "wild_boar":         {"name": "鬃毛野猪",   "hp": 30,  "atk": 8,  "def": 4,  "exp": 15,  "gold": 8,   "level": 2,  "level_range": (1, 3),  "element": "土"},
    "rogue_cultivator":  {"name": "散修",       "hp": 25,  "atk": 10, "def": 3,  "exp": 18,  "gold": 15,  "level": 2,  "level_range": (1, 4),  "element": None},
    "blood_bat":         {"name": "噬血蝠",     "hp": 16,  "atk": 9,  "def": 1,  "exp": 10,  "gold": 5,   "level": 1,  "level_range": (1, 3),  "element": None},
    "ironback_centipede": {"name": "铁背蜈蚣",  "hp": 22,  "atk": 7,  "def": 5,  "exp": 14,  "gold": 7,   "level": 2,  "level_range": (1, 3),  "element": "金"},
    "stone_bear":        {"name": "石熊妖",     "hp": 55,  "atk": 16, "def": 8,  "exp": 35,  "gold": 22,  "level": 4,  "level_range": (3, 6),  "element": "土"},
    "wolf_king":         {"name": "灰鬃狼王",   "hp": 50,  "atk": 18, "def": 6,  "exp": 38,  "gold": 20,  "level": 5,  "level_range": (3, 7),  "element": "木"},
    "soul_spider":       {"name": "噬魂蛛",     "hp": 42,  "atk": 20, "def": 5,  "exp": 36,  "gold": 18,  "level": 5,  "level_range": (3, 7),  "element": None},
    "ancient_tree_demon": {"name": "古树妖",    "hp": 70,  "atk": 14, "def": 12, "exp": 45,  "gold": 28,  "level": 5,  "level_range": (4, 7),  "element": "木"},
    "rock_beast":        {"name": "岩角兽",     "hp": 40,  "atk": 13, "def": 8,  "exp": 22,  "gold": 12,  "level": 4,  "level_range": (3, 5),  "element": "土"},
    "wind_yao":          {"name": "风翼妖",     "hp": 48,  "atk": 20, "def": 5,  "exp": 32,  "gold": 22,  "level": 5,  "level_range": (3, 6),  "element": None},
    "purple_eagle":      {"name": "紫云鹰",     "hp": 45,  "atk": 18, "def": 5,  "exp": 30,  "gold": 20,  "level": 5,  "level_range": (4, 6),  "element": None},
    "mine_demon_chief":  {"name": "妖兵统领",   "hp": 90,  "atk": 25, "def": 10, "exp": 60,  "gold": 45,  "level": 7,  "level_range": (6, 9),  "element": None},
    "cave_troll_yao":    {"name": "洞穴巨妖",   "hp": 110, "atk": 28, "def": 14, "exp": 72,  "gold": 55,  "level": 8,  "level_range": (6, 10), "element": "土"},
    "demonic_cultivator": {"name": "魔修",      "hp": 120, "atk": 35, "def": 12, "exp": 100, "gold": 80,  "level": 10, "level_range": (8, 12), "element": None},
    "shadow_demon":      {"name": "魔族修士",   "hp": 140, "atk": 38, "def": 15, "exp": 110, "gold": 90,  "level": 11, "level_range": (9, 13), "element": None},
    "flood_dragon":      {"name": "蛟龙",       "hp": 180, "atk": 45, "def": 20, "exp": 180, "gold": 150, "level": 13, "level_range": (11, 14),"element": "水"},
    "ancient_true_dragon":{"name": "上古真龙",  "hp": 300, "atk": 60, "def": 30, "exp": 400, "gold": 300, "level": 15, "level_range": (13, 15),"element": "火"},
}

# ═══════════════ 物品 ═══════════════
ITEMS = {
    # ── 丹药·恢复气血 ──
    "huiqi_dan":     {"name": "回气丹",       "desc": "恢复30气血",                       "type": "consumable", "effect": "heal",         "value": 30,   "price": 15},
    "huichun_dan":   {"name": "回春丹",       "desc": "恢复80气血",                       "type": "consumable", "effect": "heal",         "value": 80,   "price": 40},
    "xuming_dan":    {"name": "续命丹",       "desc": "恢复200气血",                      "type": "consumable", "effect": "heal",         "value": 200,  "price": 120},
    "jiuzhuan_dan":  {"name": "九转还魂丹",   "desc": "气血完全恢复",                     "type": "consumable", "effect": "heal_full",    "value": 0,    "price": 350},
    # ── 丹药·提升修为 ──
    "peiyuan_dan":   {"name": "培元丹",       "desc": "获得50修为",                       "type": "consumable", "effect": "exp",          "value": 50,   "price": 60},
    "juling_dan":    {"name": "聚灵丹",       "desc": "获得150修为",                      "type": "consumable", "effect": "exp",          "value": 150,  "price": 200},
    "wudao_dan":     {"name": "悟道丹",       "desc": "获得400修为",                      "type": "consumable", "effect": "exp",          "value": 400,  "price": 550},
    # ── 丹药·特殊 ──
    "pojing_dan":    {"name": "破境丹",       "desc": "下次突破必定成功",                 "type": "consumable", "effect": "breakthrough", "value": 1,    "price": 500},
    "dingdan":       {"name": "凝神定魄丹",   "desc": "下次战斗伤害+30%（一次）",         "type": "consumable", "effect": "combat_buff",  "value": 30,   "price": 150},
    # ── 符箓 ──
    "liliang_fulu":  {"name": "力量符箓",     "desc": "攻击+2（永久）",                   "type": "consumable", "effect": "atk_up",       "value": 2,    "price": 100},
    "liliang_fulu2": {"name": "高级力量符箓", "desc": "攻击+5（永久）",                   "type": "consumable", "effect": "atk_up",       "value": 5,    "price": 350},
    "huti_fulu":     {"name": "护体符箓",     "desc": "防御+2（永久）",                   "type": "consumable", "effect": "def_up",       "value": 2,    "price": 100},
    "huti_fulu2":    {"name": "高级护体符箓", "desc": "防御+5（永久）",                   "type": "consumable", "effect": "def_up",       "value": 5,    "price": 350},
    "qifu_fulu":     {"name": "祈福符箓",     "desc": "气血上限+30（永久）",              "type": "consumable", "effect": "hp_up",        "value": 30,   "price": 200},
    # ── 灵草·炼丹材料 ──
    "lingcao":       {"name": "灵草",         "desc": "最常见的炼丹灵草",                 "type": "material", "price": 5},
    "bingling_cao":  {"name": "冰灵草",       "desc": "蕴含寒冰之力的灵草",               "type": "material", "price": 15},
    "huoling_hua":   {"name": "火灵花",       "desc": "生长在火山口的灵花",               "type": "material", "price": 15},
    "wanling_guo":   {"name": "万灵果",       "desc": "凝聚天地灵气的果实",               "type": "material", "price": 40},
    "dueling_teng":  {"name": "毒灵藤",       "desc": "带有剧毒的灵藤",                   "type": "material", "price": 10},
    "jiuhuan_cao":   {"name": "九转还魂草",   "desc": "传说中能起死回生的仙草",           "type": "material", "price": 120},
    "longxian_cao":  {"name": "龙涎草",       "desc": "吸收龙族气息而生的稀世灵草",       "type": "material", "price": 150},
    "fengxue_hua":   {"name": "凤血花",       "desc": "凤凰精血浇灌而成的绝世灵花",       "type": "material", "price": 180},
    # ── 矿石·材料 ──
    "hantie_kuang":  {"name": "寒铁矿",       "desc": "蕴含寒气的铁矿石",                 "type": "material", "price": 12},
    "xuanjin_shi":   {"name": "玄晶石",       "desc": "灵力凝聚而成的晶体矿石",           "type": "material", "price": 30},
    "tianwai_yuntie":{"name": "天外陨铁",     "desc": "来自域外的神秘金属",               "type": "material", "price": 100},
    "zijin_kuang":   {"name": "紫金矿",       "desc": "紫色光芒流转的极品矿石",           "type": "material", "price": 200},
    # ── 妖兽材料 ──
    "yaodan":        {"name": "妖兽内丹",     "desc": "妖兽体内的灵力结晶",               "type": "material", "price": 25},
    "yaogu":         {"name": "妖兽骨骼",     "desc": "坚硬的妖兽骨骼，可用于炼器",       "type": "material", "price": 15},
    "yaopimo":       {"name": "妖兽皮毛",     "desc": "带有灵力的妖兽皮毛",               "type": "material", "price": 20},
    # ── 炼器基础装备（坊市可购，用于过渡）──
    "tiemu_sword":   {"name": "铁木剑",       "desc": "凡器·下品  攻击+3",   "type": "equip", "slot": "weapon", "atk": 3,   "price": 30},
    "cloth_robe":    {"name": "粗布道袍",     "desc": "凡器       防御+3",   "type": "equip", "slot": "armor", "def": 3,   "price": 35},
    "qingyu_peidai": {"name": "青玉佩",       "desc": "凡器       攻击+2 气血+10", "type": "equip", "slot": "accessory", "atk": 2, "bonus_hp": 10, "price": 80},
    "tongqian_hufu": {"name": "铜钱护符",     "desc": "凡器       防御+2 气血+10", "type": "equip", "slot": "accessory", "def": 2, "bonus_hp": 10, "price": 80},
}

# 掉落表：monster_id -> [(item_id, 概率)]
DROP_TABLE = {
    # 一阶妖兽 (练气期 1-3)
    "green_wolf":        [("huiqi_dan", 0.3), ("lingcao", 0.25), ("yaogu", 0.08)],
    "spirit_slime":      [("huiqi_dan", 0.2), ("lingcao", 0.15)],
    "poison_snake":      [("huiqi_dan", 0.3), ("dueling_teng", 0.15), ("yaopimo", 0.08)],
    "fire_rat":          [("huiqi_dan", 0.2), ("huoling_hua", 0.15)],
    "wild_boar":         [("huiqi_dan", 0.4), ("cloth_robe", 0.1), ("lingcao", 0.25), ("yaogu", 0.1)],
    "rogue_cultivator":  [("huiqi_dan", 0.3), ("tiemu_sword", 0.1), ("liliang_fulu", 0.05), ("hantie_kuang", 0.1)],
    "blood_bat":         [("huiqi_dan", 0.25), ("dueling_teng", 0.1), ("yaopimo", 0.1)],
    "ironback_centipede": [("huiqi_dan", 0.3), ("cloth_robe", 0.08), ("lingcao", 0.2), ("hantie_kuang", 0.1)],
    # 二阶妖兽 (筑基期 4-6)
    "stone_bear":        [("huichun_dan", 0.3), ("lingwen_armor", 0.1), ("bingling_cao", 0.15), ("yaogu", 0.12), ("hantie_kuang", 0.1)],
    "wolf_king":         [("huichun_dan", 0.3), ("hantie_sword", 0.1), ("lingcao", 0.2), ("yaodan", 0.06)],
    "soul_spider":       [("huichun_dan", 0.3), ("liliang_fulu", 0.05), ("dueling_teng", 0.15), ("yaopimo", 0.1)],
    "ancient_tree_demon":[("huichun_dan", 0.4), ("huti_fulu", 0.08), ("wanling_guo", 0.1), ("yaogu", 0.1)],
    "rock_beast":        [("huiqi_dan", 0.4), ("hantie_sword", 0.08), ("bingling_cao", 0.1), ("hantie_kuang", 0.15)],
    "wind_yao":          [("huichun_dan", 0.3), ("liliang_fulu", 0.05), ("huoling_hua", 0.1), ("yaopimo", 0.08)],
    "purple_eagle":      [("huichun_dan", 0.3), ("peiyuan_dan", 0.1), ("wanling_guo", 0.1), ("yaodan", 0.08)],
    # 三阶妖兽 (结丹期 7-9)
    "mine_demon_chief":  [("hantie_sword", 0.12), ("lingwen_armor", 0.1), ("liliang_fulu", 0.05), ("bingling_cao", 0.15), ("xuanjin_shi", 0.08), ("yaodan", 0.1)],
    "cave_troll_yao":    [("qinggang_sword", 0.08), ("xuantie_armor", 0.06), ("huichun_dan", 0.4), ("wanling_guo", 0.12), ("xuanjin_shi", 0.1), ("yaodan", 0.12)],
    # 四阶妖兽 (元婴期 10-11)
    "demonic_cultivator":[("liliang_fulu", 0.1), ("qinggang_sword", 0.08), ("pojing_dan", 0.02), ("huoling_hua", 0.1), ("tianwai_yuntie", 0.06), ("jiuhuan_cao", 0.05)],
    "shadow_demon":      [("zhanlong_sword", 0.04), ("longlin_armor", 0.03), ("pojing_dan", 0.03), ("wanling_guo", 0.1), ("tianwai_yuntie", 0.08), ("longxian_cao", 0.04)],
    # 五阶妖兽 (化神+ 12+)
    "flood_dragon":      [("longlin_armor", 0.05), ("huichun_dan", 0.5), ("pojing_dan", 0.05), ("wanling_guo", 0.2), ("longxian_cao", 0.08), ("zijin_kuang", 0.06)],
    "ancient_true_dragon":[("zhanlong_sword", 0.12), ("longlin_armor", 0.08), ("pojing_dan", 0.1), ("liliang_fulu", 0.15), ("huti_fulu", 0.15), ("wanling_guo", 0.25), ("fengxue_hua", 0.08), ("zijin_kuang", 0.1)],
}

# ═══════════════ 怪物生成 ═══════════════
LEVEL_SCALE_PER_LV = 0.08

def spawn_monster(monster_id, player_level=None):
    base = MONSTERS[monster_id]
    if player_level is not None:
        actual_lv = max(1, player_level + random.randint(-2, 2))
    else:
        lv_min, lv_max = base["level_range"]
        actual_lv = random.randint(lv_min, lv_max)
    diff = actual_lv - base["level"]
    factor = max(0.5, 1 + diff * LEVEL_SCALE_PER_LV)
    return {
        "id": monster_id, "name": base["name"], "level": actual_lv,
        "hp": max(1, int(base["hp"] * factor)),
        "atk": max(1, int(base["atk"] * factor)),
        "def": max(0, int(base["def"] * factor)),
        "exp": max(1, int(base["exp"] * factor)),
        "gold": max(1, int(base["gold"] * factor)),
        "element": base.get("element"),
    }
