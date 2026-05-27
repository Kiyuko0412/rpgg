from ..effect import Effect
from ..event import Damage

class Stealth(Effect):
    """隱身效果"""
    priority = 12

    def __init__(self, mul=1.5):
        self.mul = mul

    def on_event(self, ev, btl):
        if isinstance(ev, Damage) and ev.source == self.owner:
            ev.amount = int(ev.amount * self.mul)
            btl.log.append(f"👤 {self.owner.name} 從陰影中現身！")
            if self in self.owner.effects:
                self.owner.effects.remove(self)
        
        # 被打有機率躲
        if isinstance(ev, Damage) and ev.target == self.owner:
            ev.amount = int(ev.amount * 0.5)
            btl.log.append(f"👤 {self.owner.name} 利用隱身躲避了部分傷害")
