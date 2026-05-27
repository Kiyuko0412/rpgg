class Event:
    pass

class Damage(Event):
    """受傷"""
    def __init__(self, source, target, amount, tags=None):
        self.source = source # 誰打的
        self.target = target # 打誰
        self.amount = amount # 痛
        self.tags = set(tags or []) 

class Heal(Event):
    """治療"""
    def __init__(self, source, target, amount, tags=None):
        self.source = source
        self.target = target
        self.amount = amount
        self.tags = set(tags or [])

class TurnStart(Event):
    """開始"""
    def __init__(self, e):
        self.entity = e

class TurnEnd(Event):
    """結束"""
    def __init__(self, e):
        self.entity = e

class SkillUsed(Event):
    """技能發動"""
    def __init__(self, c, t, sk):
        self.caster = c
        self.target = t
        self.skill = sk
