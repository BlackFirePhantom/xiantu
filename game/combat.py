"""仙途游戏 - 战斗文案"""

import random


# ═══════════════ 战斗文案 ═══════════════

ATTACK_VERBS = [
    "催动灵力，一掌拍向{m}", "祭出飞剑，剑光一闪斩向{m}",
    "凝聚灵力于拳，轰向{m}", "掐动法诀，一道灵光射向{m}",
    "运转功法，灵力化作刀芒劈向{m}",
]
MONSTER_ATTACK_VERBS = [
    "{m}怒吼一声，一爪拍来", "{m}张口喷出一道妖气",
    "{m}浑身妖力暴涨，猛扑过来", "{m}凝聚妖力，化作暗影袭来",
]


def fmt_attack(n):
    return random.choice(ATTACK_VERBS).format(m=n)


def fmt_monster_attack(n):
    return random.choice(MONSTER_ATTACK_VERBS).format(m=n)
