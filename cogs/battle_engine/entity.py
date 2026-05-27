class Entity:
    """戰鬥中的玩家或怪"""
    def __init__(self, name, hp, m_hp=None, mp=0, m_mp=0, atk=0, df=0):
        self.name = name
        self.max_hp = m_hp if m_hp is not None else hp
        self.hp = hp
        self.max_mp = m_mp
        self.mp = mp
        self.atk = atk
        self.df = df
        self.effects = [] # 目前身上的效果
        self.skills = []  # 擁有的技能名清單
        self.skill_cds = {} # 技能冷卻：{技能名: 剩餘回合}

    def add_eff(self, eff):
        """掛效果"""
        eff.owner = self
        self.effects.append(eff)

    def is_alive(self):
        """還活著嗎"""
        return self.hp > 0

    def tick_cds(self):
        """減 CD"""
        for s in list(self.skill_cds.keys()):
            if self.skill_cds[s] > 0:
                self.skill_cds[s] -= 1
            if self.skill_cds[s] == 0:
                del self.skill_cds[s]

    def can_use(self):
        """哪些招能放"""
        return [s for s in self.skills if self.skill_cds.get(s, 0) == 0]
