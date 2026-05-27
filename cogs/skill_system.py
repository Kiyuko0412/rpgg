import discord
from discord import SelectOption
from discord.ui import Select, View
from discord.ext import commands
from .database import *
import random
import math


S_PER_PAGE = 10 

class LearnSkillView(View):
    """學習介面"""
    def __init__(self, ctx, sys, s_n, parent: 'SkillTreeView'):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.sys = sys
        self.s_n = s_n
        self.parent = parent

        btn = discord.ui.Button(
            label=f"學習 {self.s_n}",
            style=discord.ButtonStyle.success,
            custom_id=f"learn:{self.s_n}"
        )
        btn.callback = self.learn_cb
        self.add_item(btn)

    async def learn_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("這不是你的按鈕啦。", ephemeral=True)
            return

        res = await self.sys.learn_sk(self.ctx, str(self.ctx.author.id), self.s_n)
        
        if not interaction.response.is_done():
            await interaction.response.send_message(res, ephemeral=True)
        else:
            await interaction.followup.send(res, ephemeral=True)

        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id == f"learn:{self.s_n}":
                item.disabled = True
                break
        
        try: await interaction.message.edit(view=self)
        except: pass 

        # 重新刷新後面的大選單
        await self.parent.refresh(interaction)


class SkillTreeView(View):
    """技能樹"""
    def __init__(self, ctx, sys, p_d, p_s):
        super().__init__(timeout=180)
        self.ctx, self.sys, self.p_d, self.p_s = ctx, sys, p_d, p_s
        self.cat, self.sel_s, self.pg = None, None, 0 

        # 初始分類選單
        c_opts = [SelectOption(label=c, value=c) for c in self.sys.tree.keys()]
        cat_sel = Select(placeholder="想看哪一系的技能？", options=c_opts or [SelectOption(label="無", value="none")], row=0)
        cat_sel.callback = self.cat_cb
        self.add_item(cat_sel)

        # 裝備選單
        learned = self.p_s.get('skills', [])
        eq = self.p_s.get('equipped_skills', [])

        e_opts = [SelectOption(label=s, value=s) for s in learned if s not in eq]
        e_sel = Select(placeholder="穿上技能", options=e_opts[:25] or [SelectOption(label="沒招可用", value="none")], row=1)
        e_sel.callback = self.eq_cb
        self.add_item(e_sel)

        u_opts = [SelectOption(label=s, value=s) for s in eq]
        u_sel = Select(placeholder="脫掉技能", options=u_opts or [SelectOption(label="沒裝招式", value="none")], row=2)
        u_sel.callback = self.ueq_cb
        self.add_item(u_sel)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("別亂動別人的技能樹啦。", ephemeral=True)
            return False
        return True

    async def refresh(self, interaction: discord.Interaction):
        """重新整理整個畫面"""
        if not interaction.response.is_done():
            await interaction.response.defer() 

        uid = str(self.ctx.author.id)
        self.p_d = await get_p_data(uid)
        self.p_s = await get_p_skills(uid)

        if not self.p_d:
            await interaction.followup.send("找不到你的資料，是不是沒註冊？", ephemeral=True)
            return

        self.clear_items() 
    
        # 分類選單
        c_opts = [SelectOption(label=c, value=c) for c in self.sys.tree.keys()]
        cat_sel = Select(placeholder=self.cat or "想看哪一系的技能？", options=c_opts or [SelectOption(label="無", value="none")], row=0)
        cat_sel.callback = self.cat_cb
        self.add_item(cat_sel)

        learned = self.p_s.get('skills', [])
        eq = self.p_s.get('equipped_skills', [])

        # 沒選分類
        if not self.cat or self.cat == "none":
            e_opts = [SelectOption(label=s, value=s) for s in learned if s not in eq]
            e_sel = Select(placeholder="穿上技能", options=e_opts[:25] or [SelectOption(label="沒招可用", value="none")], row=1)
            e_sel.callback = self.eq_cb
            self.add_item(e_sel)

            u_opts = [SelectOption(label=s, value=s) for s in eq]
            u_sel = Select(placeholder="脫掉技能", options=u_opts or [SelectOption(label="沒裝招式", value="none")], row=2)
            u_sel.callback = self.ueq_cb
            self.add_item(u_sel)
            
            emb = discord.Embed(title="技能管理中心", description="點選分類學新招，或在下方調整裝備。", color=discord.Color.gold())
            emb.set_footer(text=f"LV.{self.p_d['level']} | 金幣: {self.p_d['money']}")

        # 選了分類
        elif self.cat in self.sys.tree:
            emb = self.gen_cat_emb(self.cat)
            back = discord.ui.Button(label="回主選單", style=discord.ButtonStyle.grey, row=3)
            back.callback = self.back_cb
            self.add_item(back)
            
            all_s = []
            for t in self.sys.tree[self.cat]:
                for s in self.sys.tree[self.cat][t]:
                    all_s.append({'name': s})

            self.total = len(all_s)
            start = self.pg * S_PER_PAGE
            p_list = all_s[start : start + S_PER_PAGE]

            if not p_list and self.pg > 0:
                self.pg = 0
                p_list = all_s[:S_PER_PAGE]

            s_opts = [SelectOption(label=s['name'], value=s['name']) for s in p_list]
            t_pgs = math.ceil(self.total / S_PER_PAGE) if self.total > 0 else 1
            s_sel = Select(placeholder=f"挑一招來學 (第 {self.pg + 1}/{t_pgs} 頁)", options=s_opts or [SelectOption(label="無", value="none")], row=2)
            s_sel.callback = self.sk_cb
            self.add_item(s_sel)

            if t_pgs > 1:
                prev = discord.ui.Button(label="上一頁", disabled=self.pg == 0, row=3)
                prev.callback = self.prev_cb
                self.add_item(prev)

                nxt = discord.ui.Button(label="下一頁", disabled=self.pg >= t_pgs - 1, row=3)
                nxt.callback = self.next_cb
                self.add_item(nxt)

        try:
            if interaction.message: await interaction.message.edit(embed=emb, view=self)
            elif hasattr(self, 'message') and self.message: await self.message.edit(embed=emb, view=self)
        except Exception as e: print(f"Refresh error: {e}")

    async def cat_cb(self, interaction: discord.Interaction):
        v = interaction.data['values'][0]
        self.cat, self.pg, self.sel_s = (None if v == "none" else v), 0, None
        await self.refresh(interaction)

    async def back_cb(self, interaction: discord.Interaction):
        self.cat, self.sel_s, self.pg = None, None, 0
        await self.refresh(interaction)

    async def prev_cb(self, interaction: discord.Interaction):
        if self.pg > 0: self.pg -= 1
        self.sel_s = None
        await self.refresh(interaction)

    async def next_cb(self, interaction: discord.Interaction):
        if self.pg < math.ceil(self.total / S_PER_PAGE) - 1: self.pg += 1
        self.sel_s = None
        await self.refresh(interaction)

    async def sk_cb(self, interaction: discord.Interaction):
        name = interaction.data['values'][0]
        if name == "none": return
        self.sel_s = name
        if not interaction.response.is_done(): await interaction.response.defer(ephemeral=True)

        sk = self.sys.get_sk(name)
        if not sk: return

        req = self.sys.reqs.get(name, {})
        emb = discord.Embed(title=f"招式詳情：{sk.name}", description=sk.desc, color=discord.Color.purple())
        emb.add_field(name="學習條件", value=f"LV.{req.get('level_req', 1)} | {req.get('cost', 0)} 金幣", inline=True)
        
        i_req = req.get('item_requirements', {})
        i_t = ", ".join([f"{i} x{q}" for i, q in i_req.items()])
        emb.add_field(name="需要材料", value=i_t or "不需要", inline=False)
        emb.add_field(name="數值", value=f"冷卻 {sk.cd} 回合 | 耗魔 {sk.mp_cost} | 命中 {int(sk.hit*100)}%", inline=True)

        learned = self.p_s.get('skills', [])
        is_l = name in learned
        emb.add_field(name="狀態", value="已學習" if is_l else "未習得", inline=False)

        v = LearnSkillView(self.ctx, self.sys, name, self)
        await interaction.followup.send(embed=emb, view=v, ephemeral=True)
        self.sel_s = None
        await self.refresh(interaction)

    async def eq_cb(self, interaction: discord.Interaction):
        n = interaction.data['values'][0]
        if n == "none": return
        if not interaction.response.is_done(): await interaction.response.defer() 
        res = await self.sys.eq_sk(str(self.ctx.author.id), n)
        await interaction.followup.send(res, ephemeral=True) 
        await self.refresh(interaction) 

    async def ueq_cb(self, interaction: discord.Interaction):
        n = interaction.data['values'][0]
        if n == "none": return
        if not interaction.response.is_done(): await interaction.response.defer() 
        res = await self.sys.ueq_sk(str(self.ctx.author.id), n)
        await interaction.followup.send(res, ephemeral=True) 
        await self.refresh(interaction) 

    def gen_cat_emb(self, cat):
        emb = discord.Embed(title=f"【{cat}】系技能樹", color=discord.Color.blue())
        emb.set_footer(text=f"LV.{self.p_d['level']} | 金幣: {self.p_d['money']}")
        learned = self.p_s.get('skills', [])
        for t, s_list in self.sys.tree[cat].items():
            lines = [f"{'✅' if s in learned else '❌'} {s}" for s in s_list]
            emb.add_field(name=t, value="\n".join(lines) if lines else "空", inline=False)
        return emb

