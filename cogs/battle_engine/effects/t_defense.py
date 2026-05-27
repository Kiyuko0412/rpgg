from ..effect import Effect
from ..event import Damage, TurnEnd

class TDefense(Effect):
    """臨時防禦"""
    priority = 10

    def __init__(self, val, t):
        self.val = val
        self.t = t

    def on_event(self, ev, btl):
        if isinstance(ev, Damage) and ev.target == self.owner:
            ev.amount = max(0, ev.amount - self.val)

        if isinstance(ev, TurnEnd) and ev.entity == self.owner:
            self.t -= 1
            if self.t <= 0:
                if self in self.owner.effects:
                    self.owner.effects.remove(self)
