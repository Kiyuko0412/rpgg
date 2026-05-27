from .event import Damage, Heal, TurnEnd, TurnStart, SkillUsed

class Battle:
    def __init__(self, es):
        self.es = es # 參戰清單
        self.log = [] 

    def emit(self, ev):
        effs = []
        for e in self.es:
            effs.extend(e.effects)

        #  priority 大的在前
        for f in sorted(effs, key=lambda x: -x.priority):
            f.on_event(ev, self)

        self.handle(ev)

    def handle(self, ev):
        """結算"""
        if isinstance(ev, Damage):
            dmg = max(0, int(ev.amount))
            ev.target.hp = max(0, ev.target.hp - dmg)
            src = ev.source.name if ev.source else "神秘力量"
            self.log.append(f"{src} 對 {ev.target.name} 造成 {dmg} 點傷害")

        elif isinstance(ev, Heal):
            amt = max(0, int(ev.amount))
            old = ev.target.hp
            ev.target.hp = min(ev.target.max_hp, ev.target.hp + amt)
            diff = ev.target.hp - old
            src = ev.source.name if ev.source else "神秘力量"
            if diff > 0:
                self.log.append(f"{src} 幫 {ev.target.name} 補了 {diff} 點血")

        elif isinstance(ev, SkillUsed):
            self.log.append(f"{ev.caster.name} 施展了「{ev.skill.name}」！")

    def start_turn(self, e):
        """回合開始"""
        self.emit(TurnStart(e))

