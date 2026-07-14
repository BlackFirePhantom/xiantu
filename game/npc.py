"""NPC 系统逻辑"""

import random
import json
from datetime import datetime, timezone
from game_data import ITEMS, MONSTERS, LOCATIONS, realm_name
from npc_data import NPCS, QUESTS, NPC_GOODWILL_TIERS, get_goodwill_tier, get_sect_rank


def get_npc_info_for_location(char):
    """获取当前地点的 NPC 信息"""
    loc_id = char["location"]
    goodwill = json.loads(char["npc_goodwill"]) if char["npc_goodwill"] else {}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    gift_dates = json.loads(char["npc_gift_date"]) if char["npc_gift_date"] else {}
    result = []
    for nid, npc in NPCS.items():
        if npc["location"] != loc_id:
            continue
        gw = goodwill.get(nid, 0)
        tier = get_goodwill_tier(gw)
        dialogues = npc["dialogues"].get(tier, npc["dialogues"][0])
        realm_text = ""
        for (lo, hi), text in npc.get("realm_dialogues", {}).items():
            if lo <= char["level"] <= hi:
                realm_text = text
                break
        can_gift = gift_dates.get(nid) != today
        result.append({
            "id": nid, "name": npc["name"], "title": npc["title"],
            "type": npc["type"], "realm": realm_name(npc["realm"]),
            "goodwill": gw, "goodwill_tier": tier,
            "goodwill_tier_name": NPC_GOODWILL_TIERS[tier]["name"],
            "dialogue": random.choice(dialogues),
            "realm_dialogue": realm_text,
            "can_gift": can_gift,
        })
    return result


def get_quest_info(char):
    """获取当前活跃任务信息"""
    active = json.loads(char["active_quests"]) if char["active_quests"] else []
    completed = json.loads(char["completed_quests"]) if char["completed_quests"] else []
    result = []
    for q in active:
        quest = QUESTS.get(q["id"])
        if not quest:
            continue
        progress = []
        for obj_type, obj_data in quest["objectives"].items():
            if obj_type == "kill":
                for mid, need in obj_data.items():
                    done = q["progress"].get(f"kill_{mid}", 0)
                    progress.append({"desc": f"击杀{MONSTERS.get(mid, {}).get('name', mid)}", "done": done, "need": need})
            elif obj_type == "collect":
                for iid, need in obj_data.items():
                    done = q["progress"].get(f"collect_{iid}", 0)
                    progress.append({"desc": f"收集{ITEMS.get(iid, {}).get('name', iid)}", "done": done, "need": need})
            elif obj_type == "visit":
                for lid in obj_data:
                    done = q["progress"].get(f"visit_{lid}", 0)
                    progress.append({"desc": f"到达{LOCATIONS.get(lid, {}).get('name', lid)}", "done": 1 if done else 0, "need": 1})
            elif obj_type == "kill_any":
                done = q["progress"].get("kill_any", 0)
                progress.append({"desc": "击杀任意妖兽", "done": done, "need": obj_data})
        result.append({"id": q["id"], "name": quest["name"], "desc": quest["desc"], "npc": quest["npc"], "progress": progress})
    return {"active": result, "completed_count": len(completed)}


def get_sect_info(char):
    """获取宗门信息"""
    contrib = char["sect_contrib"] if char["sect_contrib"] else 0
    rank = get_sect_rank(contrib)
    from npc_data import SECT_RANKS
    return {
        "contrib": contrib, "rank": rank,
        "rank_name": SECT_RANKS[rank]["name"],
        "bonus": SECT_RANKS[rank]["bonus"],
        "desc": SECT_RANKS[rank]["desc"],
    }