from .battle_engine.entity import Entity
from .battle_engine.skill import Skill, calc_dmg
from .battle_engine.event import Damage, Heal
from .battle_engine.effects.defense import Defense
from .battle_engine.effects.t_defense import TDefense
from .battle_engine.effects.dodge import Dodge
from .battle_engine.effects.invincible import Invincible
from .battle_engine.effects.damage_reduction import DamageReduction
from .battle_engine.effects.stealth import Stealth

class Character(Entity):
    """繼承自戰鬥實體的角色類別"""
    def __init__(self, name, hp, atk, df, m_hp=None, mp=50, m_mp=50):
        super().__init__(name, hp, m_hp, mp, m_mp, atk, df)

class SkillSystem:
    """技能系統核心邏輯"""
    skills = {}
    tree = {
        "攻擊": {
            "層級1": ["基礎攻擊", "快速打擊"],
            "層級2": ["強力一擊", "盾牌猛擊"],
            "層級3": ["強化打擊", "奧術衝擊"]
        },
        "防禦": {
            "層級1": ["基礎防禦", "格擋"],
            "層級2": ["鐵壁", "反彈傷害"],
            "層級3": ["無敵護盾", "生命汲取"]
        },
        "功能": {
            "層級1": ["治療"],
            "層級2": ["治癒術", "加速"],
            "層級3": ["隱身", "傳送", "時間操控", "術式順轉","領域展開"]
        }
    }
    reqs = {
        "基礎攻擊": {"cost": 1, "level_req": 1, "item_requirements": {}},
        "快速打擊": {"cost": 1, "level_req": 1, "item_requirements": {}},
        "強力一擊": {"cost": 5, "level_req": 5, "item_requirements": {}},
        "盾牌猛擊": {"cost": 5, "level_req": 5, "item_requirements": {"貓耳": 2, "香菸": 1}},
        "強化打擊": {"cost": 10, "level_req": 10, "item_requirements": {}},
        "奧術衝擊": {"cost": 10, "level_req": 10, "item_requirements": {}},
        "基礎防禦": {"cost": 1, "level_req": 1, "item_requirements": {}},
        "格擋": {"cost": 1, "level_req": 1, "item_requirements": {}},
        "鐵壁": {"cost": 5, "level_req": 5, "item_requirements": {}},
        "反彈傷害": {"cost": 5, "level_req": 5, "item_requirements": {}},
        "無敵護盾": {"cost": 20, "level_req": 10, "item_requirements": {}},
        "生命汲取": {"cost": 20, "level_req": 10, "item_requirements": {}},
        "治療": {"cost": 1, "level_req": 1, "item_requirements": {}},
        "治癒術": {"cost": 5, "level_req": 5, "item_requirements": {}},
        "加速": {"cost": 5, "level_req": 5, "item_requirements": {}},
        "隱身": {"cost": 20, "level_req": 10, "item_requirements": {}},
        "傳送": {"cost": 20, "level_req": 10, "item_requirements": {}},
        "時間操控": {"cost": 20, "level_req": 10, "item_requirements": {}},
        "領域展開": {"cost": 20, "level_req": 10, "item_requirements": {}},
        "術式順轉": {"cost": 20, "level_req": 10, "item_requirements": {}}
    }

    @classmethod
    def reg(cls, n, d, cd, mp, f, h):
        cls.skills[n] = Skill(n, d, cd, mp, f, h)

    @classmethod
    def get_sk(cls, n):
        return cls.skills.get(n)

    @classmethod
    async def learn_sk(cls, ctx, pid, n):
        p = await get_p_data(pid)
        if not p: return "找不到資料。"

        sk = cls.get_sk(n)
        if not sk: return f"找不到技能 {n}。"

        p_s = await get_p_skills(pid)
        if n in p_s['skills']: return f"你早就學過 {n} 啦。"

        r = cls.reqs.get(n)
        if not r: return f"沒這招的學習方法。"

        if p['level'] < r["level_req"]: return f"等級不夠，要 {r['level_req']} 級。"
        if p['money'] < r["cost"]: return f"錢不夠，要 {r['cost']} 金幣。"

        # 扣東西
        i_req = r.get("item_requirements", {})
        if i_req:
            bag = p.get('items', {})
            missing = []
            for i_n, q in i_req.items():
                iid = get_i_id_by_n(i_n)
                if not iid: return f"後台配方出錯：{i_n}"
                if bag.get(str(iid), 0) < q:
                    missing.append(f"{i_n} x{q - bag.get(str(iid), 0)}")
            
            if missing: return f"還缺這些材料：{', '.join(missing)}。"

            for i_n, q in i_req.items():
                iid = str(get_i_id_by_n(i_n))
                bag[iid] -= q
                if bag[iid] <= 0: del bag[iid]
            await set_p_data(pid, items=bag)

        new_m = p['money'] - r["cost"]
        await set_p_data(pid, money=new_m)
        
        p_s['skills'].append(n)
        await set_p_skills(pid, skills=p_s['skills'])
        return f"領悟了：{n}！剩餘金幣：{new_m}"

    @classmethod
    async def eq_sk(cls, pid, n):
        p_s = await get_p_skills(pid)
        if not p_s or n not in p_s['skills']: return f"你還沒學過 {n}。"
        if n in p_s['equipped_skills']: return f"早就裝備著了。"
        if len(p_s['equipped_skills']) >= 3: return "招式欄滿了，最多裝 3 個。"

        p_s['equipped_skills'].append(n)
        await set_p_skills(pid, equipped_skills=p_s['equipped_skills'])
        return f"裝備成功：{n}"

    @classmethod
    async def ueq_sk(cls, pid, n):
        p_s = await get_p_skills(pid)
        if not p_s or n not in p_s['equipped_skills']: return f"你沒裝這招啊。"
        p_s['equipped_skills'].remove(n)
        await set_p_skills(pid, equipped_skills=p_s['equipped_skills'])
        return f"已卸下：{n}"

class SkillCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def skill(self, ctx):
        """開啟技能樹管理介面"""
        try:
            uid = str(ctx.author.id)
            p_d = await get_p_data(uid)
            p_s = await get_p_skills(uid)
            if not p_d:
                await ctx.send("先去註冊角色吧！")
                return
            emb = discord.Embed(title="技能樹大廳", description="在這裡管理你的超能力。", color=discord.Color.gold())
            emb.set_footer(text=f"LV.{p_d['level']} | 金幣: {p_d['money']}")
            await ctx.send(embed=emb, view=SkillTreeView(ctx, SkillSystem, p_d, p_s))
        except Exception as e: await ctx.send(f"出錯啦：{e}")

async def setup(bot):
    await bot.add_cog(SkillCog(bot))

# 招式效果

async def sk_atk(c, t, b):
    d = calc_dmg(c, t, c.atk * 1.0)
    b.emit(Damage(source=c, target=t, amount=d))

async def sk_quick(c, t, b):
    d = calc_dmg(c, t, c.atk * 0.8)
    b.emit(Damage(source=c, target=t, amount=d))

async def sk_power(c, t, b):
    d = calc_dmg(c, t, c.atk * 2.5)
    b.emit(Damage(source=c, target=t, amount=d))

async def sk_heal(c, t, b):
    b.emit(Heal(source=c, target=c, amount=int(c.atk * 0.5)))

