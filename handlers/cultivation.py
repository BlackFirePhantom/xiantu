"""修真、境界突破、功法及经脉系统的 Socket 事件处理器。"""

import json
import random
import logging
from flask import session
from flask_socketio import emit

import game_state
from game_state import (
    get_cached_character as get_character,
    update_cached_character as update_character,
    get_character_inventory_cached as get_character_inventory,
    set_character_inventory_cached as set_character_inventory
)
from game_data import (
    LOCATIONS, SPIRIT_ROOTS, TECHNIQUES, MERIDIANS, ITEMS, ALIGNMENT_CONFLICTS,
    MAX_LEVEL, EXP_PER_LEVEL, BREAKTHROUGH_CHANCE, TECHNIQUE_MAX_PROFICIENCY,
    realm_name
)
from game.utils import get_full_stats, gain_proficiency, get_exp_needed
from game.cultivation import attempt_breakthrough

# 导入其它 Handler 的功能
from handlers.base import do_get_state

logger = logging.getLogger("xiantu.handlers.cultivation")

def register_cultivation_handlers(socketio):
    @socketio.on("meditate")
    def handle_meditate():
        if "user_id" not in session: return
        game_state.touch_activity(session.get("username", ""))
        char = get_character(session["user_id"])
        if not char: return
        loc = LOCATIONS.get(char["location"], LOCATIONS["qingyun_town"])
        if not loc["safe"]:
            emit("game_msg", {"text": "此处妖气弥漫，无法静心打做。", "type": "error"})
            return
        stats = get_full_stats(char)
        # 熟练度增长
        prof_gained = gain_proficiency(char, session["user_id"], source="meditate")
        prof_parts = [f"{TECHNIQUES[tid]['name']}+{amt}" for tid, amt in prof_gained.items() if tid in TECHNIQUES]
        prof_msg = f" 熟练度提升（{', '.join(prof_parts)}）。" if prof_parts else ""

        update_character(session["user_id"], hp=stats["max_hp"], mp=stats.get("max_mp", 50))

        msgs = [
            f"你盘膝而坐，运转功法，天地灵气涌入体内……气血完全恢复，灵力充盈。{prof_msg}",
            f"你闭目凝神，灵力缓缓流转，伤势痊愈，气血充盈，灵力回满。{prof_msg}",
            f"你静心打坐，体悟天地大道，灵台清明，气血恢复如初，灵力充沛。{prof_msg}",
        ]
        emit("game_msg", {"text": random.choice(msgs), "type": "heal"})
        do_get_state(session["user_id"])

    @socketio.on("breakthrough")
    def handle_breakthrough():
        if "user_id" not in session: return
        char = get_character(session["user_id"])
        if not char: return
        cur_lv = char["level"]
        if cur_lv >= MAX_LEVEL:
            emit("game_msg", {"text": "你已是大乘期修士，前方唯有飞升一途。", "type": "info"})
            return
        needed = get_exp_needed(cur_lv)
        if needed == "-" or char["exp"] < needed:
            emit("game_msg", {"text": f"修为不足，无法尝试突破。需要 {needed} 修为。", "type": "error"})
            return

        base_chance = BREAKTHROUGH_CHANCE.get(cur_lv, 0.5)
        if char["has_breakthrough_pill"]:
            chance = 1.0
            update_character(session["user_id"], has_breakthrough_pill=0)
            pill_msg = "你服下破境丹，灵台通明，突破毫无阻碍！"
        else:
            chance = base_chance
            pill_msg = ""

        # 突破直接消耗修为
        new_exp = char["exp"] - needed
        update_character(session["user_id"], exp=max(0, new_exp))

        emit("game_msg", {"text": f"你盘膝坐下，消耗 {needed} 修为，运转功法尝试突破……", "type": "info"})
        if pill_msg:
            emit("game_msg", {"text": pill_msg, "type": "buff"})

        result = attempt_breakthrough(char, needed, chance)
        if result["success"]:
            new_lv = result["new_level"]
            new_stats = result["new_stats"]
            update_character(session["user_id"], level=new_lv, max_hp=new_stats["max_hp"], atk=new_stats["atk"], def_stat=new_stats["def_stat"], hp=new_stats["max_hp"])
            new_realm = realm_name(new_lv)
            logger.info("突破成功：%s -> %s (Lv.%d)", session.get("username"), new_realm, new_lv)
            emit("game_msg", {"text": f"体内灵力暴涌，丹田剧烈震动--突破成功！你已迈入{new_realm}！", "type": "heal"})
            emit("system_msg", {"text": f"天道感应：{session.get('username')} 突破至 {new_realm}，引发天地异象！"}, broadcast=True, namespace="/")
        else:
            hp_loss = result["hp_loss"]
            fail_msgs = [
                f"灵力逆行，经脉受损……突破失败！{needed} 修为化为乌有。",
                f"丹田中灵力暴走，冲击境界失败，{needed} 修为付诸东流！",
                f"天地灵气反噬，境界壁垒纹丝不动，{needed} 修为消散于天地间。",
                f"关键时刻心魔入侵，突破功亏一篑，{needed} 修为烟消云散。",
            ]
            emit("game_msg", {"text": random.choice(fail_msgs), "type": "error"})
            update_character(session["user_id"], hp=max(1, char["hp"] - hp_loss))
        do_get_state(session["user_id"])

    @socketio.on("get_techniques")
    def handle_get_techniques():
        if "user_id" not in session: return
        char = get_character(session["user_id"])
        if not char: return
        learned = json.loads(char["techniques"]) if char["techniques"] else []
        sr_id = char["spirit_root"]
        sr = SPIRIT_ROOTS.get(sr_id, {})
        sr_element = sr.get("element")
        is_tian = sr_id in ("tian", "huntian")

        available = []
        for tid, t in TECHNIQUES.items():
            if tid in learned: continue
            if t.get("fragment_only"): continue

            cost_gold = t.get("cost_gold", t["req_realm"] * 50)
            cost_items = t.get("cost_items", {})

            # 检查所有条件
            reasons = []
            can_learn = True
            if char["level"] < t["req_realm"]:
                reasons.append(f"需{realm_name(t['req_realm'])}")
                can_learn = False
            if t.get("req_element") and not is_tian and sr_element != t["req_element"]:
                reasons.append(f"需{t['req_element']}灵根")
                can_learn = False
            if t.get("req_technique") and t["req_technique"] not in learned:
                pre_name = TECHNIQUES.get(t["req_technique"], {}).get("name", "?")
                reasons.append(f"需先学{pre_name}")
                can_learn = False
            if char["gold"] < cost_gold:
                reasons.append(f"需{cost_gold}灵石")
                can_learn = False
            for iid, cnt in cost_items.items():
                reasons.append(f"需{ITEMS.get(iid,{}).get('name','?')}x{cnt}")

            alignment = t.get("alignment", "中立")
            # 检查正魔道冲突
            has_conflict = False
            if alignment != "中立":
                for lid in learned:
                    lt = TECHNIQUES.get(lid, {})
                    la = lt.get("alignment", "中立")
                    if la != "中立" and la != alignment:
                        has_conflict = True
                        break

            available.append({
                "id": tid, "name": t["name"], "tier": t["tier"], "desc": t["desc"],
                "req_realm": realm_name(t["req_realm"]), "cost_gold": cost_gold,
                "cost_items": [{"name": ITEMS.get(iid,{}).get("name","?"), "need": cnt} for iid, cnt in cost_items.items()],
                "req_element": t.get("req_element"),
                "req_technique": t.get("req_technique"),
                "alignment": alignment,
                "reasons": reasons,
                "can_learn": can_learn,
                "has_conflict": has_conflict,
            })
        emit("techniques_list", {"available": available, "learned": learned})

    @socketio.on("learn_technique")
    def handle_learn_technique(data):
        if "user_id" not in session: return
        char = get_character(session["user_id"])
        if not char: return
        tid = data.get("technique")
        if not tid or tid not in TECHNIQUES:
            return
        t = TECHNIQUES[tid]
        learned = json.loads(char["techniques"]) if char["techniques"] else []

        if tid in learned:
            emit("game_msg", {"text": f"你已经领悟了【{t['name']}】。", "type": "error"})
            return
        if t.get("fragment_only"):
            emit("game_msg", {"text": f"【{t['name']}】只能通过集齐残卷领悟。", "type": "error"})
            return
        if char["level"] < t["req_realm"]:
            emit("game_msg", {"text": f"境界不足，需要{realm_name(t['req_realm'])}才能领悟。", "type": "error"})
            return
        if t.get("req_element"):
            sr_id = char["spirit_root"]
            sr = SPIRIT_ROOTS.get(sr_id, {})
            sr_element = sr.get("element")
            if sr_element != t["req_element"] and sr_id != "tian" and sr_id != "huntian":
                emit("game_msg", {"text": f"灵根不符，需要{t['req_element']}灵根才能修炼此功法。你的灵根属性为{sr_element or '无属性'}。", "type": "error"})
                return
        if t.get("req_technique"):
            if t["req_technique"] not in learned:
                pre = TECHNIQUES.get(t["req_technique"], {})
                emit("game_msg", {"text": f"需要先领悟【{pre.get('name', t['req_technique'])}】。", "type": "error"})
                return
        cost_gold = t.get("cost_gold", t["req_realm"] * 50)
        if char["gold"] < cost_gold:
            emit("game_msg", {"text": f"参悟功法需要 {cost_gold} 灵石，灵石不足。", "type": "error"})
            return
        cost_items = t.get("cost_items", {})
        if cost_items:
            inv = get_character_inventory(session["user_id"])
            for iid, cnt in cost_items.items():
                if inv.get(iid, 0) < cnt:
                    emit("game_msg", {"text": f"需要【{ITEMS.get(iid,{}).get('name',iid)}】x{cnt}，材料不足。", "type": "error"})
                    return
            for iid, cnt in cost_items.items():
                inv[iid] -= cnt
                if inv[iid] <= 0: del inv[iid]
            set_character_inventory(session["user_id"], inv)
        if t.get("alignment") and t["alignment"] != "中立":
            for lid in learned:
                lt = TECHNIQUES.get(lid, {})
                la = lt.get("alignment", "中立")
                if la != "中立" and la != t["alignment"]:
                    conflict_key = (la, t["alignment"])
                    if ALIGNMENT_CONFLICTS.get(conflict_key, 0) > 0:
                        emit("game_msg", {"text": f"警告：【{t['name']}】（{t['alignment']}）与已学【{lt['name']}】（{la}）存在道法冲突！同时修炼可能影响突破。", "type": "error"})

        learned.append(tid)
        update_character(session["user_id"], techniques=json.dumps(learned), gold=char["gold"] - cost_gold)
        emit("game_msg", {"text": f"你耗费 {cost_gold} 灵石，潜心参悟，终于领悟了【{t['name']}】（{t['tier']}）！", "type": "buff"})
        do_get_state(session["user_id"])

    @socketio.on("get_meridians")
    def handle_get_meridians():
        if "user_id" not in session: return
        char = get_character(session["user_id"])
        if not char: return
        opened = json.loads(char["open_meridians"]) if char["open_meridians"] else []
        available = []
        for mid, m in MERIDIANS.items():
            status = "opened" if mid in opened else ("unlockable" if char["level"] >= m["req_realm"] and char["exp"] >= m["cost"] else "locked")
            available.append({
                "id": mid, "name": m["name"], "desc": m["desc"], "cost": m["cost"],
                "req_realm": realm_name(m["req_realm"]), "status": status,
                "bonus": f"气血+{m['bonus_hp']} 攻击+{m['bonus_atk']} 防御+{m['bonus_def']}"
            })
        emit("meridians_list", {"data": available, "opened": opened})

    @socketio.on("open_meridian")
    def handle_open_meridian(data):
        if "user_id" not in session: return
        char = get_character(session["user_id"])
        if not char: return
        mid = data.get("meridian")
        if not mid or mid not in MERIDIANS:
            return
        m = MERIDIANS[mid]
        opened = json.loads(char["open_meridians"]) if char["open_meridians"] else []
        if mid in opened:
            emit("game_msg", {"text": f"你的{m['name']}已经打通。", "type": "error"})
            return
        if char["level"] < m["req_realm"]:
            emit("game_msg", {"text": f"境界不足，需要{realm_name(m['req_realm'])}才能打通。", "type": "error"})
            return
        if char["exp"] < m["cost"]:
            emit("game_msg", {"text": f"打通{m['name']}需要 {m['cost']} 修为，修为不足。", "type": "error"})
            return
        opened.append(mid)
        update_character(session["user_id"], open_meridians=json.dumps(opened), exp=char["exp"] - m["cost"])
        emit("game_msg", {"text": f"你消耗 {m['cost']} 修为，冲击{m['name']}……经脉畅通，灵力大增！", "type": "buff"})
        do_get_state(session["user_id"])
