from ..effect import Effect
from ..event import Damage, TurnEnd

class DamageReduction(Effect):
    """百分比減傷"""
    priority = 8

    def __init__(self, rate=0.5, t=1):
        self.rate = rate
        self.t = t

    def on_event(self, ev, btl):
        if isinstance(ev, Damage) and ev.target == self.owner:
            ev.amount = int(ev.amount * (1 - self.rate))

        if isinstance(ev, TurnEnd) and ev.entity == self.owner:
            self.t -= 1
            if self.t <= 0:
                if self in self.owner.effects:
                    self.owner.effects.remove(self)
