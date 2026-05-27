import discord
import json
from discord.ext import commands
from discord.ui import Select, View
from discord import Embed, SelectOption
import random
from .database import *
from .skill_system import SkillSystem

class NotAdmin(Exception):
    pass

# 讀設定
with open('admin_ids.json', 'r', encoding='utf-8') as f:
    admins = json.load(f)


class Main(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def ping(self, ctx: commands.Context):
        """看延遲"""
        await ctx.send(f"延遲：{round(self.bot.latency*1000)}ms")



    @commands.command()
    async def register(self, ctx):
        """註冊"""
        uid = str(ctx.author.id)
        p = await get_p_data(uid)
        if p is None:
            # 沒資料
            d = {
                'id': uid, 'level': 1, 'exp': 0, 'money': 100, 'items': '{}',
                'rank': '普通玩家', 'hp': 100, 'maxhp': 100, 'mp': 50, 'maxmp': 50,
                'atk': 15, 'defense': 10
            }
            await create_p(d)
            await create_p_sk({'id': uid, 'skills': '[]', 'equipped_skills': '[]'})
            await ctx.send('註冊成功囉。')
        else:
            await ctx.send('你已經是這裡的一員啦，不用再註冊。')

    @commands.command()
    async def me(self, ctx):
        """個人資料"""
        uid = str(ctx.author.id)
        p = await get_p_data(uid)
        sk = await get_p_skills(uid)

        if p is None:
            await ctx.send("查不到你的資料，先註冊吧！")
            return

        e_m = discord.utils.get(self.bot.emojis, name='money')
        e_i = discord.utils.get(self.bot.emojis, name='92')
        e_j = discord.utils.get(self.bot.emojis, name='juju')

        async def update_emb(interaction, mode):
            if interaction.user != ctx.author: return
            
            emb = Embed(title=f":sunny: | {ctx.author.name} 的資料卡", color=0x1f4239)
            emb.set_thumbnail(url=ctx.author.avatar.url)

            if mode == 'item':
                items = p['items']
                res = ""
                for iid, q in items.items():
                    info = get_i_info(iid)
                    if info: res += f"{info['name']}: `{q}`\n"
                emb.add_field(name="背包物品", value=res or "空空如也", inline=False)
            elif mode == 'money':
                emb.add_field(name="錢包", value=f"{p['money']} {e_m or '金幣'}", inline=True)
            elif mode == 'skill':
                eq = sk['equipped_skills']
                res = "\n".join([f"`{s}`" for s in eq]) if eq else "沒裝任何技能"
                emb.add_field(name="目前裝備技能", value=res, inline=False)
                emb.add_field(name="小撇步", value="想換技能？用 `=skill` 看看吧", inline=False)
            else:
                emb.add_field(name="稱號", value=p['rank'], inline=False)
                emb.add_field(name="等級", value=f"LV.{p['level']}", inline=True)
                emb.add_field(name="經驗值", value=f"({p['exp']} / {(100 + (p['level'] - 1) * 20)})", inline=True)
                emb.add_field(name="狀態", value=f"HP: {p['maxhp']} | ATK: {p['atk']} | DEF: {p['defense']}", inline=False)

            # 重新加選單
            sel = Select(placeholder="想看什麼呢？", options=[
                SelectOption(label="錢包", value="money", emoji=e_m, description="看我多有錢"),
                SelectOption(label="背包", value="item", emoji=e_i, description="看我有什麼寶貝"),
                SelectOption(label="技能", value="skill", emoji=e_j, description="看我的絕招"),
                SelectOption(label="首頁", value="me", emoji=e_j, description="回主畫面")
            ])
            async def cb(it): await update_emb(it, it.data['values'][0])
            sel.callback = cb
            v = View(); v.add_item(sel)
            await interaction.response.edit_message(embed=emb, view=v)

        # 初始 Embed
        emb = Embed(title=f":sunny: | {ctx.author.name} 的資料卡", color=0x1f4239)
        emb.set_thumbnail(url=ctx.author.avatar.url)
        emb.add_field(name="稱號", value=p['rank'], inline=False)
        emb.add_field(name="等級", value=f"LV.{p['level']}", inline=True)
        emb.add_field(name="經驗值", value=f"({p['exp']} / {(100 + (p['level'] - 1) * 20)})", inline=True)
        emb.add_field(name="狀態", value=f"HP: {p['maxhp']} | ATK: {p['atk']} | DEF: {p['defense']}", inline=False)

        sel = Select(placeholder="想看什麼呢？", options=[
            SelectOption(label="錢包", value="money", emoji=e_m, description="看我多有錢"),
            SelectOption(label="背包", value="item", emoji=e_i, description="看我有什麼寶貝"),
            SelectOption(label="技能", value="skill", emoji=e_j, description="看我的絕招"),
            SelectOption(label="首頁", value="me", emoji=e_j, description="回主畫面")
        ])
        async def cb(it): await update_emb(it, it.data['values'][0])
        sel.callback = cb
        v = View(); v.add_item(sel)
        await ctx.send(embed=emb, view=v)

    @commands.command()
    async def say(self, ctx, *, msg):
        """代說"""
        await ctx.message.delete()
        await ctx.send(msg)

    @commands.command()
    async def room(self, ctx):
        """開討論串房間"""
        try:
            t = await ctx.message.create_thread(name=f"{ctx.author.name}的房間", auto_archive_duration=60)
            await t.send(f"歡迎來到 {ctx.author.mention} 的祕密基地！這裡在 #{ctx.channel.name} 之下。")
        except Exception as e:
            await ctx.send(f"開不了房間...：{e}")

    @commands.command()
    async def info(self, ctx, *, i_n: str = None):
        """查物品資訊"""
        if not i_n:
            await ctx.send("你要查什麼？例如：`=info 香菸`")
            return
        
        info = get_i_info_by_n(i_n)
        if info:
            emb = Embed(title=f"【{info['name']}】", color=0x3498db)
            emb.add_field(name="編號", value=info['id'], inline=True)
            emb.add_field(name="分類", value=info['category'], inline=True)
            emb.add_field(name="介紹", value=info.get('description', '沒寫介紹'), inline=False)
            emb.add_field(name="性質", value=f"{'可交易' if info.get('tradable') else '不可交易'}, {'可堆疊' if info.get('stackable') else '不可堆疊'}", inline=True)
            emb.add_field(name="收購價", value=f"{info.get('sell_price', '未知')} 金幣", inline=True)
            await ctx.send(embed=emb)
        else:
            await ctx.send(f"找不到這個東西：{i_n}")

    @commands.command()
    async def admin_give(self, ctx, target: discord.Member, iid: str, q: int = 1):
        """送東西"""
        try:
            await self.check_admin(ctx)
            info = get_i_info(iid)
            if info:
                await give_items(str(target.id), {iid: q})
                await ctx.send(f"管理員已發放 {info['name']} x{q} 給 {target.mention}")
            else:
                await ctx.send(f"找不到 ID: {iid} 的物品")
        except NotAdmin: pass

    async def check_admin(self, ctx):
        """權限檢查"""
        if str(ctx.author.id) not in admins:
            await ctx.send("阿勒?(´･ ･｀｡) ")
            raise NotAdmin()

    @commands.command()
    async def exp(self, ctx, target: discord.Member, amt: int):
        """發經驗"""
        try:
            await self.check_admin(ctx)
            res, err = await add_exp(str(target.id), amt)
            if err:
                await ctx.send(err)
            else:
                lv_msg = "\n".join(res['level_up_messages'])
                await ctx.send(f"{target.mention} 拿到 {amt} 點經驗！\n目前 LV.{res['new_level']} ({res['new_exp']})\n{lv_msg}")
        except NotAdmin: pass
    
    @commands.command()
    async def r(self, ctx, *opts):
        """隨機選一個"""
        if not opts:
            await ctx.send("給個選項讓我挑吧！")
            return
        sel = random.choice(opts)
        await ctx.send(embed=Embed(title="鳩鳩幫你選", description=f"就決定是：**{sel}** 啦！", color=0x1f4239))

async def setup(bot: commands.Bot):
    await bot.add_cog(Main(bot))
    print('>> 核心系統啟動成功 <<')