def interact_with_npc(char, uid, nid):
    """与 NPC 交互，返回结果 dict"""
    if not nid or nid not in NPCS:
        return {"success": False, "message": "此人查无此名。"}
    npc = NPCS[nid]
    if npc["location"] != char["location"]:
        return {"success": False, "message": "此地并无此人。"}

    gw = json.loads(char["npc_goodwill"]) if char["npc_goodwill"] else {}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    gift_dates = json.loads(char["npc_gift_date"]) if char["npc_gift_date"] else {}
    daily_key = f"daily_{nid}"

    goodwill_changed = False
    if gift_dates.get(daily_key) != today:
        gw[nid] = gw.get(nid, 0) + 1
        gift_dates[daily_key] = today
        goodwill_changed = True

    goodwill = gw.get(nid, 0)
    tier = get_goodwill_tier(goodwill)
    dialogues = npc["dialogues"].get(tier, npc["dialogues"][0])
    realm_text = ""
    for (lo, hi), text in npc.get("realm_dialogues", {}).items():
        if lo <= char["level"] <= hi:
            realm_text = text
            break

    completed = json.loads(char["completed_quests"]) if char["completed_quests"] else []
    active = json.loads(char["active_quests"]) if char["active_quests"] else []
    active_ids = [q["id"] for q in active]
    available_quests = []
    for qid, q in QUESTS.items():
        if q["npc"] != nid:
            continue
        if qid in active_ids:
            continue
        if not q["daily"] and qid in completed:
            continue
        if char["level"] < q["req_realm"]:
            continue
        available_quests.append({
            "id": qid, "name": q["name"], "desc": q["desc"], "daily": q["daily"],
            "accept_text": q.get("accept_text", ""),
        })

    return {
        "success": True,
        "goodwill_changed": goodwill_changed,
        "updated_goodwill": gw,
        "updated_gift_dates": gift_dates,
        "detail": {
            "id": nid, "name": npc["name"], "title": npc["title"],
            "type": npc["type"], "goodwill": goodwill, "goodwill_tier": tier,
            "goodwill_tier_name": NPC_GOODWILL_TIERS[tier]["name"],
            "dialogue": random.choice(dialogues),
            "realm_dialogue": realm_text,
            "available_quests": available_quests,
            "gift_preferences": npc.get("gift_preferences", {}),
        },
    }


