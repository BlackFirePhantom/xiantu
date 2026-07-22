from services.player_state import build_player_state


def test_player_state_projection_is_transport_independent(make_char):
    character = make_char(
        name="归一道人",
        techniques='["modao_rumen"]',
        open_meridians='["ren_mai"]',
    )

    state = build_player_state(
        character,
        {"huiqi_dan": 2},
        online_count=3,
        is_afk=True,
    )

    assert set(state) == {
        "char",
        "spirit_root",
        "techniques",
        "meridians",
        "location",
        "inventory",
        "equipment",
        "pets",
        "npcs",
        "quests",
        "sect",
        "online_count",
        "is_afk",
    }
    assert state["char"]["name"] == "归一道人"
    assert state["inventory"][0]["id"] == "huiqi_dan"
    assert state["inventory"][0]["count"] == 2
    assert state["online_count"] == 3
    assert state["is_afk"] is True


def test_player_state_projection_ignores_unknown_inventory_and_equipment(make_char):
    character = make_char(weapon="missing_weapon")

    state = build_player_state(character, {"missing_item": 9})

    assert state["inventory"] == []
    assert state["equipment"] == {
        "weapon": None,
        "armor": None,
        "accessory": None,
    }
