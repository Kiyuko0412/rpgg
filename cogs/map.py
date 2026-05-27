import discord
from discord import PartialEmoji 
from discord.ext import commands
from discord.ui import Button, View, Select
import random
import json
import copy
from .fight import Fight
from .database import (
    get_p_data, set_p_data, 
    log_map_in, get_today_map_cnt, 
    get_i_id_by_n, ITEMS, 
    save_map_progress, load_map_progress, del_map_progress,
    add_exp, give_items
)

class MapBtn(Button):
    """地圖移動按鈕基底"""
    def __init__(self, uid, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uid = uid

    async def callback(self, it: discord.Interaction):
        m_cog = it.client.get_cog('Map')
        if not m_cog: return

        if it.user.id != self.uid:
            await it.response.send_message("這不是你的地圖啦。", ephemeral=True)
            return

        p = m_cog.players.get(self.uid)
        if not p:
            await it.response.send_message("地圖過期了，請重新輸入 `/map`。", ephemeral=True)
            return
        
        if p.get('in_combat'):
            await it.response.send_message("戰鬥中不能亂跑喔！", ephemeral=True)
            return

        await self.act(it, m_cog)

    async def act(self, it, cog): pass

class MoveBtn(MapBtn):
    def __init__(self, uid, label, dx, dy):
        super().__init__(uid, label=label, style=discord.ButtonStyle.primary)
        self.dx, self.dy = dx, dy

    async def act(self, it, cog):
        await cog.btn_cb(it, self.dx, self.dy, self.uid)

class SpdBtn(MapBtn):
    def __init__(self, uid):
        super().__init__(uid, label="切換跑速", style=discord.ButtonStyle.secondary)

    async def act(self, it, cog):
        p = cog.players[self.uid]
        p['speed'] = 2 if p['speed'] == 1 else 1
        await cog.refresh_msg(it, self.uid)

class Map(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {} # 存玩家當前地圖狀態
        self.tips = "" 

        # 讀資料
        try:
            with open('cogs/maps_data.json', 'r', encoding='utf-8') as f:
                self.m_data = json.load(f)
        except:
            print("找不到 maps_data.json")
            self.m_data = {}

        # 預設表情符號
        self.emoji_me = "😐" 
        self.emoji_wall = "🧱" 
        self.emoji_ju = "⬛" 
        
        self.emoji_treasure = "💎"

        self.emoji_forest_exit = "🌲"
        self.emoji_wall_cave = "🪨" 
        self.emoji_monster_cave = "👾"
        self.emoji_treasure_cave = "💰"
        self.emoji_ju_cave = "👣" 
        self.emoji_cave_exit = "↪️"
        self.emoji_reward_exit = "🏆" 
        self.emoji_volcano_boss = "👹" 

        self.emoji_yeah = "🎉"
        self.emoji_digua = "🍠"
        self.emoji_na = "🚫"

    def load_p_map(self, uid, mid, start, saved=None, fresh=False):
        """載入地圖環境"""
        if mid not in self.m_data:
            mid = 'map1_forest' 
            if mid not in self.m_data: return False
            start = self.m_data[mid].get('start_pos', [1,1])

        grid = [list(r) for r in self.m_data[mid]['layout']]

        if uid not in self.players:
            self.players[uid] = {
                'mid': mid, 'pos': list(start), 'grid': grid, 'speed': 1,
                'rewards': {'money': 0, 'items': {}},
                'state': {'collected': [], 'killed': []},
                'in_combat': False
            }
        else:
            p = self.players[uid]
            p['mid'], p['pos'], p['grid'] = mid, list(start), grid
            if fresh:
                p['rewards'] = {'money': 0, 'items': {}}
                p['in_combat'] = False 
            if not saved:
                p['state'] = {'collected': [], 'killed': []}
        
        p = self.players[uid]
        # 把之前的狀態蓋上去 (開過的寶箱、打過的怪)
        if saved:
            p['state'] = saved
            empty = self.get_empty(mid)
            for r, c in saved.get('collected', []):
                if 0 <= r < len(grid) and 0 <= c < len(grid[0]): grid[r][c] = empty
            for r, c in saved.get('killed', []):
                if 0 <= r < len(grid) and 0 <= c < len(grid[0]): grid[r][c] = empty
        
        # 標記玩家 P
        for r_idx, row in enumerate(grid):
            for c_idx, cell in enumerate(row):
                if cell == 'P': grid[r_idx][c_idx] = self.get_empty(mid)
        
        if 0 <= start[0] < len(grid) and 0 <= start[1] < len(grid[0]):
            grid[start[0]][start[1]] = 'P'
        else:
            grid[0][0] = 'P'
            p['pos'] = [0,0]
        return True

    def get_empty(self, mid):
        return '.' if mid in self.m_data and '.' in self.m_data[mid]['legend'] else " "

    def draw_map(self, uid):
        """渲染地圖字串"""
        p = self.players.get(uid)
        if not p: return "地圖迷路中..."

        mid = p['mid']
        grid = p['grid']
        legend = self.m_data[mid]['legend']

        res = []
        for r in grid:
            row = []
            for cell in r:
                e_n = legend.get(str(cell))
                row.append(str(getattr(self, e_n, cell) if e_n else cell))
            res.append("".join(row))
        return "\n".join(res)

    async def move(self, uid, dx, dy, it):
        """處理移動與碰撞"""
        p = self.players.get(uid)
        if not p: return

        mid, grid, pos, speed = p['mid'], p['grid'], p['pos'], p['speed']
        conf = self.m_data.get(mid)
        if not conf: return

        walls = [k for k, v in conf['legend'].items() if "wall" in v]
        nx, ny = pos[0], pos[1]

        for _ in range(speed):
            px, py = nx + dx, ny + dy
            if not (0 <= px < len(grid) and 0 <= py < len(grid[0])):
                self.tips = "到邊界了，過不去喔。"
                break
            
            tile = grid[px][py]
            if tile in walls:
                self.tips = "噢！撞到牆了..."
                break

            nx, ny = px, py

            # 一般傳送門
            if tile in conf.get('exits', {}):
                ex = conf['exits'][tile]
                t_mid, t_pos = ex['target_map_id'], list(ex['target_pos'])
                
                if conf.get('dungeon_id') and self.m_data.get(t_mid, {}).get('dungeon_id') != conf['dungeon_id']:
                    m, i = p['rewards']['money'], sum(p['rewards']['items'].values())
                    if m > 0 or i > 0:
                        self.tips = f"中途離開了區域，噴掉了 {m} 金幣跟 {i} 件寶物..."
                        p['rewards'] = {'money': 0, 'items': {}}
                
                if self.load_p_map(uid, t_mid, t_pos):
                    await set_p_data(str(uid), current_map_id=t_mid, current_map_x=t_pos[0], current_map_y=t_pos[1])
                    self.tips = f"進入了 {self.m_data[t_mid]['name']}"
                return 

            # 結算終點
            for rx in conf.get('reward_exits', []):
                if tile == rx['char']:
                    sid = str(uid)
                    fix_r = rx.get('rewards', {})
                    ses_r = p['rewards']
                    
                    total_m = fix_r.get('money', 0) + ses_r.get('money', 0)
                    to_add = {}
                    for k, v in fix_r.get('items', {}).items():
                        iid = get_i_id_by_n(str(k))
                        if iid: to_add[iid] = to_add.get(iid, 0) + v
                    for k, v in ses_r.get('items', {}).items():
                        iid = get_i_id_by_n(k)
                        if iid: to_add[iid] = to_add.get(iid, 0) + v
                            
                    res_txt = ["**結算清單：**"]
                    if total_m > 0:
                        cur_m = (await get_p_data(sid))['money']
                        await set_p_data(sid, money=cur_m + total_m)
                        res_txt.append(f"💰 金幣: +{total_m}")

                    exp = fix_r.get('exp', 0)
                    if exp > 0:
                        res, err = await add_exp(sid, exp)
                        if not err:
                            res_txt.append(f"✨ 經驗: +{exp}")
                            if res['level_up_messages']: res_txt.extend(res['level_up_messages'])

                    if to_add:
                        await give_items(sid, to_add)
                        ilist = [f"{ITEMS.get(i, {'name':i})['name']} x{q}" for i, q in to_add.items()]
                        res_txt.append(f"📦 物品: {', '.join(ilist)}")

                    await del_map_progress(sid, mid)
                    emb = discord.Embed(title=f"🚩 {conf.get('name')} 攻略完成！", description=rx.get('message', "辛苦了！") + "\n" + "\n".join(res_txt), color=0x2ecc71)
                    await it.response.edit_message(content=None, embed=emb, view=None)
                    if uid in self.players: del self.players[uid]
                    return "DONE"

            # 遇怪
            ekey = conf['legend'].get(str(tile))
            if ekey and ("monster" in ekey or "boss" in ekey):
                f_cog = self.bot.get_cog('Fight')
                if f_cog:
                    mn = None
                    mlist = conf.get('monsters', [])
                    if mlist:
                        if tile == 'B': mn = mlist[0].get('name')
                        else:
                            val = [m for m in mlist if m.get('name')]
                            if val: mn = random.choice(val).get('name')

                    empty = self.get_empty(mid)
                    grid[pos[0]][pos[1]] = empty
                    p['pos'] = [nx, ny]
                    grid[nx][ny] = 'P'
                    await set_p_data(str(uid), current_map_x=nx, current_map_y=ny)
                    
                    p['in_combat'] = True 
                    await f_cog.mapfight(it.user, it.channel, mid, conf['tier'], mn)

                    # 標記怪被打死
                    mrc = [nx, ny]
                    grid[nx][ny] = empty 
                    if mrc not in p['state']['killed']:
                        p['state']['killed'].append(mrc)
                        await save_map_progress(str(uid), mid, json.dumps(p['state']))
                    grid[nx][ny] = 'P'
                    return 

            # 撿寶
            tkey = next((k for k, v in conf['legend'].items() if "treasure" in v), None)
            if tkey and tile == tkey:
                trc = [px, py]
                if trc not in p['state']['collected']:
                    p['state']['collected'].append(trc)
                    await save_map_progress(str(uid), mid, json.dumps(p['state']))

                    tr = conf.get('treasure_rewards')
                    if tr:
                        p['rewards']['money'] += tr.get('money', 0)
                        for k, v in tr.get('items', {}).items():
                            p['rewards']['items'][k] = p['rewards']['items'].get(k, 0) + v
                        self.tips = "撿到了寶箱！"
                else: self.tips = "這箱子是空的。"
                grid[px][py] = self.get_empty(mid)

        # 更新玩家位置
        if nx != pos[0] or ny != pos[1]:
            empty = self.get_empty(mid)
            grid[pos[0]][pos[1]] = empty
            p['pos'] = [nx, ny]
            grid[nx][ny] = 'P'
            await set_p_data(str(uid), current_map_x=nx, current_map_y=ny)
            if not self.tips: self.tips = "前進成功。"

    async def btn_cb(self, it, dx, dy, uid):
        res = await self.move(uid, dx, dy, it)
        if res == "DONE": return
        if uid in self.players: await self.refresh_msg(it, uid)

    async def refresh_msg(self, it, uid):
        p = self.players.get(uid)
        if not p: return

        mid = p['mid']
        name = self.m_data.get(mid, {}).get('name', "未知地帶")
        emb = discord.Embed(title=name, description=self.draw_map(uid), color=0x4b9eaf)

        spd = "快" if p.get('speed') == 2 else "慢"
        money = p['rewards']['money']
        footer = f"本局收集金幣: {money} | 跑速: {spd}"
        if self.tips: footer += f"\n提示: {self.tips}"
        emb.set_footer(text=footer)
        self.tips = "" 

        await it.response.edit_message(embed=emb, view=self.gen_view(uid))

    def gen_view(self, uid):
        v = View(timeout=None)
        v.add_item(MoveBtn(uid, "上", -1, 0))
        v.add_item(MoveBtn(uid, "下", 1, 0))
        v.add_item(MoveBtn(uid, "左", 0, -1))
        v.add_item(MoveBtn(uid, "右", 0, 1))
        v.add_item(SpdBtn(uid))
        return v
    
    @commands.command(name="oldmap") 
    async def oldmap(self, ctx):
        """回上一張地圖"""
        uid = ctx.author.id
        db = await get_p_data(str(uid))
        mid, pos = 'map1_forest', [1,1]

        if db:
            if db.get('current_map_id') in self.m_data:
                mid = db['current_map_id']
                pos = [db.get('current_map_x', 1), db.get('current_map_y', 1)]

        saved_s = await load_map_progress(str(uid), mid)
        if self.load_p_map(uid, mid, pos, saved=json.loads(saved_s) if saved_s else None, fresh=True):
            p = self.players[uid]
            emb = discord.Embed(title=self.m_data[p['mid']]['name'], description=self.draw_map(uid), color=0x4b9eaf)
            await ctx.send(embed=emb, view=self.gen_view(uid))

    @commands.Cog.listener()
    async def on_ready(self):
        # 自定義 Emoji
        self.emoji_yeah = discord.utils.get(self.bot.emojis, name='yeah') or self.emoji_yeah
        self.emoji_me = discord.utils.get(self.bot.emojis, name='pixelju2') or self.emoji_me
        self.emoji_wall = discord.utils.get(self.bot.emojis, name='graywall') or self.emoji_wall
        self.emoji_ju = discord.utils.get(self.bot.emojis, name='jujuwithcope') or self.emoji_ju
        self.emoji_na = discord.utils.get(self.bot.emojis, name='na') or self.emoji_na
        self.emoji_digua = discord.utils.get(self.bot.emojis, name='digua') or self.emoji_digua
        self.emoji_wood_f = discord.utils.get(self.bot.emojis, name='wood_f')
        self.emoji_cave_entrance = discord.utils.get(self.bot.emojis, name='portal')
        self.emoji_treasure = discord.utils.get(self.bot.emojis, name='treasure')
        self.emoji_monster = discord.utils.get(self.bot.emojis, name='monster')
        self.emoji_forest_exit = discord.utils.get(self.bot.emojis, name='emoji_forest_exit') or self.emoji_forest_exit
        self.emoji_reward_exit = discord.utils.get(self.bot.emojis, name='emoji_reward_exit') or self.emoji_reward_exit
        self.emoji_volcano_boss = discord.utils.get(self.bot.emojis, name='emoji_volcano_boss') or self.emoji_volcano_boss

    @commands.hybrid_command(name="map", description="開啟地圖選單")
    async def map_cmd(self, ctx):
        v = MapSelView(ctx.author.id, self)
        msg = await ctx.send("要出發去哪裡？", view=v)
        v.msg = msg

class MapSelView(View):
    def __init__(self, aid, cog):
        super().__init__(timeout=180)
        self.aid, self.cog, self.msg = aid, cog, None
        self.add_item(WorldSel(self.cog.m_data, self.aid))

    async def interaction_check(self, it: discord.Interaction) -> bool:
        if it.user.id != self.aid:
            await it.response.send_message("別亂點別人的選單啦。", ephemeral=True)
            return False
        return True

class WorldSel(Select):
    def __init__(self, data, aid):
        self.data, self.aid = data, aid
        ws = sorted(list(set(d.get('world', '其他') for d in data.values())))
        opts = [discord.SelectOption(label=w) for w in ws]
        super().__init__(placeholder="挑一個世界...", options=opts)

    async def callback(self, it: discord.Interaction):
        sel = self.values[0]
        v = self.view
        v.clear_items()
        
        m_in_w = {mid: d for mid, d in self.data.items() if d.get('world') == sel}
        areas = sorted(list(set(d.get('area') for d in m_in_w.values() if d.get('area'))))

        if len(areas) > 1:
            v.add_item(AreaSel(m_in_w, sel, self.aid))
            txt = f"已選擇世界：**{sel}**，請挑區域："
        else:
            v.add_item(MapDetailSel(m_in_w, self.aid))
            txt = f"已選擇世界：**{sel}**，請挑地圖："
        
        v.add_item(BackBtn(self.aid))
        await it.response.edit_message(content=txt, view=v)

class AreaSel(Select):
    def __init__(self, m_in_w, w_n, aid):
        self.m_in_w, self.aid = m_in_w, aid
        areas = sorted(list(set(d.get('area', '未知') for d in m_in_w.values())))
        opts = [discord.SelectOption(label=a) for a in areas]
        super().__init__(placeholder="挑一個區域...", options=opts)

    async def callback(self, it: discord.Interaction):
        sel = self.values[0]
        v = self.view
        v.clear_items()
        m_in_a = {mid: d for mid, d in self.m_in_w.items() if d.get('area') == sel}
        v.add_item(MapDetailSel(m_in_a, self.aid))
        v.add_item(BackBtn(self.aid))
        await it.response.edit_message(content=f"區域：**{sel}**，請挑地圖：", view=v)

class MapDetailSel(Select):
    def __init__(self, maps, aid):
        self.maps, self.aid = maps, aid
        opts = []
        for mid, d in maps.items():
            if d.get('hidden_in_menu'): continue
            lbl = d.get('name', mid)
            dsc = []
            if d.get('entry_cost_money'): dsc.append(f"${d['entry_cost_money']}")
            if d.get('daily_limit'): dsc.append(f"限{d['daily_limit']}次")
            opts.append(discord.SelectOption(label=lbl, value=mid, description=" | ".join(dsc) or "自由進入"))
        
        super().__init__(placeholder="挑一張地圖...", options=opts or [discord.SelectOption(label="沒地圖", value="NONE")])

    async def callback(self, it: discord.Interaction):
        mid = self.values[0]
        if mid == "NONE": return

        cog = self.view.cog
        d = self.maps.get(mid)
        sid = str(it.user.id)
        db = await get_p_data(sid)
        if not db: return

        # 門檻檢查
        lim = d.get('daily_limit')
        if lim and (await get_today_map_cnt(sid, mid)) >= lim:
            await it.response.send_message("今天去太多次了，明天請早。", ephemeral=True)
            return

        cost = d.get('entry_cost_money', 0)
        if db['money'] < cost:
            await it.response.send_message(f"錢不夠啦，要 {cost} 金幣。", ephemeral=True)
            return

        if cost > 0: await set_p_data(sid, money=db['money'] - cost)
        if lim: await log_map_in(sid, mid)

        start = d.get('start_pos', [1,1])
        if cog.load_p_map(it.user.id, mid, start, fresh=True):
            emb = discord.Embed(title=d.get('name'), description=cog.draw_map(it.user.id), color=0x4b9eaf)
            await it.message.edit(content=f"已進入 **{d.get('name')}**", embed=emb, view=cog.gen_view(it.user.id))

class BackBtn(Button):
    def __init__(self, aid):
        super().__init__(label="返回", style=discord.ButtonStyle.grey, row=4)
        self.aid = aid

    async def callback(self, it: discord.Interaction):
        v = self.view
        v.clear_items()
        v.add_item(WorldSel(v.cog.m_data, self.aid))
        await it.response.edit_message(content="重新挑一個世界：", view=v)

async def setup(bot: commands.Bot):
    await bot.add_cog(Map(bot))
    print('>> 地圖系統載入完畢 <<')
