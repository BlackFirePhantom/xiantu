"""奇遇事件和突发事件处理逻辑"""

import random
from game_data import (
    FORTUNE_EVENTS, SURPRISE_EVENTS, ITEMS, TECHNIQUES,
)
from game.utils import get_full_stats
from models import update_character, get_character_inventory, set_character_inventory


def check_fortune(char):
    """奇遇判定，返回触发的事件或 None"""
    for event in FORTUNE_EVENTS:
        if random.random() < event["chance"]:
            return {
                "title": event["title"],
                "text": event["text"],
                "choices": [{"index": i, "text": c["text"]} for i, c in enumerate(event["choices"])],
                "event_id": event["id"],
            }
    return None


def process_surprise(char, trigger):
    """处理突发事件，返回结果 dict 或 None"""
    for evt in SURPRISE_EVENTS:
        if evt["trigger"] != trigger or random.random() >= evt["chance"]:
            continue

        result = {
            "text": f"【突发】{evt['text']}",
            "effect": evt.get("eff", evt.get("effect")),
        }

        eff = evt.get("effect")
        if eff == "extra_fight":
            result["action"] = "extra_fight"
        elif eff == "exp_boost":
            gain = random.randint(*evt["value_range"])
            result["action"] = "exp_boost"
            result["gain"] = gain
        elif eff == "gold_gain":
            gain = random.randint(*evt["value_range"])
            result["action"] = "gold_gain"
            result["gain"] = gain
        elif eff == "herb_gain":
            herb = random.choice(evt["herb_pool"])
            count = random.randint(*evt["count_range"])
            result["action"] = "herb_gain"
            result["herb"] = herb
            result["count"] = count
        elif eff == "heal_partial":
            stats = get_full_stats(char)
            heal = random.randint(*evt["value_range"])
            result["action"] = "heal_partial"
            result["heal"] = heal
            result["max_hp"] = stats["max_hp"]
        elif eff == "storm":
            stats = get_full_stats(char)
            hp_loss = int(stats["max_hp"] * evt["hp_loss_pct"])
            exp_gain = random.randint(*evt["exp_gain_range"])
            result["action"] = "storm"
            result["hp_loss"] = hp_loss
            result["exp_gain"] = exp_gain
        elif eff == "item_gain":
            result["action"] = "item_gain"
            result["item"] = evt["item"]
            result["count"] = evt["count"]
        elif eff == "loot_cache":
            result["action"] = "loot_cache"
            result["items"] = evt["items"]
            result["gold_range"] = evt["gold_range"]
        elif eff == "material_gain":
            mat = random.choice(evt["mat_pool"])
            count = random.randint(*evt["count_range"])
            result["action"] = "material_gain"
            result["mat"] = mat
            result["count"] = count

        return result
    return None


def _try_learn_technique(char, uid):
    """尝试随机学习一门功法，返回 (success, tech_id_or_none)"""
    import json
    learned = json.loads(char["techniques"]) if char["techniques"] else []
    available = [tid for tid, t in TECHNIQUES.items() if tid not in learned and char["level"] >= t["req_realm"]]
    if available:
        chosen = random.choice(available)
        learned.append(chosen)
        update_character(uid, techniques=json.dumps(learned))
        return True, chosen
    return False, None


def _give_random_item(uid, pool=None):
    """随机给一个物品，返回 item_id"""
    if pool is None:
        pool = [("peiyuan_dan", 0.3), ("huichun_dan", 0.3), ("liliang_fulu", 0.15), ("huti_fulu", 0.15), ("pojing_dan", 0.1)]
    r = random.random()
    cum = 0
    chosen = pool[0][0]
    for item_id, chance in pool:
        cum += chance
        if r < cum:
            chosen = item_id
            break
    inv = get_character_inventory(uid)
    inv[chosen] = inv.get(chosen, 0) + 1
    set_character_inventory(uid, inv)
    return chosen


