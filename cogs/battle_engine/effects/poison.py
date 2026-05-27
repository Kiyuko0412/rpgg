from ..effect import Effect
from ..event import TurnStart, Damage

class Poison(Effect):
    """中毒效果"""
    priority = 0

    def __init__(self, dmg, t):
        self.dmg = dmg
        self.t = t

    def on_event(self, ev, btl):
        if isinstance(ev, TurnStart) and ev.entity == self.owner:
            self.owner.hp = max(0, self.owner.hp - self.dmg)
            btl.log.append(f"🤢 {self.owner.name} 因為中毒噴了 {self.dmg} 點血")
            self.t -= 1
            if self.t <= 0:
                if self in self.owner.effects:
                    self.owner.effects.remove(self)
