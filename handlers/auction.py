"""拍卖行事件与后台竞拍自动逻辑的 Socket 处理器。"""

import time
import random
import uuid as _uuid
from flask import session
from flask_socketio import emit

from game_state import (
    get_cached_character as get_character,
    update_cached_character as update_character,
    get_character_inventory_cached as get_character_inventory,
    set_character_inventory_cached as set_character_inventory
)
from game_data import ITEMS, AUCTION_POOL, AUCTION_NPC

# 导入其它 Handler 提供的功能
from handlers.base import do_get_state

def _item_name(item_id):
    """获取物品名称（优先从ITEMS，再从坊市静态列表）"""
    if item_id in ITEMS:
        return ITEMS[item_id]["name"]
    _shop_names = {
        "liliang_fulu2": "高级力量符箓", "huti_fulu2": "高级护体符箓",
        "qifu_fulu": "祈福符箓", "pet_feed_good": "高级灵兽粮",
        "pet_feed_best": "万灵精华",
    }
    return _shop_names.get(item_id, item_id)

def _refresh_auctions():
    """刷新拍卖行：随机上架新拍品"""
    now = time.time() * 1000  # ms
    game_state.auction_last_refresh = now
    # 移除已结束超过5分钟的拍品
    to_del = [k for k, v in game_state.active_auctions.items() if v.get("won") and now - v.get("ends_at", 0) > 300000]
    for k in to_del:
        del game_state.active_auctions[k]

    # 随机选取新拍品上架
    for pool_item in AUCTION_POOL:
        if random.random() > pool_item["prob"]:
            continue
        # 检查是否已有同类拍品
        if any(a["item_id"] == pool_item["id"] and a["rarity"] == pool_item["rarity"] and not a.get("won") for a in game_state.active_auctions.values()):
            continue
        low, high = pool_item["base_price"]
        start_price = random.randint(low, high)
        min_incr = max(10, start_price // 10)
        aid = _uuid.uuid4().hex[:8]
        duration = random.randint(90, 180) * 1000  # 90~180秒
        game_state.active_auctions[aid] = {
            "auction_id": aid,
            "item_id": pool_item["id"],
            "name": _item_name(pool_item["id"]),
            "desc": pool_item["desc"],
            "rarity": pool_item["rarity"],
            "start_price": start_price,
            "current_price": start_price,
            "min_increment": min_incr,
            "highest_bidder": None,   # "player" / "npc" / None
            "bids_player": 0,
            "bids_npc": 0,
            "ends_at": now + duration,
            "won": False,
            "sold_to_npc": False,
            "created_at": now,
        }
        # NPC延迟出价
        npc_interest = AUCTION_NPC["interest"].get(pool_item["rarity"], {})
        if random.random() < npc_interest.get("chance", 0.3):
            npc_delay = random.randint(AUCTION_NPC["bid_delay"][0], AUCTION_NPC["bid_delay"][1])
            game_state.active_auctions[aid]["npc_bid_at"] = now + npc_delay * 1000
            game_state.active_auctions[aid]["npc_max_bids"] = npc_interest.get("max_bids", 2)
            game_state.active_auctions[aid]["npc_max_pct"] = npc_interest.get("max_pct", 1.3)

def _npc_may_bid(auction):
    """NPC决定是否出价"""
    npc = game_state.auction_npc_state
    if not npc:
        return False
    if npc["total_spent"] >= npc["budget"]:
        return False
    if auction.get("won") or auction.get("sold_to_npc"):
        return False
    bids = auction.get("bids_npc", 0)
    if bids >= auction.get("npc_max_bids", 2):
        return False
    max_price = int(auction["start_price"] * auction.get("npc_max_pct", 1.3))
    if auction["current_price"] >= max_price:
        return False
    if npc["budget"] - npc["total_spent"] < auction["current_price"] + auction["min_increment"]:
        return False
    return True

def _npc_do_bid(auction):
    """NPC执行出价"""
    increment = auction["min_increment"] * (1 + random.randint(0, 2))
    new_price = auction["current_price"] + increment
    max_price = int(auction["start_price"] * auction.get("npc_max_pct", 1.3))
    new_price = min(new_price, max_price)
    if new_price <= auction["current_price"]:
        return False
    auction["current_price"] = new_price
    auction["highest_bidder"] = "npc"
    auction["bids_npc"] = auction.get("bids_npc", 0) + 1
    return True

def _process_auction_ticks():
    """后台循环：处理NPC出价、拍卖结束、4小时自动刷新"""
    while True:
        if game_state.socketio:
            game_state.socketio.sleep(3)
        else:
            time.sleep(3)
            
        now = time.time() * 1000

        # 4小时自动刷新拍品
        if now - game_state.auction_last_refresh >= game_state.AUCTION_REFRESH_INTERVAL:
            _refresh_auctions()
            if game_state.socketio:
                game_state.socketio.emit("auction_log", {"text": "天机拍卖行新一批宝物上架了！", "type": "shop"}, namespace="/")
                game_state.socketio.emit("auction_update", {}, namespace="/")

        changed = False
        for aid, a in list(game_state.active_auctions.items()):
            if a.get("won") or a.get("sold_to_npc"):
                continue
            # 检查拍卖是否结束
            if now >= a["ends_at"]:
                if a["highest_bidder"] == "player":
                    # 玩家拍得：扣灵石 + 发放物品
                    uid = a.get("player_user_id")
                    if uid:
                        char = get_character(uid)
                        if char and char["gold"] >= a["current_price"]:
                            update_character(uid, gold=char["gold"] - a["current_price"])
                            inv = get_character_inventory(uid)
                            inv[a["item_id"]] = inv.get(a["item_id"], 0) + 1
                            set_character_inventory(uid, inv)
                            if game_state.socketio:
                                game_state.socketio.emit("auction_log", {"text": f"你拍得了【{a['name']}】，扣除 {a['current_price']} 灵石！", "type": "shop"}, namespace="/")
                        elif char:
                            if game_state.socketio:
                                game_state.socketio.emit("auction_log", {"text": f"你拍得了【{a['name']}】但灵石不足，拍品流拍！", "type": "error"}, namespace="/")
                    a["won"] = True
                    if game_state.socketio:
                        game_state.socketio.emit("auction_update", {"auction_id": aid}, namespace="/")
                elif a["highest_bidder"] == "npc":
                    a["sold_to_npc"] = True
                    game_state.auction_npc_state["total_spent"] += a["current_price"]
                    if game_state.socketio:
                        game_state.socketio.emit("auction_log", {"text": f"【{a['name']}】被金算盘以{a['current_price']}灵石拍走！", "type": "info"}, namespace="/")
                        game_state.socketio.emit("auction_update", {"auction_id": aid}, namespace="/")
                else:
                    # 无人出价，流拍
                    a["won"] = True
                changed = True
                continue
            # NPC延迟出价
            npc_bid_at = a.get("npc_bid_at")
            if npc_bid_at and now >= npc_bid_at and _npc_may_bid(a):
                if _npc_do_bid(a):
                    a["npc_bid_at"] = now + random.randint(5, 15) * 1000  # 下次出价延迟
                    if game_state.socketio:
                        game_state.socketio.emit("auction_log", {"text": f"金算盘对【{a['name']}】出价 {a['current_price']} 灵石！", "type": "info"}, namespace="/")
                        game_state.socketio.emit("auction_update", {"auction_id": aid}, namespace="/")
                    changed = True
            # 拍卖即将结束时NPC最后一搏
            time_left = a["ends_at"] - now
            if 0 < time_left < 15000 and a["highest_bidder"] == "player" and _npc_may_bid(a):
                if random.random() < 0.6:
                    if _npc_do_bid(a):
                        if game_state.socketio:
                            game_state.socketio.emit("auction_log", {"text": f"金算盘在最后关头抢价【{a['name']}】→ {a['current_price']}灵石！", "type": "info"}, namespace="/")
                            game_state.socketio.emit("auction_update", {"auction_id": aid}, namespace="/")
                        changed = True

def register_auction_handlers(socketio):
    @socketio.on("get_auction")
    def handle_get_auction():
        if "user_id" not in session: return
        # 首次打开或拍品为空时初始化
        if not game_state.active_auctions:
            _refresh_auctions()
        now = time.time() * 1000
        items = []
        for aid, a in sorted(game_state.active_auctions.items(), key=lambda x: x[1].get("created_at", 0)):
            items.append({
                "auction_id": a["auction_id"],
                "item_id": a["item_id"],
                "name": a["name"],
                "desc": a["desc"],
                "rarity": a["rarity"],
                "current_price": a["current_price"],
                "min_increment": a["min_increment"],
                "highest_bidder": a["highest_bidder"],
                "ends_at": a["ends_at"],
                "won": a.get("won", False),
                "sold_to_npc": a.get("sold_to_npc", False),
                "player_won": a.get("won") and a["highest_bidder"] == "player",
            })
        next_refresh = game_state.auction_last_refresh + game_state.AUCTION_REFRESH_INTERVAL
        emit("auction_list", {"items": items, "next_refresh": next_refresh})

    @socketio.on("auction_bid")
    def handle_auction_bid(data):
        if "user_id" not in session: return
        game_state.touch_activity(session.get("username", ""))
        char = get_character(session["user_id"])
        if not char: return

        aid = data.get("auction_id")
        amount = data.get("amount", 0)
        if not aid or aid not in game_state.active_auctions:
            emit("game_msg", {"text": "该拍品已不存在。", "type": "error"})
            return

        a = game_state.active_auctions[aid]
        if a.get("won") or a.get("sold_to_npc"):
            emit("game_msg", {"text": "该拍品已成交。", "type": "error"})
            return

        now = time.time() * 1000
        if now >= a["ends_at"]:
            emit("game_msg", {"text": "拍卖已结束。", "type": "error"})
            return

        min_bid = a["current_price"] + a["min_increment"]
        if amount < min_bid:
            emit("game_msg", {"text": f"出价不得低于 {min_bid} 灵石。", "type": "error"})
            return

        if amount > char["gold"]:
            emit("game_msg", {"text": f"灵石不足！你只有 {char['gold']} 灵石。", "type": "error"})
            return

        # 记录出价（不扣灵石，成交时才扣）
        a["current_price"] = amount
        a["highest_bidder"] = "player"
        a["bids_player"] = a.get("bids_player", 0) + 1
        a["player_user_id"] = session["user_id"]

        # 延长拍卖时间（防止最后秒杀）
        time_left = a["ends_at"] - now
        if time_left < 20000:
            a["ends_at"] = now + 20000

        # NPC可能加价
        npc_interest = AUCTION_NPC["interest"].get(a["rarity"], {})
        if random.random() < npc_interest.get("chance", 0.3) and _npc_may_bid(a):
            npc_delay = random.randint(AUCTION_NPC["bid_delay"][0], AUCTION_NPC["bid_delay"][1])
            a["npc_bid_at"] = now + npc_delay * 1000

        emit("game_msg", {"text": f"你对【{a['name']}】出价 {amount} 灵石！", "type": "shop"})
        socketio.emit("auction_update", {"auction_id": aid}, namespace="/")
        do_get_state(session["user_id"])