def process_fortune_outcome(char, outcome, uid):
    """处理奇遇事件的选项结果，返回 list of message dicts"""
    messages = []

    def msg(text, mtype="info"):
        messages.append({"text": text, "type": mtype})

    if outcome == "nothing":
        msg("你谨慎地选择了离开。")

    elif outcome == "heal_full":
        stats = get_full_stats(char)
        update_character(uid, hp=stats["max_hp"])
        msg("你运转功法调息，气血完全恢复，灵台一片清明。", "heal")

    elif outcome == "reward_random":
        item_id = _give_random_item(uid)
        msg(f"你获得了一枚【{ITEMS[item_id]['name']}】！", "shop")

    elif outcome == "reward_technique":
        ok, tid = _try_learn_technique(char, uid)
        if ok:
            t = TECHNIQUES[tid]
            msg(f"你领悟了【{t['name']}】（{t['tier']}）！", "buff")
        else:
            gold_gain = random.randint(50, 150)
            update_character(uid, gold=char["gold"] + gold_gain)
            msg(f"虽未领悟功法，但你感悟颇多，获得 {gold_gain} 灵石。", "shop")

    elif outcome == "reward_technique_or_item":
        ok, tid = _try_learn_technique(char, uid)
        if ok:
            t = TECHNIQUES[tid]
            msg(f"你领悟了【{t['name']}】（{t['tier']}）！", "buff")
        else:
            item_id = _give_random_item(uid)
            msg(f"你获得了一枚【{ITEMS[item_id]['name']}】！", "shop")

    elif outcome == "reward_technique_or_exp":
        ok, tid = _try_learn_technique(char, uid)
        if ok:
            t = TECHNIQUES[tid]
            msg(f"你领悟了【{t['name']}】（{t['tier']}）！", "buff")
        else:
            gain = random.randint(50, 120)
            update_character(uid, exp=char["exp"] + gain)
            msg(f"虽未领悟功法，但老者的点拨让你感悟颇深，修为提升 {gain}！", "buff")

    elif outcome == "reward_technique_or_gold":
        ok, tid = _try_learn_technique(char, uid)
        if ok:
            t = TECHNIQUES[tid]
            msg(f"你领悟了【{t['name']}】（{t['tier']}）！", "buff")
        else:
            gold_gain = random.randint(60, 180)
            update_character(uid, gold=char["gold"] + gold_gain)
            msg(f"此人感激涕零，将全部身家 {gold_gain} 灵石赠予你。", "shop")

    elif outcome == "reward_exp_small":
        gain = random.randint(15, 40)
        update_character(uid, exp=char["exp"] + gain)
        msg(f"你略有所悟，修为提升 {gain}。", "buff")

    elif outcome == "reward_exp_big":
        gain = random.randint(40, 100)
        update_character(uid, exp=char["exp"] + gain)
        msg(f"你感悟颇深，灵力涌入丹田，修为提升 {gain}！", "buff")

    elif outcome == "reward_exp_huge":
        gain = random.randint(100, 300)
        update_character(uid, exp=char["exp"] + gain)
        msg(f"天地法则涌入你的识海，修为暴涨 {gain}！丹田中灵力翻涌不止！", "buff")

    elif outcome == "reward_exp_big_or_damage":
        if random.random() < 0.5:
            gain = random.randint(40, 100)
            update_character(uid, exp=char["exp"] + gain)
            msg(f"老者目光一闪，一道灵力涌入你的识海——修为提升 {gain}！「不错，有胆识。」", "buff")
        else:
            stats = get_full_stats(char)
            dmg = stats["max_hp"] // 6
            new_hp = max(1, char["hp"] - dmg)
            update_character(uid, hp=new_hp)
            msg(f"老者轻哼一声，一股无形的压力将你震退——你受到 {dmg} 点伤害。「不知天高地厚。」", "error")

    elif outcome == "reward_exp_huge_or_trap":
        if random.random() < 0.4:
            gain = random.randint(100, 300)
            update_character(uid, exp=char["exp"] + gain)
            msg(f"你成功深入遗迹核心，获得上古大能的残余传承——修为暴涨 {gain}！", "buff")
        else:
            stats = get_full_stats(char)
            dmg = stats["max_hp"] // 3
            new_hp = max(1, char["hp"] - dmg)
            update_character(uid, hp=new_hp)
            msg(f"遗迹中的阵法突然发动！一道灵光击中你——受到 {dmg} 点伤害，你狼狈逃出。", "error")

    elif outcome == "reward_item_huichun":
        inv = get_character_inventory(uid)
        inv["huichun_dan"] = inv.get("huichun_dan", 0) + 2
        set_character_inventory(uid, inv)
        msg("你装了两瓶灵泉水，效果堪比【回春丹】。", "shop")

    elif outcome == "reward_item_peiyuan":
        inv = get_character_inventory(uid)
        inv["peiyuan_dan"] = inv.get("peiyuan_dan", 0) + 1
        set_character_inventory(uid, inv)
        msg("你获得了一枚散发着清香的【培元丹】！", "shop")

    elif outcome == "reward_item_peiyuan_or_pojing":
        if random.random() < 0.3:
            inv = get_character_inventory(uid)
            inv["pojing_dan"] = inv.get("pojing_dan", 0) + 1
            set_character_inventory(uid, inv)
            msg("你以灵力探入石珠，珠中竟封印着一枚【破境丹】！此物价值连城！", "shop")
        else:
            inv = get_character_inventory(uid)
            inv["peiyuan_dan"] = inv.get("peiyuan_dan", 0) + 2
            set_character_inventory(uid, inv)
            msg("石珠解封后化作两枚【培元丹】，也算不错。", "shop")

    elif outcome == "reward_item_multiple":
        inv = get_character_inventory(uid)
        for item_id in random.sample(["huiqi_dan", "huichun_dan", "peiyuan_dan", "lingcao", "bingling_cao"], 3):
            inv[item_id] = inv.get(item_id, 0) + 1
        set_character_inventory(uid, inv)
        update_character(uid, gold=char["gold"] - 50)
        msg("你花了50灵石买了好几样东西，其中混着那枚石珠。收获颇丰。", "shop")

    elif outcome == "reward_item_or_nothing":
        if random.random() < 0.5:
            item_id = _give_random_item(uid, [("peiyuan_dan", 0.4), ("pojing_dan", 0.1), ("juling_dan", 0.3), ("wudao_dan", 0.2)])
            msg(f"你获得了一枚【{ITEMS[item_id]['name']}】！", "shop")
        else:
            msg("你犹豫太久，玉简已被他人拍走。", "error")

    elif outcome == "reward_item_rare":
        inv = get_character_inventory(uid)
        rare = random.choice(["pojing_dan", "juling_dan", "wudao_dan", "jiuzhuan_dan"])
        inv[rare] = inv.get(rare, 0) + 1
        set_character_inventory(uid, inv)
        msg(f"玉佩灵光一闪，化作一枚【{ITEMS[rare]['name']}】落入你掌中。因果了却，灵台通明。", "shop")

    elif outcome == "reward_item_rare_or_trap":
        if random.random() < 0.5:
            inv = get_character_inventory(uid)
            rare = random.choice(["wanling_guo", "longxian_cao", "fengxue_hua"])
            inv[rare] = inv.get(rare, 0) + 2
            set_character_inventory(uid, inv)
            msg(f"鸟卵中蕴含着浓郁灵气，化作两株【{ITEMS[rare]['name']}】。", "shop")
        else:
            stats = get_full_stats(char)
            dmg = stats["max_hp"] // 4
            new_hp = max(1, char["hp"] - dmg)
            update_character(uid, hp=new_hp)
            msg(f"你刚伸手，青鸾暴怒之下一爪拍来！受到 {dmg} 点伤害，你仓皇逃走。", "error")

    elif outcome == "reward_item_scroll":
        inv = get_character_inventory(uid)
        scroll = random.choice(["liliang_fulu", "huti_fulu", "qifu_fulu"])
        inv[scroll] = inv.get(scroll, 0) + 1
        set_character_inventory(uid, inv)
        msg(f"你拓印了壁画内容，制成一枚【{ITEMS[scroll]['name']}】。", "shop")

    elif outcome == "reward_herbs":
        inv = get_character_inventory(uid)
        herbs = random.choice(["lingcao", "bingling_cao", "huoling_hua"])
        count = random.randint(2, 4)
        inv[herbs] = inv.get(herbs, 0) + count
        set_character_inventory(uid, inv)
        msg(f"你悄悄采摘了 {count} 株【{ITEMS[herbs]['name']}】，巨蟒并未察觉。", "shop")

    elif outcome == "reward_herbs_rare":
        inv = get_character_inventory(uid)
        rare = random.choice(["wanling_guo", "longxian_cao", "fengxue_hua"])
        inv[rare] = inv.get(rare, 0) + 1
        set_character_inventory(uid, inv)
        msg(f"你以一枚回气丹换取巨蟒的信任，它竟从谷底叼来一株【{ITEMS[rare]['name']}】赠你。", "shop")

    elif outcome == "reward_herbs_poison_or_fight":
        if random.random() < 0.6:
            inv = get_character_inventory(uid)
            inv["dueling_teng"] = inv.get("dueling_teng", 0) + 3
            inv["bingling_cao"] = inv.get("bingling_cao", 0) + 1
            set_character_inventory(uid, inv)
            msg("你屏息潜入，成功采得毒灵藤x3和冰灵草x1，迅速撤离。", "shop")
        else:
            msg("你刚靠近毒灵藤，沼泽中一头毒蟒猛然窜出！", "error")
            return messages, "fight"

    elif outcome in ("reward_gold_bad", "reward_gold_small"):
        gain = random.randint(20, 60)
        update_character(uid, gold=char["gold"] + gain)
        msg(f"你获得 {gain} 灵石。", "shop")

    elif outcome == "reward_gold_big_or_trap":
        if random.random() < 0.4:
            gold_gain = random.randint(100, 300)
            inv = get_character_inventory(uid)
            for mid in random.sample(["yaodan", "yaogu", "yaopimo"], 2):
                inv[mid] = inv.get(mid, 0) + 2
            set_character_inventory(uid, inv)
            update_character(uid, gold=char["gold"] + gold_gain)
            msg(f"储物戒指中竟有 {gold_gain} 灵石和大量妖兽材料！你发财了！", "shop")
        else:
            stats = get_full_stats(char)
            dmg = stats["max_hp"] // 3
            new_hp = max(1, char["hp"] - dmg)
            update_character(uid, hp=new_hp)
            msg(f"你刚触碰飞剑，洞府中沉寂万年的守护阵法轰然发动！一道灵光击中你——受到 {dmg} 点伤害。", "error")

    elif outcome == "reward_materials":
        inv = get_character_inventory(uid)
        for mid in random.sample(["hantie_kuang", "xuanjin_shi", "yaodan"], 2):
            inv[mid] = inv.get(mid, 0) + random.randint(1, 3)
        set_character_inventory(uid, inv)
        msg("你小心收集了陨落之地散落的矿石和材料。", "shop")

    elif outcome == "reward_materials_or_trap":
        if random.random() < 0.5:
            inv = get_character_inventory(uid)
            for mid in random.sample(["xuanjin_shi", "tianwai_yuntie", "yaodan"], 2):
                inv[mid] = inv.get(mid, 0) + random.randint(1, 2)
            set_character_inventory(uid, inv)
            msg("你破解了阵法，搜刮了洞府中的矿石和材料。", "shop")
        else:
            stats = get_full_stats(char)
            dmg = stats["max_hp"] // 4
            new_hp = max(1, char["hp"] - dmg)
            update_character(uid, hp=new_hp)
            msg(f"你触碰物品的瞬间，噬灵阵轰然发动！受到 {dmg} 点伤害，你拼命逃出。", "error")

    elif outcome == "reward_materials_rare":
        inv = get_character_inventory(uid)
        inv["tianwai_yuntie"] = inv.get("tianwai_yuntie", 0) + 2
        inv["zijin_kuang"] = inv.get("zijin_kuang", 0) + 1
        set_character_inventory(uid, inv)
        update_character(uid, exp=char["exp"] + random.randint(30, 80))
        msg("你第一个赶到陨落之地，拾得天外陨铁x2、紫金矿x1，混沌之气令修为精进！", "shop")

    elif outcome == "trap_damage":
        stats = get_full_stats(char)
        dmg = stats["max_hp"] // 4
        new_hp = max(1, char["hp"] - dmg)
        update_character(uid, hp=new_hp)
        msg(f"你强行破阵，受到 {dmg} 点伤害，总算逃出生天。", "error")

    elif outcome == "trap_damage_big":
        stats = get_full_stats(char)
        dmg = stats["max_hp"] // 3
        new_hp = max(1, char["hp"] - dmg)
        update_character(uid, hp=new_hp)
        msg(f"丹药入喉，化作一股灼热的毒气侵蚀经脉——受到 {dmg} 点伤害！你猛然惊醒，心魔消散。", "error")

    elif outcome == "trap_pay":
        cost = min(char["gold"], random.randint(20, 80))
        update_character(uid, gold=char["gold"] - cost)
        msg(f"你丢下 {cost} 灵石，趁机脱身。", "error")

    elif outcome in ("fight_bandit", "fight_demon_boss"):
        return messages, "fight"

    elif outcome == "reward_egg_common":
        inv = get_character_inventory(uid)
        inv["egg_common"] = inv.get("egg_common", 0) + 1
        set_character_inventory(uid, inv)
        msg("你小心翼翼地将灵兽蛋收入储物袋。回去后可以尝试孵化。", "shop")

    elif outcome == "reward_egg_rare":
        inv = get_character_inventory(uid)
        inv["egg_rare"] = inv.get("egg_rare", 0) + 1
        set_character_inventory(uid, inv)
        msg("你将这枚灵气氤氲的灵兽蛋收入囊中，心中一阵激动。", "shop")

    elif outcome == "reward_egg_rare_or_fight":
        if random.random() < 0.4:
            inv = get_character_inventory(uid)
            inv["egg_rare"] = inv.get("egg_rare", 0) + 1
            set_character_inventory(uid, inv)
            msg("母兽归来，见你并无恶意，竟将一枚灵兽蛋推向你——它似乎在托付自己的孩子。", "shop")
        else:
            msg("母兽归来，见你站在洞口，怒吼一声扑了过来！", "error")
            return messages, "fight"

    elif outcome == "reward_egg_legend_or_rare":
        if random.random() < 0.3:
            inv = get_character_inventory(uid)
            inv["egg_legend"] = inv.get("egg_legend", 0) + 1
            set_character_inventory(uid, inv)
            msg("灵力探入蛋壳，你感应到一股磅礴的生命力——这竟是一枚传说级灵兽蛋！", "buff")
        else:
            inv = get_character_inventory(uid)
            inv["egg_rare"] = inv.get("egg_rare", 0) + 1
            set_character_inventory(uid, inv)
            msg("灵力探查后确认这是一枚品质不错的灵兽蛋，收入囊中。", "shop")

    else:
        msg("你平静地离开了。", "info")

    return messages, None
