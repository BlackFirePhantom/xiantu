"""
仙途事件集 — 灵感源自修仙小说经典桥段
奇遇事件(FORTUNE_EVENTS): 移动时触发，有选择分支
突发事件(SURPRISE_EVENTS): 移动/战斗中触发，直接生效
"""

# ══════════════════════════════════════════════════════════════
#                          奇 遇 事 件
#   每个事件：title / text / choices[{text, outcome}]
#   outcome 值: reward_xxx / fight / nothing / heal_full / trap_xxx
# ══════════════════════════════════════════════════════════════

FORTUNE_EVENTS = [
    # ── 01 崖底奇缘 ──────────────────────────────────────
    {
        "id": "cliff_cave",
        "trigger": "move", "chance": 0.06,
        "title": "崖底奇缘",
        "text": (
            "你行至一处断崖，脚下碎石松动，身形一个不稳便坠了下去。"
            "耳畔风声如刀，眼前天旋地转——"
            "不知过了多久，身下传来一声沉闷的撞击，竟是落入一潭幽碧寒泉之中。"
            "你挣扎着浮出水面，抬头望去，崖壁之上竟有一处隐秘洞穴，"
            "洞口石壁上刻着几个古篆——「有缘者入」。"
        ),
        "choices": [
            {"text": "进入洞穴探查", "outcome": "reward_technique_or_item"},
            {"text": "在寒泉中运功疗伤", "outcome": "heal_full"},
            {"text": "沿崖壁攀爬离开", "outcome": "nothing"},
        ],
    },
    # ── 02 神秘老者 ──────────────────────────────────────
    {
        "id": "mysterious_elder",
        "trigger": "move", "chance": 0.05,
        "title": "松下棋局",
        "text": (
            "山道尽头，一棵古松下盘坐着一位白发老者。"
            "他面容枯槁，衣衫褴褛，身前摆着一壶浊酒，正对着棋盘独自对弈。"
            "你路过他身旁时，他忽然开口：「小友，可愿与老夫下一局？」"
            "他的目光浑浊，但你心中却莫名一凛——此人气息深不可测，仿佛与天地融为一体。"
        ),
        "choices": [
            {"text": "恭敬应允，陪老者下棋", "outcome": "reward_technique_or_exp"},
            {"text": "婉言拒绝，继续赶路", "outcome": "nothing"},
            {"text": "暗中试探老者修为", "outcome": "reward_exp_big_or_damage"},
        ],
    },
    # ── 03 古修士洞府 ────────────────────────────────────
    {
        "id": "ancient_cave",
        "trigger": "move", "chance": 0.05,
        "title": "古修士洞府",
        "text": (
            "你拨开一人高的荒草，眼前赫然出现一道石门。"
            "门上灵纹早已暗淡，却仍隐隐散发着一股古朴苍凉的气息。"
            "你以灵力推门而入，洞府内竟以夜明珠镶满穹顶，光华流转如星河。"
            "正中央的玉台上，一具白骨盘膝而坐，骨手中紧握一柄飞剑。"
            "白骨面前的石桌上，摆着三样物事：一枚储物戒指、一卷兽皮古籍、一只封印的玉瓶。"
        ),
        "choices": [
            {"text": "恭敬行礼后逐一检查", "outcome": "reward_random"},
            {"text": "先研读石壁上的文字", "outcome": "reward_exp_big"},
            {"text": "直接取走飞剑和戒指", "outcome": "reward_gold_big_or_trap"},
        ],
    },
    # ── 04 灵药幽谷 ──────────────────────────────────────
    {
        "id": "herb_valley",
        "trigger": "move", "chance": 0.06,
        "title": "灵药幽谷",
        "text": (
            "穿过密林，眼前豁然开朗——一片幽谷之中，遍地灵草，药香扑鼻。"
            "你认出了其中几株：百年灵芝、九叶玄参，甚至有一株罕见的冰灵草！"
            "然而谷中央盘踞着一头通体雪白的巨蟒，蛇瞳中寒光闪烁，"
            "分明已达三阶妖兽之境。它冷冷地注视着你，似乎在说：此地有主。"
        ),
        "choices": [
            {"text": "悄悄采摘外围灵药", "outcome": "reward_herbs"},
            {"text": "以丹药与巨蟒交换", "outcome": "reward_herbs_rare"},
            {"text": "转身离开，不冒此险", "outcome": "nothing"},
        ],
    },
    # ── 05 心魔幻境 ──────────────────────────────────────
    {
        "id": "heart_demon",
        "trigger": "move", "chance": 0.04,
        "title": "心魔幻境",
        "text": (
            "你行至一处枯井旁，忽然脚下踩空，坠入一片混沌之中。"
            "再睁眼，你发现自己站在一片血色荒原上，脚下尸骨累累。"
            "远处，一位面容模糊的老者向你伸出手，掌心托着一枚散发金光的丹药："
            "「服下此丹，便可一步登天……你，愿意吗？」"
            "你心中警兆顿生——这是心魔！"
        ),
        "choices": [
            {"text": "凝神静气，默诵清心诀", "outcome": "reward_exp_big"},
            {"text": "接过丹药服下", "outcome": "trap_damage_big"},
            {"text": "以灵力斩破幻境", "outcome": "reward_exp_big_or_damage"},
        ],
    },
    # ── 06 遗迹壁画 ──────────────────────────────────────
    {
        "id": "mural_enlighten",
        "trigger": "move", "chance": 0.04,
        "title": "壁画悟道",
        "text": (
            "你走入一间坍塌的密室，残垣断壁之上竟绘满了壁画。"
            "画中一人持剑立于风雨之中，剑势与天地合一，一剑劈开苍穹。"
            "你凝神注视，忽觉画中人的剑意扑面而来，眼前天旋地转——"
            "你仿佛置身于万年前的战场之上，亲眼目睹那位剑仙的绝世一剑。"
            "剑意如潮水般涌入你的识海……"
        ),
        "choices": [
            {"text": "沉浸其中，全力感悟", "outcome": "reward_exp_huge"},
            {"text": "保持清明，边悟边警戒", "outcome": "reward_exp_big"},
            {"text": "拓印壁画，留待日后参悟", "outcome": "reward_item_scroll"},
        ],
    },
    # ── 07 坊市捡漏 ──────────────────────────────────────
    {
        "id": "market_bargain",
        "trigger": "move", "chance": 0.05,
        "title": "坊市捡漏",
        "text": (
            "坊市角落，一个满脸风霜的散修摆着地摊，上面杂七杂八堆着些残破法器和低阶丹药。"
            "你本欲走过，余光却瞥见一枚灰扑扑的石珠，其上隐约有细如发丝的纹路流转。"
            "你心中一动——这分明是封印形态的灵宝！"
            "散修见你驻足，随口道：「那破珠子？五十灵石拿走。」"
        ),
        "choices": [
            {"text": "果断买下", "outcome": "reward_item_peiyuan_or_pojing"},
            {"text": "故意多挑几样掩人耳目", "outcome": "reward_item_multiple"},
            {"text": "不动声色离开", "outcome": "nothing"},
        ],
    },
    # ── 08 受伤的灵兽 ────────────────────────────────────
    {
        "id": "injured_beast",
        "trigger": "move", "chance": 0.04,
        "title": "浴血青鸾",
        "text": (
            "深渊底部，一头浑身浴血的青鸾伏在碎石之中，翅膀折断，凤目中满是戒备与痛楚。"
            "它的身下护着一枚泛着淡金色光芒的卵——这是一头即将产子的神鸟。"
            "它虚弱地嘶鸣一声，勉强抬起利爪，似乎在警告你不要靠近。"
            "你注意到，它的伤势并非妖兽所为，而是……人为的法器伤痕。"
        ),
        "choices": [
            {"text": "以灵药救治青鸾", "outcome": "reward_technique_or_exp"},
            {"text": "趁其虚弱取走鸟卵", "outcome": "reward_item_rare_or_trap"},
            {"text": "默默离开", "outcome": "nothing"},
        ],
    },
    # ── 09 空间裂缝 ──────────────────────────────────────
    {
        "id": "spatial_rift",
        "trigger": "move", "chance": 0.03,
        "title": "空间裂缝",
        "text": (
            "天空忽然撕裂，一道漆黑的裂缝凭空出现。"
            "裂缝中传来阵阵荒古的气息和隐约的喊杀之声。"
            "透过裂缝，你隐约看见一片血色战场上，无数上古修士的残影仍在厮杀——"
            "这竟是一处被封存万年的上古战场遗迹！"
            "裂缝边缘不断扭曲，似乎随时都会闭合。"
            "而在裂缝入口附近，一枚散发着柔和白光的玉简正缓缓飘出。"
        ),
        "choices": [
            {"text": "冲入裂缝探查", "outcome": "reward_exp_huge_or_trap"},
            {"text": "抢夺玉简后撤离", "outcome": "reward_technique"},
            {"text": "在裂缝外收集飘出的物品", "outcome": "reward_random"},
        ],
    },
    # ── 10 天降陨星 ──────────────────────────────────────
    {
        "id": "meteorite",
        "trigger": "move", "chance": 0.04,
        "title": "天降陨星",
        "text": (
            "子夜时分，天穹骤亮如白昼。"
            "一颗赤红色的流星拖着长长的尾焰划过天际，坠落在不远处的山坳中，大地为之震颤。"
            "你感应到一股从未感知过的奇异灵气波动——"
            "那不是金木水火土任何一种属性，而是……混沌之气？"
            "方圆百里的修士恐怕都已察觉，一场争夺即将开始。"
        ),
        "choices": [
            {"text": "立刻全速赶往陨落之地", "outcome": "reward_materials_rare"},
            {"text": "观察片刻再动身", "outcome": "reward_materials"},
            {"text": "不趟这趟浑水", "outcome": "nothing"},
        ],
    },
    # ── 11 魔修陷阱 ──────────────────────────────────────
    {
        "id": "demon_trap",
        "trigger": "move", "chance": 0.04,
        "title": "噬灵陷阱",
        "text": (
            "你循着浓郁的灵气找到了一处隐秘洞府，洞口阵法柔和，内部陈设雅致，"
            "甚至有一桌尚未凉透的灵茶。"
            "然而你越看越觉得不对——墙角的地砖有新翻动的痕迹，"
            "空气中隐隐有一丝极淡的血腥气。"
            "你运起灵目术望去，骇然发现那些看似装饰的符文，竟是一个巨大的「噬灵阵」！"
            "洞府中央的蒲团下面，埋着数具修士尸体，丹田处空空如也。"
        ),
        "choices": [
            {"text": "立刻退出，不触碰任何东西", "outcome": "nothing"},
            {"text": "破解阵法搜刮资源", "outcome": "reward_materials_or_trap"},
            {"text": "设下反伏击等魔修回来", "outcome": "fight_demon_boss"},
        ],
    },
    # ── 12 灵脉涌动 ──────────────────────────────────────
    {
        "id": "spirit_vein",
        "trigger": "move", "chance": 0.05,
        "title": "灵脉涌动",
        "text": (
            "你脚下的大地忽然微微震颤，一股磅礴的灵气自地底喷涌而出！"
            "方圆数十丈内，草木疯长，灵雾弥漫，空气中灵气浓度骤然提升数倍。"
            "这是地底灵脉偶然涌动的异象，通常只会持续片刻。"
            "你感到丹田中的灵力不由自主地加速运转……"
        ),
        "choices": [
            {"text": "立刻盘膝打坐，趁机修炼", "outcome": "reward_exp_big"},
            {"text": "以灵瓶收集涌出的灵液", "outcome": "reward_herbs_rare"},
            {"text": "继续赶路", "outcome": "nothing"},
        ],
    },
    # ── 13 天道馈赠 ──────────────────────────────────────
    {
        "id": "heaven_gift",
        "trigger": "move", "chance": 0.02,
        "title": "天道馈赠",
        "text": (
            "你将路边一株灵药让给了一位垂死的凡人老者，转身离去，心中并无遗憾。"
            "然而刚走出三步，天际忽然降下一道金色光柱，将你笼罩其中。"
            "浩瀚的天地灵气疯狂涌入你的经脉，丹田中灵力暴涨。"
            "冥冥之中，你听到了一声似有若无的叹息——那是天道的回应。"
            "善因结善果，大道无形，却从不亏欠有德之人。"
        ),
        "choices": [
            {"text": "接受天道馈赠，感悟大道", "outcome": "reward_exp_huge"},
        ],
    },
    # ── 14 拍卖会 ────────────────────────────────────────
    {
        "id": "auction_drama",
        "trigger": "move", "chance": 0.04,
        "title": "拍卖会风云",
        "text": (
            "万宝楼内人声鼎沸，各路修士云集。"
            "台上展柜中，一枚漆黑如墨的残破玉简静静躺着，"
            "拍卖师笑道：「此物乃上古遗迹所得，无人能辨其用途，底价五十灵石。」"
            "满堂哄笑，无人问津。"
            "然而你怀中的一件旧物却微微发热——这玉简绝非凡品！"
        ),
        "choices": [
            {"text": "果断出价五十灵石拍下", "outcome": "reward_technique"},
            {"text": "故作犹豫等流拍后私下收购", "outcome": "reward_item_or_nothing"},
            {"text": "不冒风险，转身离开", "outcome": "nothing"},
        ],
    },
    # ── 15 因果幻境 ──────────────────────────────────────
    {
        "id": "karma_vision",
        "trigger": "move", "chance": 0.02,
        "title": "前世因果",
        "text": (
            "你在枯井边打坐时，忽然坠入一片混沌之中。"
            "再睁眼，你发现自己身处一座战火纷飞的古城，身着将军铠甲，手握长枪。"
            "城下万千敌军压境，身旁一名面容模糊的女子将一枚玉佩塞入你手中："
            "「将军，来世……莫要忘了我。」"
            "你猛然惊醒，掌心中竟真的多了一枚温润玉佩，上面刻着一个看不清的字。"
        ),
        "choices": [
            {"text": "收下玉佩，了却这段因果", "outcome": "reward_item_rare"},
            {"text": "将玉佩投入井中，斩断因果", "outcome": "reward_exp_big"},
            {"text": "以灵力炼化玉佩", "outcome": "reward_exp_huge_or_trap"},
        ],
    },
    # ── 16 秘境开启 ──────────────────────────────────────
    {
        "id": "secret_realm",
        "trigger": "move", "chance": 0.03,
        "title": "秘境浮现",
        "text": (
            "天际忽然裂开一道金光，虚空中浮现出一座巍峨殿宇的虚影，仙乐隐隐，瑞气千条。"
            "方圆百里的修士纷纷仰头，目中尽是狂热——「虚天殿开启了！」"
            "这是三百年一现的上古秘境，传闻其中藏有化神期大能的完整传承。"
            "秘境入口处光幕流转，已有数道身影冲了进去。"
        ),
        "choices": [
            {"text": "立刻冲入秘境争夺先机", "outcome": "reward_exp_huge_or_trap"},
            {"text": "观察片刻再进入", "outcome": "reward_random"},
            {"text": "秘境太危险，不进去了", "outcome": "nothing"},
        ],
    },
    # ── 17 荒野求援 ──────────────────────────────────────
    {
        "id": "rescue_cultivator",
        "trigger": "move", "chance": 0.05,
        "title": "荒野求援",
        "text": (
            "前方草丛中传来微弱的呻吟声。你拨开杂草，发现一名修士浑身是血地倒在地上，"
            "气息奄奄。他的储物袋已被抢走，只剩腰间一枚暗淡的玉佩。"
            "他抓住你的衣袖，艰难开口：「道友……求你……救我……」"
            "他身上的伤口散发着淡淡的魔气——是被魔修所伤。"
        ),
        "choices": [
            {"text": "以灵药救治此人", "outcome": "reward_technique_or_gold"},
            {"text": "搜刮他身上残余之物", "outcome": "reward_gold_small"},
            {"text": "帮他可能引来魔修追杀，绕道离开", "outcome": "nothing"},
        ],
    },
    # ── 18 毒沼奇遇 ──────────────────────────────────────
    {
        "id": "poison_swamp",
        "trigger": "move", "chance": 0.04,
        "title": "毒沼奇遇",
        "text": (
            "你误入一片弥漫着紫色瘴气的沼泽地，脚下的淤泥散发着刺鼻的恶臭。"
            "正欲退出，却见沼泽中央生长着一株通体漆黑的灵草，"
            "草叶上凝结着晶莹的毒液珠——竟是罕见的「毒灵藤」！"
            "但沼泽深处传来低沉的呼吸声，显然有剧毒妖兽在此栖息。"
        ),
        "choices": [
            {"text": "冒险采摘毒灵藤", "outcome": "reward_herbs_poison_or_fight"},
            {"text": "记下位置后离开", "outcome": "nothing"},
        ],
    },
    # ── 19 飞剑残魂 ──────────────────────────────────────
    {
        "id": "sword_spirit",
        "trigger": "move", "chance": 0.03,
        "title": "飞剑残魂",
        "text": (
            "你路过一片乱石滩时，一柄锈迹斑斑的断剑忽然发出嗡鸣之声，自行飞起！"
            "剑身上浮现出一道虚影——竟是一位上古剑修的残魂。"
            "残魂面容模糊，声音苍凉：「万年了……终于有人路过此地。"
            "小友，我乃万剑宗末代掌门，临终前将一缕残魂封入此剑。"
            "你可愿听我讲一段剑道？」"
        ),
        "choices": [
            {"text": "恭敬聆听剑道传承", "outcome": "reward_technique"},
            {"text": "炼化残魂吸收灵力", "outcome": "reward_exp_big"},
            {"text": "不理会，继续赶路", "outcome": "nothing"},
        ],
    },
    # ── 20 丹田异动 ──────────────────────────────────────
    {
        "id": "dantian_resonance",
        "trigger": "move", "chance": 0.03,
        "title": "丹田共鸣",
        "text": (
            "你正行走间，丹田中忽然传来一阵剧烈的震动，灵力不受控制地向外扩散！"
            "你大惊之下连忙运功压制，却发现这并非走火入魔——"
            "而是你体内的灵力与天地间某种神秘力量产生了共鸣。"
            "共鸣持续了整整一炷香的时间，待你回过神来，修为竟已悄然精进。"
        ),
        "choices": [
            {"text": "感悟天地法则", "outcome": "reward_exp_big"},
            {"text": "压制异动，稳固根基", "outcome": "heal_full"},
        ],
    },
    # ── 21 灵兽巢穴 ──────────────────────────────────────
    {
        "id": "beast_nest",
        "trigger": "move", "chance": 0.05,
        "title": "灵兽巢穴",
        "text": (
            "你发现一处被藤蔓遮蔽的山洞，洞口散落着碎裂的蛋壳和柔软的兽毛。"
            "你小心翼翼地探头望去，洞穴深处铺满了干草和灵叶，"
            "其中静静躺着一枚泛着微光的灵兽蛋——母兽似乎外出觅食了。"
            "蛋壳表面隐约可见灵纹流转，显然不是凡物。"
        ),
        "choices": [
            {"text": "悄悄取走灵兽蛋", "outcome": "reward_egg_common"},
            {"text": "在洞口等待母兽归来，尝试收服", "outcome": "reward_egg_rare_or_fight"},
            {"text": "不碰，以免招惹麻烦", "outcome": "nothing"},
        ],
    },
    # ── 22 天降灵蛋 ──────────────────────────────────────
    {
        "id": "falling_egg",
        "trigger": "move", "chance": 0.03,
        "title": "天降灵蛋",
        "text": (
            "一道流光自天际划过，落在你前方不远处的草丛中，激起一阵灵雾。"
            "你急忙上前查看，只见草丛中静静躺着一枚灵气氤氲的巨蛋，"
            "蛋壳上流转着五彩光华——这是传说中的灵兽蛋！"
            "方圆数里都能感应到这股灵气波动，恐怕很快就会有人赶来。"
        ),
        "choices": [
            {"text": "立刻收入储物袋", "outcome": "reward_egg_rare"},
            {"text": "以灵力探查蛋的品质", "outcome": "reward_egg_legend_or_rare"},
        ],
    },
]


