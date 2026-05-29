"""
仙途NPC数据：NPC定义、任务系统、好感度、宗门贡献
"""

# ═══════════════ NPC定义 ═══════════════
NPCS = {
    "su_wanjin": {
        "name": "苏万金", "title": "青云坊市掌柜", "location": "qingyun_town", "type": "merchant", "realm": 4,
        "greeting": "哟，新来的？灵石带够了没有？",
        "dialogues": {
            0: ["哟，新来的？灵石带够了没有？本店概不赊账。", "看什么看？穷鬼买不起就别挡着后面的道友。"],
            1: ["小友又来了？今日新到了一批冰灵草，要不要看看？", "你我是老主顾了，给你留了几样好东西。"],
            2: ["贤弟，你来得正好。有人托我出手一件灵器，旁人我不放心，只给你留着。", "以你我的交情，坊市里什么消息我都可以替你打听一二。"],
            3: ["万金此生走南闯北，见过修士无数，如贤弟这般赤诚之人，少之又少。今后但有差遣，万死不辞。", "实不相瞒，我在暗市中还有些门路。你若需要稀罕物，我替你想办法。"],
        },
        "realm_dialogues": {
            (1,3): "练气期的小修士，劝你别好高骛远，先买些回气丹备着。修行路上，保命要紧。",
            (4,6): "筑基了？不错不错，法器级别的装备我这儿有一些，攒够灵石再来。",
            (7,10): "前辈驾临，小店蓬荜生辉！暗市通道已为您开启，请移步内堂。",
            (11,15): "大……大能前辈！万金有眼无珠，此前多有怠慢。前辈需要什么，万金赴汤蹈火也要办到。",
        },
        "gift_preferences": {"liked": ["hantie_kuang","xuanjin_shi","tianwai_yuntie"], "disliked": ["dueling_teng"], "liked_value": 3, "disliked_value": -2},
    },
    "zhou_yunyou": {
        "name": "周云游", "title": "云游散修", "location": "luoxia_plains", "type": "quest", "realm": 6,
        "greeting": "你也是来此历练的？老夫这有个差事。",
        "dialogues": {
            0: ["你也是来此历练的？嗯……看你面相，怕是活不过三天。罢了，老夫这有个差事，你若办得成，赏你些好东西。"],
            1: ["又见面了，小友。上次你办的差事利索得很，这次有个更有意思的。"],
            2: ["老夫行走天下数百年，识人无数。小友是我见过最有潜力的年轻人。来，这有一桩机缘，只告诉你一人。"],
            3: ["云游一生孤独，不曾想老来遇到你这么个忘年交。今日将珍藏多年的密卷交给你——这是我的毕生所学。"],
        },
        "realm_dialogues": {
            (1,3): "练气期就敢来苍茫草原？胆子不小。这样吧，帮我采集三株灵草，我保你平安。",
            (4,6): "境界不错了。我这儿有些诛杀妖兽的悬赏，赏金丰厚，可敢接？",
            (7,10): "前辈莫怪老朽斗胆——我有一桩数十年未能完成的旧事，想托付于你。",
            (11,15): "天大的机缘！传说天劫峰上封印着一头上古真龙，老夫无力前往，不知前辈可有兴趣？",
        },
        "gift_preferences": {"liked": ["peiyuan_dan","juling_dan"], "disliked": ["huiqi_dan"], "liked_value": 4, "disliked_value": -2},
    },
    "qingxu": {
        "name": "清虚道人", "title": "青云宗传功长老", "location": "qingyun_town", "type": "trainer", "realm": 12,
        "greeting": "嗯？又一个来求道的。",
        "dialogues": {
            0: ["嗯？又一个来求道的。老夫每日只传授三人，你先到门外候着，听我讲完一卷经文再进来。"],
            1: ["你来了。上次教你的功法领悟得如何？修行之道，切忌囫囵吞枣。来，今日为你讲解经脉运行之法。"],
            2: ["好苗子！老夫修道八百年，像你这般悟性的人，不超过五个。来，今日传你一门不传之秘。"],
            3: ["痴儿，你可知老夫为何独独看重你？因为你的心性……像极了年轻时的我。今日倾囊相授，愿你走得比我更远。"],
        },
        "realm_dialogues": {
            (1,3): "练气之道，在于感应天地灵气。闭目凝神，将灵力引入丹田——这便是修行的第一步。",
            (4,6): "筑基便是打牢根基。功法不在多，在精。选一门适合自己的，反复参悟。",
            (7,10): "结丹之后，灵力凝聚成核，与天地共鸣。此时当悟大道之意，而非执着于术法之巧。",
            (11,15): "道友修为通天，老夫已无甚可教。但有一卷上古残卷，或许对道友有所裨益。",
        },
        "gift_preferences": {"liked": ["wudao_dan","jiuhuan_cao"], "disliked": ["dueling_teng"], "liked_value": 5, "disliked_value": -2},
    },
    "danyangzi": {
        "name": "丹阳子", "title": "丹鼎阁阁主", "location": "qingyun_town", "type": "crafter", "realm": 9,
        "greeting": "灵草不是这么用的！看你浪费的那些材料，老夫心都在滴血。",
        "dialogues": {
            0: ["灵草不是这么用的！看你浪费的那些材料，老夫心都在滴血。罢了，本阁主今日心情好，指点你一二。"],
            1: ["你那株冰灵草品质不错啊。拿来给我看看……嗯，冰灵草配火灵花，阴阳调和，可炼回春丹。"],
            2: ["你的丹道造诣进步神速。来，今日传你一个诀窍——炼丹时先以文火温炉三息，可提升一成成功率。"],
            3: ["我丹阳子一生收徒七人，皆不成器。唯你……有几分药王当年的风骨。这套九转丹诀，今日传于你。"],
        },
        "realm_dialogues": {
            (1,3): "小友，炼丹之道急不得。先把基础丹药练熟了再说。",
            (4,6): "筑基期的修士，可以尝试炼制回春丹了。我这儿有几张丹方，你拿去参详。",
            (7,10): "结丹之后，丹火品质大增。以你的丹火，可以尝试炼制聚灵丹。",
            (11,15): "前辈的丹道造诣，老夫自愧不如。这张九转丹方，或许前辈用得上。",
        },
        "gift_preferences": {"liked": ["wanling_guo","huoling_hua","fengxue_hua"], "disliked": ["yaogu"], "liked_value": 4, "disliked_value": -2},
    },
    "ouye_qingfeng": {
        "name": "欧冶青锋", "title": "炼器大师", "location": "spirit_cave", "type": "crafter", "realm": 8,
        "greeting": "想锻造法宝？先把材料备齐了再说。",
        "dialogues": {
            0: ["想锻造法宝？先把材料备齐了再说。没有好的矿石，巧妇难为无米之炊。"],
            1: ["你上次送来的寒铁矿不错，纯度很高。下次多弄些来，我给你打一柄好剑。"],
            2: ["贤弟，我看你骨骼清奇，适合用剑。来，我以天外陨铁为基，为你铸一柄趁手的法宝。"],
            3: ["我欧冶家世代炼器，到了我这一辈，险些失传。你若是有缘人……这套天工炼器诀，便传与你了。"],
        },
        "realm_dialogues": {
            (1,3): "你现在还是凡铁用用吧，法器的活等你境界高了再来。",
            (4,6): "法器我可以帮你锻造，材料自备，加工费二十灵石。",
            (7,10): "灵器级法宝？有胆识。材料备齐了来找我，我给你炼一柄好的。",
            (11,15): "前辈……仙器级别的锻造，老夫平生只成功过一次。但若前辈信任，愿再试一次。",
        },
        "gift_preferences": {"liked": ["tianwai_yuntie","zijin_kuang","xuanjin_shi"], "disliked": ["lingcao"], "liked_value": 5, "disliked_value": -1},
    },
    "an_die": {
        "name": "暗蝶", "title": "蝶影阁阁主", "location": "mine_depth", "type": "informant", "realm": 7,
        "greeting": "嘘……别大声。你想知道什么？先付灵石。",
        "dialogues": {
            0: ["嘘……别大声。你想知道什么？先付灵石。这条规矩，从我蝶影阁建立那天起就没变过。"],
            1: ["又来了？这次给你个优惠——买一送一。苍茫草原最近出现了一头异变妖兽，赏金很高。"],
            2: ["贤弟，你是少数让我看得顺眼的修士。这条消息不收你钱——幽冥祭坛深处有一座远古传送阵。"],
            3: ["我暗蝶行走暗中数百年，你是唯一一个不问我真面目的人。这份信任……值千金。来，这是我蝶影阁的令牌。"],
        },
        "realm_dialogues": {
            (1,3): "你这修为……我劝你别打探太多，有些事知道了反而是祸。",
            (4,6): "有些消息值灵石，有些消息值命。你出得起哪个？",
            (7,10): "前辈想知道什么？暗蝶知无不言。当然，灵石还是要收的。",
            (11,15): "大能前辈亲临，暗蝶不胜惶恐。前辈想知道的事……恐怕整个蝶影阁的情报网都未必有答案。",
        },
        "gift_preferences": {"liked": ["dueling_teng","yaodan"], "disliked": ["lingcao"], "liked_value": 3, "disliked_value": -1},
    },
    "xuanqing": {
        "name": "玄清真人", "title": "青云宗接引长老", "location": "qingyun_town", "type": "sect", "realm": 13,
        "greeting": "小友，既然踏上了修仙之路，便不可懈怠。",
        "dialogues": {
            0: ["小友，既然踏上了修仙之路，便不可懈怠。青云宗虽是小宗门，却也传承千年。你若有意，可先完成几桩宗门任务。"],
            1: ["你的宗门贡献已有不少。继续努力，达到内门弟子的标准后，宗门会为你开放更多资源。"],
            2: ["你已被提拔为内门弟子。从今日起，可进入宗门藏经阁参悟功法，宗门丹房也可为你所用。"],
            3: ["你已成为青云宗核心弟子，长老会一致通过。宗门秘境、护宗大阵……一切向你开放。好好修行，莫辜负宗门的期望。"],
        },
        "realm_dialogues": {
            (1,3): "小友初入仙途，先从宗门杂务做起吧。完成宗门任务，积累贡献。",
            (4,6): "筑基之后，可接取更高级的宗门任务。宗门藏经阁中有些功法，对你或许有用。",
            (7,10): "结丹修士，已是宗门的中坚力量。宗门正在筹备一次秘境探索，你可愿参加？",
            (11,15): "前辈修为通天，青云宗能有前辈坐镇，实乃宗门之幸。宗门一切资源，前辈随意取用。",
        },
        "gift_preferences": {"liked": ["jiuzhuan_dan","fengxue_hua","longxian_cao"], "disliked": [], "liked_value": 5, "disliked_value": 0},
    },
}

