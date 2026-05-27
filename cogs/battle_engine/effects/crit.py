import random
from ..effect import Effect
from ..event import Damage

class Crit(Effect):
    """爆擊"""
    priority = 15

    def __init__(self, rate=0.1, mul=1.5):
        self.rate = rate # 爆擊率
        self.mul = mul   # 爆擊倍率

    def on_event(self, ev, btl):
        if isinstance(ev, Damage) and ev.source == self.owner:
            if random.random() < self.rate:
                ev.amount = int(ev.amount * self.mul)
                ev.tags.add("crit")
                btl.log.append(f"💥 {self.owner.name} 打出了爆擊！")
