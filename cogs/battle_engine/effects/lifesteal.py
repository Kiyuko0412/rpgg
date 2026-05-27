from ..effect import Effect
from ..event import Damage, Heal

class Lifesteal(Effect):
    """吸血效果"""
    priority = 1 

    def __init__(self, rate=0.1):
        self.rate = rate

    def on_event(self, ev, btl):
        if isinstance(ev, Damage) and ev.source == self.owner and ev.target != self.owner:
            amt = int(ev.amount * self.rate)
            if amt > 0:
                btl.emit(Heal(source=self.owner, target=self.owner, amount=amt, tags=["lifesteal"]))
