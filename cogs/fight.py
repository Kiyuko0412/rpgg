import discord
import random
import json
from discord.ext import commands
from discord import Embed, ButtonStyle
from discord.ui import Button, View
import aiosqlite
from .skill_system import SkillSystem, Character
from .database import *
from .battle_engine.battle import Battle
from .battle_engine.event import TurnStart, TurnEnd
from .battle_engine.effects.lifesteal import Lifesteal
from .battle_engine.effects.cooldown_reduction import CooldownReduction

class SkBtn(discord.ui.Button):
    """招式按鈕"""
    def __init__(self, s):
        super().__init__(style=discord.ButtonStyle.primary, label=s.name)
        self.s = s

    async def callback(self, it: discord.Interaction):
        await self.view.use_sk(it, self.s.name)

class SkipBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="跳過回合")

    async def callback(self, it: discord.Interaction):
        await self.view.skip(it)

class CloseBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="關閉")

    async def callback(self, it: discord.Interaction):
        await it.message.delete()

class RefreshBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.success, label="刷新")

    async def callback(self, it: discord.Interaction):
        await self.view.refresh(it)

class BattleView(discord.ui.View):
    """戰鬥"""
    def __init__(self, cog, p, e, msg, pic, intro, m_n, tier, drop, chan):
        super().__init__(timeout=None)
        self.cog, self.uid = cog, p.name.id
        self.p, self.e, self.msg = p, e, msg
        self.pic, self.intro = pic, intro
        self.m_n, self.tier = m_n, tier
        self.drop_d, self.chan = drop, chan
        self.done = False

        self.btl = Battle([self.p, self.e])
        self.logs = self.btl.log
        self.up_btns()

    def up_btns(self):
        """更新按鈕"""
        self.clear_items()
        if not self.done:
            for s_n in self.p.skills:
                sk = SkillSystem.get_sk(s_n)
                if sk:
                    btn = SkBtn(sk)
                    cd = self.p.skill_cds.get(s_n, 0)
                    if cd > 0:
                        btn.disabled = True
                        btn.label = f"{sk.name} ({cd}R)"
                    self.add_item(btn)
            self.add_item(SkipBtn())
            self.add_item(RefreshBtn())
        else:
            self.add_item(CloseBtn())

    async def skip(self, it: discord.Interaction):
        if self.done: return
        self.logs.append(f"{self.p.name} 決定先觀望一下。")
        self.btl.emit(TurnStart(self.p))
        self.btl.emit(TurnEnd(self.p))
        await self.e_turn(it)

    async def use_sk(self, it: discord.Interaction, s_n):
        if self.done: return
        sk = SkillSystem.get_sk(s_n)
        if sk:
            self.btl.emit(TurnStart(self.p))
            if await sk.use(self.p, self.e, self.btl):
                self.btl.emit(TurnEnd(self.p))
                if not self.e.is_alive():
                    await self.finish(it, True)
                    return
                await self.e_turn(it)
            else:
                await it.response.send_message("招式放不出來...", ephemeral=True)

    async def e_turn(self, it: discord.Interaction):
        """換怪動手"""
        self.btl.emit(TurnStart(self.e))
        can = self.e.can_use()
        if can:
            sk = SkillSystem.get_sk(random.choice(can))
            if sk: await sk.use(self.e, self.p, self.btl)
        else:
            self.logs.append(f"{self.e.name} 發呆中...")

        self.btl.emit(TurnEnd(self.e))
        self.logs.append("─" * 20)

        if not self.p.is_alive():
            await self.finish(it, False)
            return

        self.p.tick_cds()
        self.e.tick_cds()
        await self.refresh(it)

    async def refresh(self, it: discord.Interaction):
        self.up_btns()
        await it.response.edit_message(embed=self.gen_emb(), view=self)

    def gen_emb(self):
        """生成血條與狀態 Embed"""
        p_hp = draw_hp(self.p.hp, self.p.max_hp)
        e_hp = draw_hp(self.e.hp, self.e.max_hp)
        emb = discord.Embed(title=f"LV.{self.tier} {self.m_n}", description=f"{self.intro}\n~~{'　'*16}~~\n{e_hp} {round(self.e.hp*100/self.e.max_hp, 1)}%\nHP: {self.e.hp} ATK: {self.e.atk} DEF: {self.e.df}", color=0x4b9eaf)
        emb.set_thumbnail(url=self.pic)
        lgs = "\n".join(self.logs[-6:])  
        emb.add_field(name="戰況紀錄", value=f"```py\n{lgs}```", inline=False)
        emb.add_field(name=f"{self.p.name} 的狀態", value=f"{p_hp} {round(self.p.hp*100/self.p.max_hp, 1)}%\nHP: {self.p.hp} ATK: {self.p.atk} DEF: {self.p.df}", inline=False)
        return emb

    async def finish(self, it: discord.Interaction, win):
        """戰鬥結算"""
        self.done = True
        self.up_btns()
        self.logs.append("─" * 20)
        if win:
            self.logs.append(f"\n成功討伐 {self.e.name}！")
            drops = roll_drops(parse_json(self.drop_d))
            await give_items(str(self.uid), drops)
            res = await gen_drop_txt(drops)
            self.logs.append(f"獲得獎勵：{res}" if res else "運氣不太好，啥都沒噴...")
            award = await self.cog.award(self.uid, self.e.name)
            self.logs.append(f"{self.p.name} {award}")
        else:
            self.logs.append(f"{self.p.name} 倒下了...")

        m_cog = self.cog.bot.get_cog('Map')
        if m_cog and self.uid in m_cog.players:
            m_cog.players[self.uid]['in_combat'] = False
        await it.response.edit_message(embed=self.gen_emb(), view=self)