async def sk_zone(c, t, b):
    d = calc_dmg(c, t, c.atk * 2.0)
    b.log.append("「領域展開：無量空處。」")
    b.emit(Damage(source=c, target=t, amount=d))

async def sk_zone2(c, t, b):
    d = calc_dmg(c, t, c.atk * 3.5)
    h = int(c.atk * 4.5)
    b.log.append("「術式順轉：蒼。術式反轉：赫。」")
    b.log.append("虛式「茈」")
    b.emit(Damage(source=c, target=t, amount=d))
    b.emit(Heal(source=c, target=c, amount=h))

async def sk_shield_bash(c, t, b):
    bonus = 0
    try:
        items = await get_eq_items(str(c.name.id))
        if any(i[2] == "盾牌" for i in items):
            bonus = int(c.df * 0.5)
            b.log.append(f"{c.name} 的盾牌發威了！")
    except: pass
    d = calc_dmg(c, t, c.atk * 1.1 + bonus)
    b.emit(Damage(source=c, target=t, amount=d))

async def sk_mend(c, t, b):
    a = int(c.max_hp * 0.20)
    if c.hp < c.max_hp * 0.5:
        a += int(c.max_hp * 0.15)
        b.log.append(f"{c.name} 傷勢嚴重，治癒潛能爆發！")
    b.emit(Heal(source=c, target=c, amount=a))

