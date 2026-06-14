"""拍卖行系统逻辑"""

import random
import time
import uuid
from game_data import ITEMS


def _item_name(item_id):
    """获取物品名称"""
    if item_id in ITEMS:
        return ITEMS[item_id]["name"]
    _shop_names = {
        "liliang_fulu2": "高级力量符箓", "huti_fulu2": "高级护体符箓",
        "qifu_fulu": "祈福符箓", "pet_feed_good": "高级灵兽粮",
        "pet_feed_best": "万灵精华",
    }
    return _shop_names.get(item_id, item_id)


# 拍卖品池
AUCTION_POOL = [
    {"id": "xuming_dan",     "rarity": "rare", "base_price": (200, 350),   "prob": 0.7, "desc": "恢复200气血"},
    {"id": "juling_dan",     "rarity": "rare", "base_price": (300, 500),   "prob": 0.7, "desc": "获得150修为"},
    {"id": "liliang_fulu2",  "rarity": "rare", "base_price": (400, 600),   "prob": 0.6, "desc": "攻击+5(永久)"},
    {"id": "huti_fulu2",     "rarity": "rare", "base_price": (400, 600),   "prob": 0.6, "desc": "防御+5(永久)"},
    {"id": "qifu_fulu",      "rarity": "rare", "base_price": (300, 500),   "prob": 0.6, "desc": "气血+30(永久)"},
    {"id": "egg_rare",       "rarity": "rare", "base_price": (400, 650),   "prob": 0.6, "desc": "孵化稀有灵宠概率更高"},
    {"id": "pet_feed_good",  "rarity": "rare", "base_price": (120, 200),   "prob": 0.7, "desc": "灵宠经验+50"},
    {"id": "map_rare",       "rarity": "rare", "base_price": (350, 550),   "prob": 0.6, "desc": "二档宝藏"},
    {"id": "jiuzhuan_dan",   "rarity": "rare", "base_price": (500, 800),   "prob": 0.5, "desc": "气血完全恢复"},
    {"id": "wudao_dan",      "rarity": "epic", "base_price": (700, 1100),  "prob": 0.4, "desc": "获得400修为"},
    {"id": "pojing_dan",     "rarity": "epic", "base_price": (800, 1200),  "prob": 0.35,"desc": "突破必定成功"},
    {"id": "egg_legend",     "rarity": "epic", "base_price": (1200, 1800), "prob": 0.35,"desc": "必定孵化稀有以上"},
    {"id": "pet_feed_best",  "rarity": "epic", "base_price": (500, 800),   "prob": 0.4, "desc": "灵宠经验+200"},
    {"id": "map_legend",     "rarity": "epic", "base_price": (1000, 1500), "prob": 0.3, "desc": "三档宝藏"},
    {"id": "wudao_dan",      "rarity": "legend", "base_price": (1500, 2500), "prob": 0.15, "desc": "获得400修为（极品）"},
    {"id": "pojing_dan",     "rarity": "legend", "base_price": (2000, 3500), "prob": 0.12, "desc": "突破必定成功（绝品）"},
    {"id": "egg_legend",     "rarity": "legend", "base_price": (2500, 4000), "prob": 0.10, "desc": "传说灵兽蛋（万年难遇）"},
    {"id": "jiuzhuan_dan",   "rarity": "legend", "base_price": (1800, 3000), "prob": 0.12, "desc": "九转还魂丹（起死回生）"},
]

# 拍卖 NPC 竞拍者配置
AUCTION_NPC = {
    "name": "金算盘",
    "title": "天机拍卖行大掌柜",
    "budget": 15000,
    "interest": {
        "rare":   {"chance": 0.5,  "max_bids": 2, "max_pct": 1.3},
        "epic":   {"chance": 0.7,  "max_bids": 3, "max_pct": 1.5},
        "legend": {"chance": 0.85, "max_bids": 4, "max_pct": 2.0},
    },
    "bid_delay": (3, 12),
}


def npc_may_bid(auction, npc_state):
    """NPC 决定是否出价"""
    if npc_state["total_spent"] >= npc_state["budget"]:
        return False
    if auction.get("won") or auction.get("sold_to_npc"):
        return False
    bids = auction.get("bids_npc", 0)
    if bids >= auction.get("npc_max_bids", 2):
        return False
    max_price = int(auction["start_price"] * auction.get("npc_max_pct", 1.3))
    if auction["current_price"] >= max_price:
        return False
    if npc_state["budget"] - npc_state["total_spent"] < auction["current_price"] + auction["min_increment"]:
        return False
    return True


def npc_do_bid(auction):
    """NPC 执行出价"""
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
