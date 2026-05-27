import random
from ..effect import Effect
from ..event import Damage, TurnEnd

class Dodge(Effect):
    """閃避效果"""
    priority = 20 

    def __init__(self, rate=0.5, t=1):
        self.rate = rate
        self.t = t

    def on_event(self, ev, btl):
        if isinstance(ev, Damage) and ev.target == self.owner:
            if random.random() < self.rate:
                ev.amount = 0
                ev.tags.add("dodged")
                btl.log.append(f"{self.owner.name} 閃開了攻擊！")

        if isinstance(ev, TurnEnd) and ev.entity == self.owner:
            self.t -= 1
            if self.t <= 0:
                if self in self.owner.effects:
                    self.owner.effects.remove(self)