# ══════════════════════════════════════════════════════════════
#                        突 发 事 件
#   无需选择，直接生效。trigger="move" 或 "fight"
# ══════════════════════════════════════════════════════════════

SURPRISE_EVENTS = [
    # ── 移动类 ──
    {
        "id": "ambush", "trigger": "move", "chance": 0.10,
        "text": "你行至半途，忽觉背后杀气袭来——一只妖兽从暗处猛扑而出！",
        "effect": "extra_fight",
    },
    {
        "id": "spirit_tide", "trigger": "move", "chance": 0.06,
        "text": "天地灵气忽然暴涨，你沐浴在灵气潮汐之中，丹田中灵力涌动不已。",
        "effect": "exp_boost", "value_range": (10, 50),
    },
    {
        "id": "treasure_spot", "trigger": "move", "chance": 0.05,
        "text": "路边碎石中露出一角灵石矿脉碎片，你随手拾取，灵力充沛。",
        "effect": "gold_gain", "value_range": (5, 30),
    },
    {
        "id": "herb_spot", "trigger": "move", "chance": 0.07,
        "text": "你注意到路边生长着几株灵草，随手采集放入储物袋。",
        "effect": "herb_gain", "herb_pool": ["lingcao","bingling_cao","huoling_hua","dueling_teng"], "count_range": (1, 3),
    },
    {
        "id": "wound_heal", "trigger": "move", "chance": 0.04,
        "text": "你路过一处灵泉，泉水温润入体，伤势恢复了不少。",
        "effect": "heal_partial", "value_range": (20, 60),
    },
    {
        "id": "spirit_storm", "trigger": "move", "chance": 0.04,
        "text": "一道灵气风暴袭来！你运转灵力抵抗，虽有些损耗，但对天地法则多了几分感悟。",
        "effect": "storm", "hp_loss_pct": 0.1, "exp_gain_range": (20, 80),
    },
    {
        "id": "merchant", "trigger": "move", "chance": 0.04,
        "text": "一位行脚商人路过，向你兜售灵药。你以低价购得两瓶回气丹。",
        "effect": "item_gain", "item": "huiqi_dan", "count": 2,
    },
    {
        "id": "fallen_cultivator", "trigger": "move", "chance": 0.04,
        "text": "你发现一位坐化修士的遗骸，身旁的储物袋中尚存些许丹药和灵石。",
        "effect": "loot_cache", "items": [("huiqi_dan", 1, 0.8), ("huichun_dan", 1, 0.4), ("peiyuan_dan", 1, 0.2)], "gold_range": (10, 50),
    },
    {
        "id": "beast_tracks", "trigger": "move", "chance": 0.06,
        "text": "你发现一串巨大的妖兽脚印，循迹而行找到了一具被啃食殆尽的妖兽残骸，尚可取用。",
        "effect": "material_gain", "mat_pool": ["yaogu","yaopimo","yaodan"], "count_range": (1, 2),
    },
    {
        "id": "dantian_buzz", "trigger": "move", "chance": 0.03,
        "text": "你的丹田忽然产生共鸣，一股神秘力量涌入——修为突飞猛进！",
        "effect": "exp_boost", "value_range": (30, 100),
    },

    # ── 战斗类 ──
    {
        "id": "beast_berserk", "trigger": "fight", "chance": 0.08,
        "text": "妖兽忽然狂暴！双目赤红，浑身妖力暴涨，攻击愈发凶猛！",
        "effect": "monster_buff", "stat": "atk", "mult": 1.5,
    },
    {
        "id": "beast_weak", "trigger": "fight", "chance": 0.08,
        "text": "你注意到妖兽行动迟缓——它身上有旧伤未愈，防御大不如前。",
        "effect": "monster_debuff", "stat": "def", "mult": 0.5,
    },
    {
        "id": "critical_moment", "trigger": "fight", "chance": 0.06,
        "text": "你灵光一闪，领悟到妖兽的弱点所在——此刻出手，必能重创！",
        "effect": "player_buff", "stat": "atk", "mult": 1.4,
    },
    {
        "id": "reinforcement", "trigger": "fight", "chance": 0.04,
        "text": "战斗的声响惊动了附近的妖兽——又有两只循声而来！",
        "effect": "extra_monsters", "count": 2,
    },
    {
        "id": "divine_strike", "trigger": "fight", "chance": 0.03,
        "text": "天道感应！一道天雷劈下，直击妖兽！雷光散去，妖兽发出一声惨嚎。",
        "effect": "thunder_strike", "dmg_range": (30, 100),
    },
    {
        "id": "treasure_drop", "trigger": "fight", "chance": 0.05,
        "text": "战斗中妖兽身上掉落了一件天材地宝——这是它此前吞噬的宝物！",
        "effect": "bonus_drop", "item_pool": ["wanling_guo","huoling_hua","bingling_cao","tianwai_yuntie"], "drop_chance": 0.6,
    },
]