def parse_json(s):
    try: return json.loads(s)
    except: return {}

class Fight(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def mapfight(self, au, cha, mid: str, tier: int, mn: str = None, boss: bool = False):
        """地圖遇怪"""
        s_n, rate = None, 1.0
        try:
            with open('cogs/maps_data.json', 'r', encoding='utf-8') as f:
                maps = json.load(f)
            m_list = maps.get(mid, {}).get("monsters", [])
            
            if mn:
                s_n = mn
                for m in m_list:
                    if m.get("name") == mn:
                        rate = m.get("reinforcement_rate", 1.0)
                        break
            else:
                if boss and m_list:
                    s_n, rate = m_list[0].get("name"), m_list[0].get("reinforcement_rate", 1.0)
                elif m_list:
                    v = [m for m in m_list if m.get("name")]
                    if v:
                        sel = random.choice(v)
                        s_n, rate = sel.get("name"), sel.get("reinforcement_rate", 1.0)
            
            if not s_n: s_n = await get_rnd_m_n(tier)
            if not s_n:
                await cha.send("這附近好像挺安靜的，沒看到怪。")
                return

            await self.spawn(au.id, cha, s_n, au, tier, rate)
        except Exception as e:
            await cha.send(f"戰鬥發生意外: {e}")

    async def spawn(self, uid, chan, mn, user, tier, rate: float):
        try:
            m_d = await get_m_data(mn, tier=tier)
            if not m_d: return

            hp = max(1, int(m_d['m_maxhp'] * rate))
            atk, df = int(m_d['m_atk'] * rate), int(m_d['m_def'] * rate)
            
            p_d = await get_p_data(str(uid))
            p_s = await get_p_skills(str(uid))

            enemy = Character(mn, hp, atk, df)
            enemy.skills = m_d.get('skills', [])
            for s in enemy.skills: enemy.skill_cds[s] = 0

            p = Character(user, p_d['hp'], p_d['atk'], p_d['defense'], m_hp=p_d['maxhp'], mp=p_d['mp'], m_mp=p_d['maxmp'])
            p.skills = p_s['equipped_skills']
            for s in p.skills: p.skill_cds[s] = 0

            # 裝備被動
            try:
                eqs = await get_eq_items(str(uid))
                for i in eqs:
                    if len(i) > 7:
                        eff = i[7]
                        if eff == "吸血": p.add_eff(Lifesteal(percentage=0.10))
                        elif eff == "減少技能冷卻時間": p.add_eff(CooldownReduction(reduction=1))
            except: pass

            emb = discord.Embed(title=f"LV.{m_d.get('current_tier', 1)} {mn}", description=f"{m_d['m_intro']}\n~~{'　'*16}~~\n{'█'*20} 100%\nHP: {enemy.hp} ATK: {enemy.atk} DEF: {enemy.df}", color=0x4b9eaf)
            emb.set_thumbnail(url=m_d['picture'])
            emb.add_field(name="戰況紀錄", value="```(o・ω・)=◯)`ν゜)```", inline=False)
            emb.add_field(name="你的狀態", value=f"{'█'*20} 100%\nHP: {p.hp} ATK: {p.atk} DEF: {p.df}", inline=False)
            
            msg = await chan.send(embed=emb)
            await msg.edit(view=BattleView(self, p, enemy, msg, m_d['picture'], m_d['m_intro'], mn, m_d['current_tier'], m_d['dropitem'], chan))
        except Exception as e:
            await chan.send(f"生成對手時出事了: {e}")

    async def award(self, uid, mn):
        """發獎勵"""
        m_d = await get_m_data(mn)
        if not m_d: return "找不到怪物數據"
        
        exp, gold = m_d['dropexp'], m_d['dropmoney']
        p_d = await get_p_data(str(uid))
        if not p_d: return "玩家不存在"
        
        await set_p_data(str(uid), money=p_d['money'] + gold)
        res, err = await add_exp(str(uid), exp)
        if err: return err
        
        lv_msg = "\n".join(res['level_up_messages'])
        return f"拿到 {exp} 經驗與 {gold} 金幣！\n{lv_msg}"

def draw_hp(cur, mx):
    """畫血條"""
    p = cur / mx
    f = int(p * 10)
    pt = int((p * 10 - f) * 8)
    bar = ('██' * f + ('█' if pt > 0 else '')).ljust(20, '░')
    return bar

def roll_drops(d_list):
    """掉落物品"""
    res = {}
    for n, d in d_list.items():
        if random.random() < d["chance"]:
            iid = get_i_id_by_n(n)
            if iid:
                res[iid] = random.randint(*d["quantity_range"]) if "quantity_range" in d else d["quantity"]
    return res

async def gen_drop_txt(drops):
    """獎勵"""
    res = []
    for iid, q in drops.items():
        info = get_i_info(iid)
        if info: res.append(f"{info['name']}:{q}")
    return ", ".join(res)

async def setup(bot: commands.Bot):
    await bot.add_cog(Fight(bot))
    print('>> 戰鬥系統 <<')
