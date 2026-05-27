from ..effect import Effect
from ..event import Damage

class Defense(Effect):
    """固定減傷"""
    priority = 5

    def __init__(self, val):
        self.val = val
    
    def on_event(self, ev, btl):
        if isinstance(ev, Damage) and ev.target == self.owner:
            ev.amount = max(0, ev.amount - self.val)