NPC_GOODWILL_TIERS = {
    0: {"name": "陌生", "min": 0, "max": 9},
    1: {"name": "熟人", "min": 10, "max": 29},
    2: {"name": "友好", "min": 30, "max": 59},
    3: {"name": "知己", "min": 60, "max": 999},
}

def get_goodwill_tier(goodwill):
    if goodwill >= 60: return 3
    if goodwill >= 30: return 2
    if goodwill >= 10: return 1
    return 0


# ═══════════════ 任务系统 ═══════════════
QUESTS = {
    # ── 练气期·日常 ──
    "dq_wolf_hunt": {
        "name": "除狼患", "desc": "落霞林中青狼成群，扰得散修们不得安宁。", "type": "kill",
        "npc": "zhou_yunyou", "req_realm": 1, "daily": True,
        "objectives": {"kill": {"green_wolf": 5}},
        "rewards": {"exp": 25, "gold": 15, "goodwill": {"zhou_yunyou": 2}},
        "accept_text": "周云游捋须道：「落霞林中青狼成群，扰得散修们不得安宁。你去杀上五头，回来领赏。」",
        "complete_text": "周云游点头道：「不错，干得利落。拿着这些灵石，去买些丹药补补。修行路远，莫要逞强。」",
    },
    "dq_herb_gather": {
        "name": "采集灵草", "desc": "丹阳子需要一批灵草入药。", "type": "collect",
        "npc": "danyangzi", "req_realm": 1, "daily": True,
        "objectives": {"collect": {"lingcao": 8}},
        "rewards": {"exp": 20, "gold": 10, "goodwill": {"danyangzi": 3}},
        "accept_text": "丹阳子头也不抬：「去采八株灵草回来，老夫正缺药材。注意，要新鲜的。」",
        "complete_text": "丹阳子接过灵草，仔细端详：「不错，品相尚可。这些灵石拿去，下次有好药材还来找我。」",
    },
    "dq_spirit_slay": {
        "name": "诛灭灵怪", "desc": "灵液怪出没，影响了灵矿开采。", "type": "kill",
        "npc": "zhou_yunyou", "req_realm": 1, "daily": True,
        "objectives": {"kill": {"spirit_slime": 3}},
        "rewards": {"exp": 20, "gold": 12, "goodwill": {"zhou_yunyou": 2}},
        "accept_text": "「灵矿洞穴附近灵液怪泛滥，你去清理三只，矿工们会感激你的。」",
        "complete_text": "「干得好。灵液怪的残骸还能提炼灵液，不亏。」",
    },
    "dq_recon": {
        "name": "巡查落霞林", "desc": "玄清真人命你巡查落霞林。", "type": "visit",
        "npc": "xuanqing", "req_realm": 1, "daily": True,
        "objectives": {"visit": ["fallenwood_forest"]},
        "rewards": {"exp": 15, "gold": 8, "sect_contrib": 5},
        "accept_text": "玄清真人道：「你去落霞林巡查一番，看看是否有异常。小心行事。」",
        "complete_text": "「嗯，落霞林暂无异常。辛苦了，这是宗门的赏赐。」",
    },
    "dq_mine_patrol": {
        "name": "矿洞巡逻", "desc": "灵矿洞穴需要巡逻。", "type": "visit",
        "npc": "xuanqing", "req_realm": 2, "daily": True,
        "objectives": {"visit": ["spirit_cave"]},
        "rewards": {"exp": 25, "gold": 15, "sect_contrib": 8},
        "accept_text": "「灵矿洞穴是宗门的重要矿脉，你去巡视一圈，确保安全。」",
        "complete_text": "「矿脉安好，你的功劳宗门记下了。」",
    },

    # ── 练气期·一次性 ──
    "qt_first_cultivation": {
        "name": "初入仙途", "desc": "清虚道人要你采集灵草，以示修行诚意。", "type": "collect",
        "npc": "qingxu", "req_realm": 1, "daily": False,
        "objectives": {"collect": {"lingcao": 3}},
        "rewards": {"exp": 40, "gold": 20, "goodwill": {"qingxu": 5}},
        "accept_text": "清虚道人淡淡道：「修行先修心。你去落霞林采三株灵草回来，老夫看看你的诚意。记住——灵草生于灵气充沛之处，莫要采错了。」",
        "complete_text": "清虚道人接过灵草，微微颔首：「尚可。灵草品质虽一般，但你肯脚踏实地去做，已是难得。来，今日传你一门吐纳之法。」",
    },
    "qt_forge_init": {
        "name": "初学炼器", "desc": "欧冶青锋要你准备炼器材料。", "type": "collect",
        "npc": "ouye_qingfeng", "req_realm": 1, "daily": False,
        "objectives": {"collect": {"hantie_kuang": 2, "yaogu": 2}},
        "rewards": {"exp": 30, "gold": 15, "goodwill": {"ouye_qingfeng": 5}},
        "accept_text": "欧冶青锋道：「想学炼器？先去弄两块寒铁矿和两根妖兽骨骼来，我看看你的诚意。」",
        "complete_text": "「材料不错。炼器之道，首重选材。你先把这门基础锻打术练熟了。」",
    },
    "qt_trust_test": {
        "name": "信任考验", "desc": "暗蝶要你证明自己的实力。", "type": "kill",
        "npc": "an_die", "req_realm": 2, "daily": False,
        "objectives": {"kill": {"rogue_cultivator": 3}},
        "rewards": {"exp": 35, "gold": 25, "goodwill": {"an_die": 8}},
        "accept_text": "暗蝶低声道：「苍茫草原上有三个散修，专门打劫落单修士。你去解决他们，我便信你。」",
        "complete_text": "暗蝶微微点头：「不错，手脚干净。从今往后，蝶影阁的情报……对你打八折。」",
    },
    "qt_sect_init": {
        "name": "宗门试炼", "desc": "玄清真人要你斩妖证明实力。", "type": "kill",
        "npc": "xuanqing", "req_realm": 1, "daily": False,
        "objectives": {"kill_any": 10},
        "rewards": {"exp": 50, "gold": 30, "sect_contrib": 15},
        "accept_text": "玄清真人道：「青云宗不收无用之人。你去斩杀十只妖兽，回来复命。」",
        "complete_text": "「不错，有几分修士的样子了。从今日起，你便是青云宗外门弟子。」",
    },

    # ── 筑基期·日常 ──
    "dq_deepwood_hunt": {
        "name": "密林猎杀", "desc": "妖兽密林中灰鬃狼王横行。", "type": "kill",
        "npc": "zhou_yunyou", "req_realm": 4, "daily": True,
        "objectives": {"kill": {"wolf_king": 3}},
        "rewards": {"exp": 80, "gold": 45, "goodwill": {"zhou_yunyou": 3}},
        "accept_text": "「妖兽密林中的灰鬃狼王愈发猖獗，你去猎杀三头，赏金丰厚。」",
        "complete_text": "「漂亮！狼王的皮毛值不少灵石。你的实力又精进了。」",
    },
    "dq_rare_herb": {
        "name": "稀有药材", "desc": "丹阳子需要稀有灵草炼制高阶丹药。", "type": "collect",
        "npc": "danyangzi", "req_realm": 4, "daily": True,
        "objectives": {"collect": {"bingling_cao": 3, "huoling_hua": 2}},
        "rewards": {"exp": 70, "gold": 40, "goodwill": {"danyangzi": 4}},
        "accept_text": "「我需要三株冰灵草和两株火灵花来炼一炉阴阳丹。你去采来。」",
        "complete_text": "「品质不错！这炉丹药若炼成，分你一枚。」",
    },
    "dq_sect_deepwood": {
        "name": "清剿密林", "desc": "宗门下令清剿妖兽密林。", "type": "kill",
        "npc": "xuanqing", "req_realm": 4, "daily": True,
        "objectives": {"kill_any_location": {"yaoshou_deepwood": 5}},
        "rewards": {"exp": 75, "gold": 35, "sect_contrib": 12},
        "accept_text": "「妖兽密林妖气暴涨，恐有异变。你带人去清剿五只妖兽。」",
        "complete_text": "「密林暂时安宁了。你的贡献，宗门铭记在心。」",
    },

    # ── 筑基期·一次性 ──
    "qt_sect_inner": {
        "name": "内门试炼", "desc": "击败强敌证明实力，晋升内门弟子。", "type": "kill",
        "npc": "xuanqing", "req_realm": 4, "daily": False,
        "objectives": {"kill": {"wolf_king": 1, "ancient_tree_demon": 1}},
        "rewards": {"exp": 150, "gold": 80, "sect_contrib": 25},
        "accept_text": "玄清真人正色道：「灰鬃狼王和古树妖是密林两大祸患。你若能各斩一头，便可晋升内门弟子。」",
        "complete_text": "「好！从今日起，你便是青云宗内门弟子。藏经阁对你开放，好好修行。」",
    },
    "qt_alchemy_mastery": {
        "name": "丹道入门", "desc": "丹阳子要你亲手炼制回春丹。", "type": "collect",
        "npc": "danyangzi", "req_realm": 3, "daily": False,
        "objectives": {"collect": {"huichun_dan": 3}},
        "rewards": {"exp": 120, "gold": 50, "goodwill": {"danyangzi": 10}},
        "accept_text": "「纸上得来终觉浅。你去亲手炼制三枚回春丹，拿来给我看看成色。」",
        "complete_text": "丹阳子捻起一枚丹药，对着光细看：「嗯，药效尚可，火候还差些。不过以你的资质，假以时日必成大器。来，这张丹方给你。」",
    },

    # ── 结丹期·日常 ──
    "dq_mine_chief": {
        "name": "妖兵统领", "desc": "矿脉深处出现了妖兵统领。", "type": "kill",
        "npc": "zhou_yunyou", "req_realm": 7, "daily": True,
        "objectives": {"kill": {"mine_demon_chief": 1}},
        "rewards": {"exp": 200, "gold": 120, "goodwill": {"zhou_yunyou": 3}},
        "accept_text": "「矿脉深处冒出一头妖兵统领，矿工们都不敢下去了。你去解决它。」",
        "complete_text": "「妖兵统领已除？太好了！矿脉可以重新开采了。这是你的赏金。」",
    },
    "dq_high_alchemy": {
        "name": "高阶炼丹", "desc": "丹阳子需要你炼制聚灵丹。", "type": "collect",
        "npc": "danyangzi", "req_realm": 6, "daily": True,
        "objectives": {"collect": {"juling_dan": 2}},
        "rewards": {"exp": 150, "gold": 80, "goodwill": {"danyangzi": 5}},
        "accept_text": "「聚灵丹供不应求，你帮我炼两枚。材料你自备。」",
        "complete_text": "「成色不错，有进步。这是你的报酬。」",
    },

    # ── 结丹期·一次性 ──
    "qt_youming_trial": {
        "name": "幽冥试炼", "desc": "幽冥祭坛魔气暴涨，前去诛杀魔修。", "type": "kill",
        "npc": "xuanqing", "req_realm": 7, "daily": False,
        "objectives": {"kill": {"demonic_cultivator": 3}},
        "rewards": {"exp": 300, "gold": 200, "sect_contrib": 40},
        "accept_text": "玄清真人神色凝重：「幽冥祭坛近日魔气暴涨，恐有魔修盘踞。你已结丹，可堪此任。前去查探，诛杀魔修，莫要堕了青云宗的名头。」",
        "complete_text": "玄清真人长叹一声：「魔修已被清除，祭坛暂时安宁。你为宗门立了大功，论功行赏，理所应当。」",
    },

    # ── 元婴期·一次性 ──
    "qt_sect_core": {
        "name": "核心弟子", "desc": "斩杀蛟龙，晋升核心弟子。", "type": "kill",
        "npc": "xuanqing", "req_realm": 10, "daily": False,
        "objectives": {"kill": {"flood_dragon": 1}},
        "rewards": {"exp": 800, "gold": 500, "sect_contrib": 80},
        "accept_text": "「天劫峰下的蛟龙已成大患。你若能斩杀此龙，便可晋升核心弟子。」",
        "complete_text": "「蛟龙已死？！你……你做到了。从今日起，你是青云宗核心弟子，长老会一致通过。」",
    },

    # ── 化神+·一次性 ──
    "qt_tribulation": {
        "name": "天劫试炼", "desc": "斩杀天劫峰上的上古真龙。", "type": "kill",
        "npc": "qingxu", "req_realm": 12, "daily": False,
        "objectives": {"kill": {"ancient_true_dragon": 1}},
        "rewards": {"exp": 2000, "gold": 1500, "goodwill": {"qingxu": 20}},
        "accept_text": "清虚道人目光深邃：「天劫峰上，传说封印着一头上古真龙。它已活了万年，实力通天。你若有胆量……去会会它。若能斩杀此龙，你便真正踏入了大能之列。」",
        "complete_text": "清虚道人闭目良久，再睁眼时，目中竟有泪光：「你做到了。万年以来，无人能杀此龙。你……已是真正的强者。」",
    },
}

# 宗门贡献等级
SECT_RANKS = {
    0:  {"name": "外门弟子", "min": 0,   "bonus": 0,    "desc": "基础宗门任务"},
    1:  {"name": "内门弟子", "min": 50,  "bonus": 0.05, "desc": "藏经阁开放，修炼速度+5%"},
    2:  {"name": "核心弟子", "min": 150, "bonus": 0.10, "desc": "宗门宝库开放，修炼速度+10%"},
    3:  {"name": "真传弟子", "min": 350, "bonus": 0.15, "desc": "青云秘典，修炼速度+15%"},
}

def get_sect_rank(contrib):
    if contrib >= 350: return 3
    if contrib >= 150: return 2
    if contrib >= 50: return 1
    return 0