def give_npc_gift(char, inv, nid, item_id):
    """赠礼给 NPC，返回结果 dict"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    gift_dates = json.loads(char["npc_gift_date"]) if char["npc_gift_date"] else {}
    if gift_dates.get(nid) == today:
        return {"success": False, "message": "今日已经赠过礼了，明日再来。"}

    if inv.get(item_id, 0) <= 0:
        return {"success": False, "message": "你没有这个物品。"}

    npc = NPCS.get(nid)
    if not npc:
        return {"success": False, "message": "此人查无此名。"}

    prefs = npc.get("gift_preferences", {})
    if item_id in prefs.get("liked", []):
        change = prefs.get("liked_value", 3)
    elif item_id in prefs.get("disliked", []):
        change = prefs.get("disliked_value", -2)
    else:
        change = 1

    inv[item_id] -= 1
    if inv[item_id] <= 0:
        del inv[item_id]

    gw = json.loads(char["npc_goodwill"]) if char["npc_goodwill"] else {}
    gw[nid] = max(0, gw.get(nid, 0) + change)
    gift_dates[nid] = today

    item_name = ITEMS.get(item_id, {}).get("name", item_id)
    if change > 0:
        message = f"你将【{item_name}】赠予{npc['name']}，好感度+{change}。"
    else:
        message = f"你将【{item_name}】赠予{npc['name']}，但对方似乎不太喜欢……好感度{change}。"

    return {
        "success": True, "message": message,
        "updated_inv": inv, "updated_goodwill": gw, "updated_gift_dates": gift_dates,
    }


def accept_quest(char, qid):
    """接受任务，返回结果 dict"""
    if not qid or qid not in QUESTS:
        return {"success": False, "message": "此任务查无此名。"}
    quest = QUESTS[qid]
    if char["level"] < quest["req_realm"]:
        return {"success": False, "message": f"境界不足，需要{realm_name(quest['req_realm'])}。"}
    active = json.loads(char["active_quests"]) if char["active_quests"] else []
    if any(q["id"] == qid for q in active):
        return {"success": False, "message": "你已经接了这个任务。"}
    completed = json.loads(char["completed_quests"]) if char["completed_quests"] else []
    if not quest["daily"] and qid in completed:
        return {"success": False, "message": "这个任务已经完成过了。"}
    active.append({"id": qid, "progress": {}})
    return {
        "success": True,
        "message": quest.get("accept_text", f"接受了任务：{quest['name']}"),
        "updated_active_quests": active,
    }


def complete_quest(char, qid):
    """完成任务，返回结果 dict"""
    if not qid or qid not in QUESTS:
        return {"success": False, "message": "此任务查无此名。"}
    quest = QUESTS[qid]
    active = json.loads(char["active_quests"]) if char["active_quests"] else []
    target = None
    for q in active:
        if q["id"] == qid:
            target = q
            break
    if not target:
        return {"success": False, "message": "你没有接这个任务。"}

    for obj_type, obj_data in quest["objectives"].items():
        if obj_type in ("kill", "collect"):
            for mid, need in obj_data.items():
                key = f"{obj_type}_{mid}"
                if target["progress"].get(key, 0) < need:
                    return {"success": False, "message": "任务目标尚未完成。"}
        elif obj_type == "visit":
            for lid in obj_data:
                if not target["progress"].get(f"visit_{lid}", 0):
                    return {"success": False, "message": "任务目标尚未完成。"}
        elif obj_type == "kill_any":
            if target["progress"].get("kill_any", 0) < obj_data:
                return {"success": False, "message": "任务目标尚未完成。"}

    rewards = quest["rewards"]
    gw = json.loads(char["npc_goodwill"]) if char["npc_goodwill"] else {}
    for npc_id, gw_change in rewards.get("goodwill", {}).items():
        gw[npc_id] = gw.get(npc_id, 0) + gw_change

    new_active = [q for q in active if q["id"] != qid]
    completed = json.loads(char["completed_quests"]) if char["completed_quests"] else []
    if not quest["daily"]:
        completed.append(qid)

    reward_text = (
        f"获得 {rewards.get('exp', 0)} 修为、{rewards.get('gold', 0)} 灵石"
        + (f"、宗门贡献+{rewards.get('sect_contrib', 0)}" if rewards.get("sect_contrib") else "")
    )

    return {
        "success": True,
        "message": quest.get("complete_text", f"完成任务：{quest['name']}！"),
        "reward_text": reward_text,
        "exp_gain": rewards.get("exp", 0),
        "gold_gain": rewards.get("gold", 0),
        "sect_contrib_gain": rewards.get("sect_contrib", 0),
        "goodwill_changes": rewards.get("goodwill", {}),
        "updated_goodwill": gw,
        "updated_active_quests": new_active,
        "updated_completed_quests": completed,
        "item_rewards": rewards.get("items", {}),
    }


def check_quest_progress(char, event_type, key, count=1):
    """检查并更新任务进度，返回 (changed, updated_active)"""
    active = json.loads(char["active_quests"]) if char["active_quests"] else []
    changed = False
    for q in active:
        quest = QUESTS.get(q["id"])
        if not quest:
            continue
        for obj_type, obj_data in quest["objectives"].items():
            if event_type == "kill" and obj_type == "kill" and key in obj_data:
                pkey = f"kill_{key}"
                q["progress"][pkey] = q["progress"].get(pkey, 0) + count
                changed = True
            elif event_type == "kill" and obj_type == "kill_any":
                q["progress"]["kill_any"] = q["progress"].get("kill_any", 0) + count
                changed = True
            elif event_type == "collect" and obj_type == "collect" and key in obj_data:
                pkey = f"collect_{key}"
                q["progress"][pkey] = q["progress"].get(pkey, 0) + count
                changed = True
            elif event_type == "visit" and obj_type == "visit" and key in obj_data:
                q["progress"][f"visit_{key}"] = 1
                changed = True
    return changed, active
