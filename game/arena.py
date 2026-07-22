import json
import random
from game_data import TECHNIQUES, SPIRIT_ROOTS, ELEMENT_COUNTER
from game.utils import get_full_stats

def simulate_pvp(challenger, defender):
    """
    模拟异步 PvP 战斗。
    返回: (winner_id, score_change, log_list)
    """
    log = []
    
    # 1. 计算双方全属性
    c_stats = get_full_stats(challenger)
    d_stats = get_full_stats(defender)
    
    # 2. 灵根五行相克
    c_sr = challenger.get("spirit_root")
    d_sr = defender.get("spirit_root")
    c_elem = SPIRIT_ROOTS.get(c_sr, {}).get("element") if c_sr else None
    d_elem = SPIRIT_ROOTS.get(d_sr, {}).get("element") if d_sr else None
    
    c_atk_mult = 1.0
    d_atk_mult = 1.0
    
    if c_elem and d_elem:
        if ELEMENT_COUNTER.get(c_elem) == d_elem:
            c_atk_mult = 1.3
            log.append(f"【五行相克】挑战者 {challenger['name']}（{c_elem}）克制防守者 {defender['name']}（{d_elem}），攻击加成 +30%！")
        elif ELEMENT_COUNTER.get(d_elem) == c_elem:
            d_atk_mult = 1.3
            log.append(f"【五行相克】防守者 {defender['name']}（{d_elem}）克制挑战者 {challenger['name']}（{c_elem}），攻击加成 +30%！")
            
    c_hp = c_stats["max_hp"]
    c_max_hp = c_stats["max_hp"]
    c_mp = c_stats["max_mp"]
    c_max_mp = c_stats["max_mp"]
    c_atk = int(c_stats["atk"] * c_atk_mult)
    c_def = c_stats["def"]
    
    d_hp = d_stats["max_hp"]
    d_max_hp = d_stats["max_hp"]
    d_mp = d_stats["max_mp"]
    d_max_mp = d_stats["max_mp"]
    d_atk = int(d_stats["atk"] * d_atk_mult)
    d_def = d_stats["def"]
    
    # 3. 解析可用技能
    def get_available_skills(char, filter_list=None):
        try:
            learned = json.loads(char["techniques"]) if char["techniques"] else []
        except Exception:
            learned = []
        skills = []
        for tid in learned:
            t = TECHNIQUES.get(tid)
            if t and t.get("skill"):
                # 防守方：若配置了防守技能列表（非空），则只保留列表中的技能；
                # 空列表 = 未配置，自动使用全部已学技能参战（最强防守）。
                if filter_list:
                    if tid not in filter_list:
                        continue
                skills.append(t["skill"])
        return skills

    # 解析防守技能
    d_def_skills_raw = defender.get("arena_defense_skills", "[]")
    try:
        d_def_skills_list = json.loads(d_def_skills_raw) if d_def_skills_raw else []
    except Exception:
        d_def_skills_list = []
        
    c_skills = get_available_skills(challenger)
    d_skills = get_available_skills(defender, d_def_skills_list)
    
    # 战斗状态初始化
    c_buffs = {}
    d_buffs = {}
    
    def get_effective_atk(base_atk, buffs):
        mult = buffs.get("atk", {}).get("mult", 1.0)
        return int(base_atk * mult)
        
    def get_effective_def(base_def, buffs):
        mult = buffs.get("def", {}).get("mult", 1.0)
        return int(base_def * mult)
        
    def decrement_buffs(buffs):
        expired = []
        for stat, info in buffs.items():
            info["rounds"] -= 1
            if info["rounds"] <= 0:
                expired.append(stat)
        for stat in expired:
            del buffs[stat]

    # 回合循环 (最大 30 回合)
    winner_id = None
    for r in range(1, 31):
        # --- 挑战者行动 ---
        if c_hp <= 0 or d_hp <= 0:
            break
            
        c_eff_atk = get_effective_atk(c_atk, c_buffs)
        d_eff_def = get_effective_def(d_def, d_buffs)
        
        # AI 行动决策
        action_taken = False
        
        # 1. 治疗优先 (生命值 < 40%)
        if c_hp < c_max_hp * 0.4:
            heal_skills = [s for s in c_skills if s["type"] == "heal" and c_mp >= s.get("mp_cost", 0)]
            if heal_skills:
                skill = random.choice(heal_skills)
                c_mp -= skill.get("mp_cost", 0)
                heal_amt = int(c_max_hp * skill["power"])
                c_hp = min(c_max_hp, c_hp + heal_amt)
                log.append(f"[第{r}回合] 挑战者 {challenger['name']} 施展【{skill['name']}】，恢复了 {heal_amt} 点气血。")
                action_taken = True
                
        # 2. 增益辅助 (若无防御增益且有增益技能)
        if not action_taken and "def" not in c_buffs:
            def_skills = [s for s in c_skills if s["type"] in {"defense", "buff"} and c_mp >= s.get("mp_cost", 0)]
            if def_skills:
                skill = random.choice(def_skills)
                c_mp -= skill.get("mp_cost", 0)
                dur = skill.get("duration", 2)
                power = skill.get("power", 0.3)
                if skill["type"] == "defense":
                    c_buffs["def"] = {"mult": 1.0 - power, "rounds": dur}
                    log.append(f"[第{r}回合] 挑战者 {challenger['name']} 施展【{skill['name']}】，使自身受到的伤害减免 {int(power*100)}%，持续 {dur} 回合。")
                else:
                    c_buffs["atk"] = {"mult": 1.0 + power, "rounds": dur}
                    log.append(f"[第{r}回合] 挑战者 {challenger['name']} 施展【{skill['name']}】，使自身攻击提升 {int(power*100)}%，持续 {dur} 回合。")
                action_taken = True
                
        # 3. 施展攻击技能
        if not action_taken:
            atk_skills = [s for s in c_skills if s["type"] in {"attack", "multi_hit"} and c_mp >= s.get("mp_cost", 0)]
            if atk_skills:
                skill = random.choice(atk_skills)
                c_mp -= skill.get("mp_cost", 0)
                if skill["type"] == "attack":
                    dmg = max(1, int(c_eff_atk * skill["power"]) - d_eff_def + random.randint(-1, 2))
                    d_hp -= dmg
                    log.append(f"[第{r}回合] 挑战者 {challenger['name']} 施展【{skill['name']}】，对 {defender['name']} 造成 {dmg} 点伤害。")
                else:
                    hits = skill.get("hits", 2)
                    total = 0
                    for h in range(hits):
                        dmg = max(1, int(c_eff_atk * skill["power"]) - d_eff_def + random.randint(-1, 2))
                        total += dmg
                    d_hp -= total
                    log.append(f"[第{r}回合] 挑战者 {challenger['name']} 施展【{skill['name']}】，{hits}连击！对 {defender['name']} 共造成 {total} 点伤害。")
                action_taken = True
                
        # 4. 普通攻击
        if not action_taken:
            dmg = max(1, c_eff_atk - d_eff_def + random.randint(-1, 2))
            d_hp -= dmg
            log.append(f"[第{r}回合] 挑战者 {challenger['name']} 催动灵力，一掌拍向 {defender['name']}，造成 {dmg} 点伤害。")

        # 检查是否击杀防守者
        if d_hp <= 0:
            log.append(f"【斗法结束】防守者 {defender['name']} 支撑不住，败下阵来！挑战者 {challenger['name']} 获得胜利！")
            winner_id = challenger["user_id"]
            break
            
        # --- 防守者行动 ---
        d_eff_atk = get_effective_atk(d_atk, d_buffs)
        c_eff_def = get_effective_def(c_def, c_buffs)
        
        action_taken = False
        
        # 1. 治疗优先 (生命值 < 40%)
        if d_hp < d_max_hp * 0.4:
            heal_skills = [s for s in d_skills if s["type"] == "heal" and d_mp >= s.get("mp_cost", 0)]
            if heal_skills:
                skill = random.choice(heal_skills)
                d_mp -= skill.get("mp_cost", 0)
                heal_amt = int(d_max_hp * skill["power"])
                d_hp = min(d_max_hp, d_hp + heal_amt)
                log.append(f"[第{r}回合] 防守者 {defender['name']} 施展【{skill['name']}】，恢复了 {heal_amt} 点气血。")
                action_taken = True
                
        # 2. 增益辅助 (若无防御增益且有增益技能)
        if not action_taken and "def" not in d_buffs:
            def_skills = [s for s in d_skills if s["type"] in {"defense", "buff"} and d_mp >= s.get("mp_cost", 0)]
            if def_skills:
                skill = random.choice(def_skills)
                d_mp -= skill.get("mp_cost", 0)
                dur = skill.get("duration", 2)
                power = skill.get("power", 0.3)
                if skill["type"] == "defense":
                    d_buffs["def"] = {"mult": 1.0 - power, "rounds": dur}
                    log.append(f"[第{r}回合] 防守者 {defender['name']} 施展【{skill['name']}】，使自身受到的伤害减免 {int(power*100)}%，持续 {dur} 回合。")
                else:
                    d_buffs["atk"] = {"mult": 1.0 + power, "rounds": dur}
                    log.append(f"[第{r}回合] 防守者 {defender['name']} 施展【{skill['name']}】，使自身攻击提升 {int(power*100)}%，持续 {dur} 回合。")
                action_taken = True
                
        # 3. 施展攻击技能
        if not action_taken:
            atk_skills = [s for s in d_skills if s["type"] in {"attack", "multi_hit"} and d_mp >= s.get("mp_cost", 0)]
            if atk_skills:
                skill = random.choice(atk_skills)
                d_mp -= skill.get("mp_cost", 0)
                if skill["type"] == "attack":
                    dmg = max(1, int(d_eff_atk * skill["power"]) - c_eff_def + random.randint(-1, 2))
                    c_hp -= dmg
                    log.append(f"[第{r}回合] 防守者 {defender['name']} 施展【{skill['name']}】，对 {challenger['name']} 造成 {dmg} 点伤害。")
                else:
                    hits = skill.get("hits", 2)
                    total = 0
                    for h in range(hits):
                        dmg = max(1, int(d_eff_atk * skill["power"]) - c_eff_def + random.randint(-1, 2))
                        total += dmg
                    c_hp -= total
                    log.append(f"[第{r}回合] 防守者 {defender['name']} 施展【{skill['name']}】，{hits}连击！对 {challenger['name']} 共造成 {total} 点伤害。")
                action_taken = True
                
        # 4. 普通攻击
        if not action_taken:
            dmg = max(1, d_eff_atk - c_eff_def + random.randint(-1, 2))
            c_hp -= dmg
            log.append(f"[第{r}回合] 防守者 {defender['name']} 催动灵力，一掌拍向 {challenger['name']}，造成 {dmg} 点伤害。")

        # 检查是否击杀挑战者
        if c_hp <= 0:
            log.append(f"【斗法结束】挑战者 {challenger['name']} 支撑不住，败下阵来！防守者 {defender['name']} 获得胜利！")
            winner_id = defender["user_id"]
            break
            
        # 递减 buff 持续时间
        decrement_buffs(c_buffs)
        decrement_buffs(d_buffs)
        
    # 如果 30 回合未分胜负，血量百分比高者胜；若相等则防守者胜
    if winner_id is None:
        c_pct = c_hp / c_max_hp
        d_pct = d_hp / d_max_hp
        log.append(f"【斗法超时】双方酣战30回合仍未决出生死！开始清算血量百分比。")
        log.append(f"挑战者剩余气血：{c_hp}/{c_max_hp} ({int(c_pct*100)}%)，防守者剩余气血：{d_hp}/{d_max_hp} ({int(d_pct*100)}%)。")
        if c_pct > d_pct:
            log.append(f"挑战者 {challenger['name']} 气血百分比更高，获得胜利！")
            winner_id = challenger["user_id"]
        else:
            log.append(f"防守者 {defender['name']} 稳守道心，判定获得胜利！")
            winner_id = defender["user_id"]

    # 4. 积分计算
    score_diff = defender.get("arena_score", 1000) - challenger.get("arena_score", 1000)
    
    if winner_id == challenger["user_id"]:
        score_change = max(10, min(35, 20 + int(score_diff * 0.05)))
    else:
        score_change = max(5, min(25, 12 - int(score_diff * 0.03)))
        
    return winner_id, score_change, log
