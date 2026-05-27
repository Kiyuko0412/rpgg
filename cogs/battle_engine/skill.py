import random
import math
from .event import Damage, Heal, SkillUsed

class Skill:
    """技能"""
    def __init__(self, name, desc, cd, mp_cost, func, hit):
        self.name = name
        self.desc = desc
        self.cd = cd
        self.mp_cost = mp_cost
        self.func = func
        self.hit = hit

    async def use(self, caster, target, battle):
        """放招式"""
        if caster.mp < self.mp_cost:
            battle.log.append(f"{caster.name} 魔力不夠，放不出「{self.name}」...")
            return False

        caster.mp -= self.mp_cost
        caster.skill_cds[self.name] = self.cd

        battle.emit(SkillUsed(caster, target, self))

        # 判定命中
        if random.random() > self.hit:
            battle.log.append(f"{caster.name} 的「{self.name}」沒中，可惜了。")
            return True

        # 跑技能效果
        await self.func(caster, target, battle)
        return True

def calc_dmg(atk, df_obj, base):
    """傷害公式"""
    d = base * (1 + random.uniform(-0.1, 0.1)) # 浮動
    df = df_obj.df
    if df <= 0: df = 1
    
    diff = max(d - df, 0)
    log_val = math.log(1 + diff / df)
    res = (df * 2) * log_val

    return max(1, int(res))