async def sk_arcane(c, t, b):
    d = calc_dmg(c, t, int(c.max_mp * 0.5))
    b.emit(Damage(source=c, target=t, amount=d))

async def sk_def(c, t, b):
    c.add_eff(TDefense(value=int(c.df * 0.20), turns=3))
    b.log.append(f"{c.name} 擺出防禦架勢！")

async def sk_block(c, t, b):
    c.add_eff(Dodge(chance=1.0, turns=1))
    b.log.append(f"{c.name} 盯著對方的動作，準備格擋！")

async def sk_wall(c, t, b):
    c.add_eff(DamageReduction(percentage=0.50, turns=3))
    b.log.append(f"{c.name} 進入鐵壁狀態，感覺更硬了！")

async def sk_inv(c, t, b):
    c.add_eff(Invincible(turns=2))
    b.log.append(f"{c.name} 開啟了絕對防禦護盾！")

async def sk_siphon(c, t, b):
    d = calc_dmg(c, t, c.atk * 1.2)
    b.emit(Damage(source=c, target=t, amount=d))
    b.emit(Heal(source=c, target=c, amount=int(d * 0.5)))

async def sk_haste(c, t, b):
    for s, val in c.skill_cds.items():
        if s != "加速": c.skill_cds[s] = max(0, val - 1)
    b.log.append(f"{c.name} 感覺大腦轉速變快了，技能 CD 縮短！")

async def sk_stealth(c, t, b):
    c.add_eff(Stealth(multiplier=1.5))
    b.log.append(f"{c.name} 消失在陰影中，準備致命一擊！")

async def sk_tele(c, t, b):
    c.add_eff(Dodge(chance=0.75))
    b.log.append(f"{c.name} 使用了瞬移，讓對方抓不到位置！")

async def sk_time(c, t, b):
    for s in list(c.skill_cds.keys()):
        if s != "時間操控": c.skill_cds[s] = 0
    b.log.append(f"{c.name} 逆轉了局部時間，所有招式冷卻歸零！")

# 註冊
SkillSystem.reg("基礎攻擊", "一般的敲擊，造成 100% 傷害", 2, 0, sk_atk, 0.95)
SkillSystem.reg("快速打擊", "手速極快，傷害略低但冷卻短", 1, 0, sk_quick, 0.90)
SkillSystem.reg("強力一擊", "蓄力重擊，造成 250% 傷害", 3, 0, sk_power, 0.85)
SkillSystem.reg("治療", "簡單包紮，回 50% 攻擊力的血量", 2, 0, sk_heal, 1.0)
SkillSystem.reg("領域展開", "無量空處，造成 200% 傷害", 1, 0, sk_zone, 0.80)
SkillSystem.reg("術式順轉", "虛式「茈」，超高額傷害與回血", 5, 0, sk_zone2, 0.75)
SkillSystem.reg("盾牌猛擊", "用盾牌砸人，有額外防禦加成", 3, 0, sk_shield_bash, 0.90)
SkillSystem.reg("治癒術", "恢復 20% 最大生命，快死的時候更有效", 5, 0, sk_mend, 1.0)
SkillSystem.reg("奧術衝擊", "把魔力當炸彈丟，造成 50% 最大魔力傷害", 3, 0, sk_arcane, 0.92)
SkillSystem.reg("基礎防禦", "找掩護，3回合內加防禦", 3, 0, sk_def, 1.0)
SkillSystem.reg("格擋", "預判攻擊，下回合必定閃避物理傷害", 4, 0, sk_block, 1.0)
SkillSystem.reg("鐵壁", "縮起來，3回合內受傷減半", 5, 0, sk_wall, 1.0)
SkillSystem.reg("無敵護盾", "什麼都傷不了我，持續2回合", 8, 0, sk_inv, 1.0)
SkillSystem.reg("生命汲取", "吸取對方的生命力來補自己", 4, 0, sk_siphon, 0.90)
SkillSystem.reg("加速", "加速思考，所有技能 CD 減 1", 7, 0, sk_haste, 1.0)
SkillSystem.reg("隱身", "變透明，下次攻擊更痛且更難被打中", 6, 0, sk_stealth, 1.0)
SkillSystem.reg("傳送", "左右橫跳，閃避率大幅提升", 8, 0, sk_tele, 1.0)
SkillSystem.reg("時間操控", "我是時間的主人！所有招式 CD 重置", 10, 0, sk_time, 1.0)
