import discord
from discord.ext import commands
from discord import app_commands
from .database import *
import json
import logging
from discord.ui import Button, View
from datetime import datetime, timedelta
from discord.ext import tasks
import uuid

# 設置日誌
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('economy')

def check_qty(q):
    """檢查數量是不是正整數"""
    return isinstance(q, int) and q > 0

class HistoryPaginator(discord.ui.View):
    """交易紀錄器"""
    def __init__(self, pages):
        super().__init__(timeout=60)
        self.pages = pages
        self.cur = 0

    @discord.ui.button(label="首頁", style=discord.ButtonStyle.gray)
    async def first(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if self.cur != 0:
            self.cur = 0
            await self.update_msg(interaction)

    @discord.ui.button(label="上一頁", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if self.cur > 0:
            self.cur -= 1
            await self.update_msg(interaction)

    @discord.ui.button(label="下一頁", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if self.cur < len(self.pages) - 1:
            self.cur += 1
            await self.update_msg(interaction)

    @discord.ui.button(label="末頁", style=discord.ButtonStyle.gray)
    async def last(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if self.cur != len(self.pages) - 1:
            self.cur = len(self.pages) - 1
            await self.update_msg(interaction)

    async def update_msg(self, interaction: discord.Interaction):
        emb = self.pages[self.cur]
        emb.set_footer(text=f"第 {self.cur + 1} 頁，共 {len(self.pages)} 頁")
        
        # 點亮或關閉按鈕
        self.first.disabled = (self.cur == 0)
        self.prev.disabled = (self.cur == 0)
        self.next.disabled = (self.cur == len(self.pages) - 1)
        self.last.disabled = (self.cur == len(self.pages) - 1)

        await interaction.response.edit_message(embed=emb, view=self)

class GiveModal(discord.ui.Modal, title='送東西或金幣'):
    """右鍵選單彈出的視窗"""
    i_n = discord.ui.TextInput(label='物品名稱（空著代表給錢）', required=False)
    qty = discord.ui.TextInput(label='數量', required=True)

    def __init__(self, item_cb, money_cb, target):
        super().__init__()
        self.item_cb = item_cb
        self.money_cb = money_cb
        self.target = target

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n = self.i_n.value.strip()
            try:
                q = int(self.qty.value)
            except ValueError:
                await interaction.response.send_message("數量請填數字", ephemeral=True)
                return

            if not check_qty(q):
                await interaction.response.send_message("數量要是正的喔", ephemeral=True)
                return

            if n:
                await self.item_cb(interaction, self.target, n, q)
            else:
                await self.money_cb(interaction, self.target, q)
        except Exception as e:
            log.error(f"GiveModal error: {e}")
            await interaction.response.send_message("出錯", ephemeral=True)

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.trades = {} # 交易請求
        self.check_trades.start()

    def cog_unload(self):
        self.check_trades.cancel()

    @tasks.loop(minutes=1.0)
    async def check_trades(self):
        """定時檢查有沒有人交易等到過期"""
        try:
            now = datetime.now()
            expired = []

            for sid, b_trades in list(self.trades.items()):
                for bid, info in list(b_trades.items()):
                    t_time = datetime.fromisoformat(info['timestamp'])
                    if now - t_time > timedelta(minutes=5):
                        expired.append((sid, bid))

            for sid, bid in expired:
                await self.cancel_td(sid, bid)
        except Exception as e:
            log.error(f"Check expired trades error: {e}")

    @check_trades.before_loop
    async def wait_ready(self):
        await self.bot.wait_until_ready()

    async def cancel_td(self, sid, bid):
        """取消交易"""
        if sid in self.trades and bid in self.trades[sid]:
            info = self.trades[sid][bid]
            del self.trades[sid][bid]
            if not self.trades[sid]: del self.trades[sid]

            s = self.bot.get_user(int(sid))
            b = self.bot.get_user(int(bid))
            msg = f"交易過期了：{info['qty']} 個 {info['item_name']}，價格 {info['price']} 金幣"

            if s:
                try: await s.send(f"你與 {b.name if b else '某人'} 的{msg}")
                except: pass
            if b:
                try: await b.send(f"你與 {s.name if s else '某人'} 的{msg}")
                except: pass

            log.info(f"交易已取消：{sid} -> {bid}")

    @app_commands.command(name="cleartd", description="把沒完成的交易請求全砍了")
    async def cleartd(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if uid in self.trades:
            cnt = len(self.trades[uid])
            del self.trades[uid]
            await interaction.response.send_message(f"幫你砍了 {cnt} 個沒人理的交易。", ephemeral=True)
        else:
            await interaction.response.send_message("你本來就沒發起什麼交易啊。", ephemeral=True)

    async def give_item(self, interaction: discord.Interaction, target: discord.Member, i_n: str, qty: int):
        """單方面送東西"""
        try:
            sid = str(interaction.user.id)
            tid = str(target.id)

            s_data = await get_p_data(sid)
            t_data = await get_p_data(tid)

            if not s_data or not t_data:
                await interaction.response.send_message("你們其中一人還沒創角色吧", ephemeral=True)
                return

            iid = get_i_id_by_n(i_n)
            if not iid:
                await interaction.response.send_message(f"找不到『{i_n}』這東西", ephemeral=True)
                return

            bag = s_data['items']
            if iid not in bag or bag[iid] < qty:
                await interaction.response.send_message("你身上的數量不夠喔", ephemeral=True)
                return

            # 扣你的加對方的
            bag[iid] -= qty
            if bag[iid] == 0: del bag[iid]

            t_bag = t_data['items']
            t_bag[iid] = t_bag.get(iid, 0) + qty

            await set_p_data(sid, items=bag)
            await set_p_data(tid, items=t_bag)

            info = get_i_info(iid)
            await interaction.response.send_message(f"已送給 {target.mention} {qty} 個 {info['name'] if info else iid}", ephemeral=True)
        except Exception as e:
            log.error(f"Give item error: {e}")
            await interaction.response.send_message("送東西失敗，晚點試試", ephemeral=True)

    async def history(self, interaction: discord.Interaction):
        """查交易史"""
        await interaction.response.defer(ephemeral=True, thinking=True)
        await interaction.followup.send("翻翻本子喔...等一下下", ephemeral=True)
        
        pid = str(interaction.user.id)
        logs = await get_p_t_log(pid, limit=30)

        if not logs:
            await interaction.edit_original_response(content="你這本是空白的，還沒做過生意喔。")
            return

        pages = []
        for i in range(0, len(logs), 10):
            emb = discord.Embed(title="交易紀錄本", color=discord.Color.blue())
            for t in logs[i:i+10]:
                _, _, t_type, i_n, q, pr, o_id, ts = t
                if t_type == "購買" and str(o_id) == pid: continue
                
                other = await self.bot.fetch_user(int(o_id))
                t_dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                f_time = t_dt.strftime("%Y-%m-%d %H:%M:%S")
                emb.add_field(
                    name=f"{t_type} - {f_time}",
                    value=f"物品: {i_n}\n數量: {q}\n價格: {pr}\n對方: {other.name}",
                    inline=False
                )
            pages.append(emb)

        await interaction.edit_original_response(content=None, embed=pages[0], view=HistoryPaginator(pages))
        
    async def give_money(self, interaction: discord.Interaction, target: discord.Member, amt: int):
        """送錢"""
        sid, tid = str(interaction.user.id), str(target.id)
        s_d = await get_p_data(sid)
        t_d = await get_p_data(tid)

        if not s_d or not t_d:
            await interaction.response.send_message("角色資料有問題", ephemeral=True)
            return

        if s_d['money'] < amt:
            await interaction.response.send_message("你錢不夠啦", ephemeral=True)
            return

        await set_p_data(sid, money=s_d['money'] - amt)
        await set_p_data(tid, money=t_d['money'] + amt)
        await interaction.response.send_message(f"已塞了 {amt} 金幣給 {target.mention}", ephemeral=True)

    @app_commands.command(name="give", description="送東西或金幣給別人")
    async def give(self, interaction: discord.Interaction, target: discord.Member, item: str = "", qty: int = 0):
        if item: await self.give_item(interaction, target, item, qty)
        else: await self.give_money(interaction, target, qty)

    @app_commands.command(name="trade", description="跟人買賣東西")
    async def trade(self, interaction: discord.Interaction, target: discord.Member, item: str, qty: int, pr: int):
        sid, bid = str(interaction.user.id), str(target.id)

        if sid == bid:
            await interaction.response.send_message("別跟自己做生意啦，很奇怪。", ephemeral=True)
            return

        if qty <= 0 or pr < 0:
            await interaction.response.send_message("數量或價格填錯了吧？", ephemeral=True)
            return

        if sid in self.trades and len(self.trades[sid]) >= 3:
            await interaction.response.send_message("你手上太多交易在等了，先清一下。", ephemeral=True)
            return

        s_d = await get_p_data(sid)
        if not s_d:
            await interaction.response.send_message("你還沒創角色吧？", ephemeral=True)
            return

        iid = get_i_id_by_n(item)
        if not iid:
            await interaction.response.send_message(f"那是啥？找不到『{item}』。", ephemeral=True)
            return

        bag = s_d['items']
        if iid not in bag or bag[iid] < qty:
            await interaction.response.send_message("你東西不夠賣人家啦。", ephemeral=True)
            return

        tid = str(uuid.uuid4())
        info = {
            "iid": iid, "item_name": item, "qty": qty, "price": pr,
            "tid": tid, "timestamp": datetime.now().isoformat()
        }

        if sid not in self.trades: self.trades[sid] = {}
        self.trades[sid][bid] = info

        class ConfirmView(discord.ui.View):
            def __init__(self, cog, sid, bid, tid):
                super().__init__(timeout=300)
                self.cog, self.sid, self.bid, self.tid = cog, sid, bid, tid

            @discord.ui.button(label="簽字成交", style=discord.ButtonStyle.green)
            async def ok(self, interaction: discord.Interaction, btn: discord.ui.Button):
                if interaction.user.id != int(self.bid):
                    await interaction.response.send_message("這不是給你的合約。", ephemeral=True)
                    return

                info = self.cog.trades.get(self.sid, {}).get(self.bid)
                if not info or info['tid'] != self.tid:
                    await interaction.response.send_message("合約已經失效了。", ephemeral=True)
                    return

                try:
                    s_d = await get_p_data(self.sid)
                    b_d = await get_p_data(self.bid)

                    if info['iid'] not in s_d['items'] or s_d['items'][info['iid']] < info['qty']:
                        await interaction.response.send_message("賣家東西好像突然不見了，成交失敗。", ephemeral=True)
                        self.stop()
                        return

                    if b_d['money'] < info['price']:
                        await interaction.response.send_message("你口袋錢不夠，沒法買。", ephemeral=True)
                        self.stop()
                        return

                    # 扣雙方換東西
                    s_bag = s_d['items']
                    s_bag[info['iid']] -= info['qty']
                    if s_bag[info['iid']] == 0: del s_bag[info['iid']]
                    
                    b_bag = b_d['items']
                    b_bag[info['iid']] = b_bag.get(info['iid'], 0) + info['qty']

                    await set_p_data(self.sid, items=s_bag, money=s_d['money'] + info['price'])
                    await set_p_data(self.bid, items=b_bag, money=b_d['money'] - info['price'])

                    await add_t_log(self.sid, "賣出", info['item_name'], info['qty'], info['price'], self.bid)
                    await add_t_log(self.bid, "購買", info['item_name'], info['qty'], info['price'], self.sid)

                    del self.cog.trades[self.sid][self.bid]
                    if not self.cog.trades[self.sid]: del self.cog.trades[self.sid]

                    for c in self.children: c.disabled = True
                    emb = discord.Embed(title="交易成功！", description=f"<@{self.bid}> 買到了 {info['qty']} 個 {info['item_name']}！", color=discord.Color.green())
                    await interaction.response.edit_message(embed=emb, view=self)
                    self.stop()
                except Exception as e:
                    log.error(f"Trade confirm error: {e}")
                    await interaction.response.send_message("交易出事", ephemeral=True)

            @discord.ui.button(label="撕毀合約", style=discord.ButtonStyle.red)
            async def no(self, interaction: discord.Interaction, btn: discord.ui.Button):
                if interaction.user.id != int(self.sid) and interaction.user.id != int(self.bid):
                    await interaction.response.send_message("不關你的事別亂動。", ephemeral=True)
                    return

                if self.sid in self.cog.trades and self.bid in self.cog.trades[self.sid]:
                    del self.cog.trades[self.sid][self.bid]
                    if not self.cog.trades[self.sid]: del self.cog.trades[self.sid]

                for c in self.children: c.disabled = True
                await interaction.response.edit_message(content="交易作廢。", embed=None, view=self)
                self.stop()

        emb = discord.Embed(title="交易請求", description=f"<@{bid}>，有人想跟你做生意！", color=discord.Color.blue())
        emb.add_field(name="賣家", value=f"<@{sid}>", inline=True)
        emb.add_field(name="物品", value=item, inline=True)
        emb.add_field(name="數量", value=str(qty), inline=True)
        emb.add_field(name="價格", value=f"{pr} 金幣", inline=True)
        emb.set_footer(text="考慮時間：5分鐘")

        await interaction.response.send_message(embed=emb, view=ConfirmView(self, sid, bid, tid))

@app_commands.context_menu(name="塞東西給他")
async def give_cm(interaction: discord.Interaction, member: discord.Member):
    cog = interaction.client.get_cog('Economy')
    if cog: await interaction.response.send_modal(GiveModal(cog.give_item, cog.give_money, member))

@app_commands.context_menu(name="看他的交易帳本")
async def history_cm(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != member.id:
        await interaction.response.send_message("別亂翻別人的帳本啦。", ephemeral=True)
        return
    cog = interaction.client.get_cog('Economy')
    if cog: await cog.history(interaction)

async def setup(bot):
    await bot.add_cog(Economy(bot))
    bot.tree.add_command(give_cm)
    bot.tree.add_command(history_cm)
    print(">> 經濟系統 <<")
