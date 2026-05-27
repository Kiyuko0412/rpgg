from ..effect import Effect
from ..event import Damage, TurnEnd

class Invincible(Effect):
    """無敵效果"""
    priority = 25 # 比閃避高

    def __init__(self, t=1):
        self.t = t

    def on_event(self, ev, btl):
        if isinstance(ev, Damage) and ev.target == self.owner:
            ev.amount = 0
            ev.tags.add("invincible")
            btl.log.append(f"✨ {self.owner.name} 處於無敵狀態，沒受傷。")

        if isinstance(ev, TurnEnd) and ev.entity == self.owner:
            self.t -= 1
            if self.t <= 0:
                if self in self.owner.effects:
                    self.owner.effects.remove(self)
