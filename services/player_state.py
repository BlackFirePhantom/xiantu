"""Transport-independent player state projections."""

import json

from game.npc import get_npc_info_for_location, get_quest_info, get_sect_info
from game.pet import get_pet_display_info
from game.utils import get_cultivation_mult, get_exp_needed, get_full_stats, get_proficiency
from game_data import (
    LOCATIONS,
    MERIDIANS,
    SPIRIT_ROOTS,
    TECHNIQUES,
    TECHNIQUE_MAX_PROFICIENCY,
    lookup_item,
    realm_name,
)


def _inventory_state(inventory):
    items = []
    for item_id, count in inventory.items():
        item = lookup_item(item_id)
        if item:
            items.append({
                "id": item_id,
                "name": item["name"],
                "count": count,
                "desc": item.get("desc", ""),
                "type": item.get("type", "misc"),
                "slot": item.get("slot"),
            })
    return items


def _equipment_state(character):
    equipment = {"weapon": None, "armor": None, "accessory": None}
    for slot in equipment:
        item_id = character.get(slot)
        item = lookup_item(item_id) if item_id else None
        if item:
            equipment[slot] = {
                "id": item_id,
                "name": item["name"],
                "desc": item.get("desc", ""),
                "slot": item.get("slot", slot),
            }
    return equipment


def _spirit_root_state(character):
    spirit_root_id = character.get("spirit_root")
    spirit_root = SPIRIT_ROOTS.get(spirit_root_id)
    if not spirit_root:
        return None
    return {
        "id": spirit_root_id,
        "name": spirit_root["name"],
        "desc": spirit_root["desc"],
        "element": spirit_root["element"],
    }


def _technique_state(character):
    proficiency = get_proficiency(character)
    learned = json.loads(character["techniques"]) if character.get("techniques") else []
    techniques = []
    for technique_id in learned:
        technique = TECHNIQUES.get(technique_id)
        if not technique:
            continue
        value = proficiency.get(technique_id, 0)
        techniques.append({
            "id": technique_id,
            "name": technique["name"],
            "tier": technique["tier"],
            "proficiency": value,
            "max_proficiency": TECHNIQUE_MAX_PROFICIENCY,
            "prof_pct": round(value / TECHNIQUE_MAX_PROFICIENCY * 100),
        })
    return techniques


def _meridian_state(character):
    opened = json.loads(character["open_meridians"]) if character.get("open_meridians") else []
    return [
        {"id": meridian_id, "name": MERIDIANS[meridian_id]["name"]}
        for meridian_id in opened
        if meridian_id in MERIDIANS
    ]


def build_player_state(character, inventory, *, online_count=0, is_afk=False):
    """Build the stable ``game_state`` payload without Flask or Socket.IO."""
    location = LOCATIONS.get(character["location"], LOCATIONS["qingyun_town"])
    stats = get_full_stats(character)
    max_mp = stats.get("max_mp", 50)
    connections = [
        {"id": location_id, "name": LOCATIONS[location_id]["name"]}
        for location_id in location["connections"]
        if location_id in LOCATIONS
    ]
    return {
        "char": {
            "name": character["name"],
            "level": character["level"],
            "realm": realm_name(character["level"]),
            "exp": character["exp"],
            "exp_needed": get_exp_needed(character["level"]),
            "hp": character["hp"],
            "max_hp": stats["max_hp"],
            "mp": character.get("mp", max_mp),
            "max_mp": max_mp,
            "atk": stats["atk"],
            "def": stats["def"],
            "gold": character["gold"],
            "kills": character["kills"],
            "deaths": character["deaths"],
            "has_breakthrough_pill": character["has_breakthrough_pill"],
            "cultivation_mult": round(get_cultivation_mult(character), 2),
        },
        "spirit_root": _spirit_root_state(character),
        "techniques": _technique_state(character),
        "meridians": _meridian_state(character),
        "location": {
            "id": character["location"],
            "name": location["name"],
            "desc": location["desc"],
            "safe": location["safe"],
            "connections": connections,
            "npc": location.get("npc"),
            "npc_dialog": location.get("npc_dialog"),
        },
        "inventory": _inventory_state(inventory),
        "equipment": _equipment_state(character),
        "pets": get_pet_display_info(character),
        "npcs": get_npc_info_for_location(character),
        "quests": get_quest_info(character),
        "sect": get_sect_info(character),
        "online_count": online_count,
        "is_afk": is_afk,
    }
