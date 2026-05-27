from ..effect import Effect
from ..event import SkillUsed

class CooldownReduction(Effect):
    """減少技能 CD"""
    priority = 1

    def __init__(self, red=1):
        self.red = red

    def on_event(self, ev, btl):
        if isinstance(ev, SkillUsed) and ev.caster == self.owner:
            sn = ev.skill.name
            if sn in self.owner.skill_cds:
                self.owner.skill_cds[sn] = max(0, self.owner.skill_cds[sn] - self.red)
