import discord
from discord.ext import commands
from discord.ui import View
import json
import random
import aiosqlite
from .database import *
import uuid

class Equipment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.eq_defs = {}  # 裝備定義
        self.set_data = {} # 套裝資料
        self.mod_defs = {} # 修飾詞定義
        self.i_defs = {}   # 物品資料
        self.load_data()

        # 槽位限制
        self.slots = {
            "sword": 1, "axe": 1, "bow": 1, "dagger": 1, "staff": 1, "wand": 1, "sword_great": 1,
            "helmet_light": 1, "helmet_heavy": 1, "helmet": 1,
            "chest_light": 1, "chest_heavy": 1, "chest": 1,
            "legs_light": 1, "legs_heavy": 1, "legs": 1,
            "boots_light": 1, "boots_heavy": 1, "boots": 1,
            "shield": 1, "shield_heavy": 1,
            "ring": 2, "amulet": 1,
            "main_armor": 1, "sub_armor": 1,
        }

    def load_data(self):
        """從 JSON 載入所有裝備跟修飾詞資料"""
        try:
            with open('cogs/equipment_data.json', 'r', encoding='utf-8') as f:
                d = json.load(f)
                self.eq_defs = {e['id']: e for e in d.get("equipment", [])}
                self.set_data = d.get("set_bonuses", {})
        except:
            print("讀不到 equipment_data.json")
        
        try:
            with open('cogs/modifiers.json', 'r', encoding='utf-8') as f:
                d = json.load(f)
                self.mod_defs = {m['id']: m for m in d.get("modifiers", [])}
        except:
            print("讀不到 modifiers.json")

        try:
            with open('cogs/items.json', 'r', encoding='utf-8') as f:
                self.i_defs = json.load(f)
        except:
            print("讀不到 items.json")
            
    def get_mat_n(self, mid):
        """拿材料名字"""
        d = self.i_defs.get(str(mid))
        return d['name'] if d else f"材料:{mid}"

    async def get_eq_inst(self, uid, owner=None):
        """從資料庫撈裝備實例"""
        async with aiosqlite.connect(DB_PATH) as db:
            q = 'SELECT uuid, owner_id, equipment_id, enhancement_level, applied_modifiers, is_equipped FROM equipment WHERE uuid = ?'
            p = [uid]
            if owner:
                q += ' AND owner_id = ?'
                p.append(owner)
            async with db.execute(q, p) as cur:
                row = await cur.fetchone()
                if row:
                    return {
                        "uuid": row[0], "owner": row[1], "eid": row[2],
                        "lv": row[3], "mods": json.loads(row[4]) if row[4] else [],
                        "is_eq": bool(row[5])
                    }
        return None
        
    async def get_p_eqs(self, uid):
        """拿玩家身上穿的所有裝備"""
        eqs = []
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT uuid, owner_id, equipment_id, enhancement_level, applied_modifiers, is_equipped FROM equipment WHERE owner_id = ? AND is_equipped = 1', (uid,)) as cur:
                rows = await cur.fetchall()
                for r in rows:
                    eqs.append({
                        "uuid": r[0], "owner": r[1], "eid": r[2],
                        "lv": r[3], "mods": json.loads(r[4]) if r[4] else [],
                        "is_eq": bool(r[5])
                    })
        return eqs

    async def calc_p_stats(self, uid, eqs):
        """算玩家的基本屬性加上裝備加成"""
        # 基礎值 (之後可以改成從資料庫拿)
        st = {"maxhp": 100, "maxmp": 50, "attack": 15, "defense": 10, "crit_rate": 0.05, "speed": 10}

        for e in eqs:
            d = self.eq_defs.get(e["eid"])
            if not d: continue

            # 1. 裝備基本值
            for k, v in d.get("stats", {}).items():
                st[k] = st.get(k, 0) + v

            # 2. 強化加成 (每級 +5%)
            lv = e.get("lv", 0)
            if lv > 0:
                bonus = 0.05 * lv
                for k, v in d.get("stats", {}).items():
                    if isinstance(v, (int, float)):
                        st[k] += round(v * bonus)

            # 3. 修飾詞加成
            for mid in e.get("mods", []):
                m_d = self.mod_defs.get(mid)
                if not m_d: continue
                for sk, sv in m_d.get("effects", {}).items():
                    if "_percent" in sk:
                        base_k = sk.replace("_percent", "")
                        # 先拿物品基本值來乘，沒有就拿玩家基本值
                        item_v = d.get("stats", {}).get(base_k, 0)
                        if item_v > 0:
                            st[base_k] += round(item_v * sv)
                        else:
                            p_base = {"maxhp": 100, "maxmp": 50, "attack": 15, "defense": 10}.get(base_k, 0)
                            st[base_k] += round(p_base * sv)
                    else:
                        base_k = sk.replace("_flat", "")
                        st[base_k] = st.get(base_k, 0) + sv
        return st

    async def calc_sets(self, eqs):
        """算套裝加成"""
        cnts = {}
        for e in eqs:
            d = self.eq_defs.get(e["eid"])
            if d and d.get("set_id"):
                sid = d["set_id"]
                cnts[sid] = cnts.get(sid, 0) + 1
        
        bonus = {}
        for sid, c in cnts.items():
            s_info = self.set_data.get(sid)
            if not s_info: continue
            
            best_eff = None
            max_c = 0
            for b in s_info.get("bonuses", []):
                if c >= b["count"] and b["count"] > max_c:
                    best_eff = b["effects"]
                    max_c = b["count"]
            
            if best_eff:
                for k, v in best_eff.items():
                    bonus[k] = bonus.get(k, 0) + v
        return bonus

    async def update_stats(self, uid):
        """重新計算並更新玩家的所有數值"""
        p = await get_p_data(uid)
        if not p: return

        eqs = await self.get_p_eqs(uid)
        st = await self.calc_p_stats(uid, eqs)
        sets = await self.calc_sets(eqs)

        # 套裝百分比加成要在最後算
        final = st.copy()
        for k, v in sets.items():
            if "_percent" in k:
                base_k = k.replace("_percent", "")
                base_v = st.get(base_k, 0)
                final[base_k] = round(final.get(base_k, 0) + base_v * v)
            else:
                final[k] = final.get(k, 0) + v
        
        # 存回資料庫
        m_hp, m_mp = final.get("maxhp", 1), final.get("maxmp", 1)
        atk, df = final.get("attack", 0), final.get("defense", 0)
        
        # 血量魔力不要超過上限
        hp = min(p.get('hp', m_hp), m_hp)
        if hp <= 0 and m_hp > 0: hp = 1
        mp = min(p.get('mp', m_mp), m_mp)
        
        await set_p_data(uid,
            hp=hp, maxhp=m_hp,
            mp=mp, maxmp=m_mp,
            atk=atk, defense=df,
            crit_rate=final.get("crit_rate"),
            speed=final.get("speed")
        )
        print(f"已更新玩家 {uid} 的戰鬥數值")

    @commands.command(name="make")
    async def make(self, ctx, eid: str):
        """做裝備"""
        uid = str(ctx.author.id)
        p = await get_p_data(uid)
        if not p:
            await ctx.send("先註冊吧！")
            return

        d = self.eq_defs.get(eid)
        if not d or not d.get("craftable"):
            await ctx.send("這東西沒辦法做喔。")
            return

        bag = p.get('items', {})
        money = p.get('money', 0)
        req_m = d.get('required_materials', {})
        price = d.get('crafting_price', 0)

        # 檢核資源
        errs = []
        deduct = {}
        for m_n, q in req_m.items():
            iid = get_i_id_by_n(m_n)
            if not iid:
                errs.append(f"配方錯誤：找不到 {m_n}")
                continue
            if bag.get(str(iid), 0) < q:
                errs.append(f"{self.get_mat_n(iid)} 不夠 (需要 {q}, 你只有 {bag.get(str(iid), 0)})")
            else:
                deduct[str(iid)] = q
        
        if errs:
            await ctx.send("材料不足：\n" + "\n".join(errs))
            return
        if money < price:
            await ctx.send(f"錢不夠啦，需要 {price}，你只有 {money}。")
            return

        # 扣錢扣料
        for iid, q in deduct.items():
            bag[iid] -= q
            if bag[iid] <= 0: del bag[iid]
        
        await set_p_data(uid, items=bag, money=money - price)

        # 隨機刷 1~2 個修飾詞
        mods = []
        pool = []
        for mid, m_d in self.mod_defs.items():
            if d["rarity"] in m_d["allowed_rarities"] and d["armor_type"] in m_d["allowed_armor_types"]:
                pool.append(mid)
        
        # 如果物品有專屬修飾詞池
        if d.get("possible_modifiers"):
            pool = [mid for mid in d["possible_modifiers"] if mid in self.mod_defs]

        if pool:
            mods = random.sample(pool, min(random.randint(1, 2), len(pool)))

        new_id = str(uuid.uuid4())
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                INSERT INTO equipment (uuid, owner_id, equipment_id, enhancement_level, applied_modifiers, is_equipped)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (new_id, uid, d['id'], 0, json.dumps(mods), 0))
            await db.commit()
        
        m_names = [self.mod_defs[mid]['name'] for mid in mods if mid in self.mod_defs]
        m_str = f" ({', '.join(m_names)})" if m_names else ""
        await ctx.send(f"鏘鏘！做出了 {d['name']}{m_str}！")

    @commands.command(name="iteminfo")
    async def iteminfo(self, ctx, key: str):
        """查裝備配方或數值"""
        d = self.eq_defs.get(key)
        if not d:
            for _, val in self.eq_defs.items():
                if val['name'] == key:
                    d = val
                    break
        
        if not d:
            await ctx.send(f"找不到『{key}』。")
            return

        emb = discord.Embed(title=f"{d['name']} ({d['id']})", description=f"稀有度: {d['rarity']}", color=0x3498db)
        
        st = "\n".join([f"{k.title()}: {v}" for k, v in d.get("stats", {}).items()])
        emb.add_field(name="基礎屬性", value=st or "無", inline=True)
        emb.add_field(name="類型", value=f"{d['type']} ({d['armor_type']})", inline=True)

        if d.get("craftable"):
            m = "\n".join([f"{self.get_mat_n(mid)}: {q}" for mid, q in d.get("required_materials", {}).items()])
            emb.add_field(name="製作材料", value=m or "免材料", inline=False)
            emb.add_field(name="手續費", value=str(d.get("crafting_price", 0)), inline=True)
        
        await ctx.send(embed=emb)

    @commands.command(name="myitem")
    async def myitem(self, ctx, uid_in: str = None):
        """看自己的裝備詳細資訊"""
        uid = str(ctx.author.id)
        
        if not uid_in:
            # 沒給 ID 就給選單
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute('SELECT uuid, equipment_id FROM equipment WHERE owner_id = ? ORDER BY is_equipped DESC', (uid,)) as cur:
                    rows = await cur.fetchall()

            if not rows:
                await ctx.send("你身上什麼都沒有。")
                return

            opts = []
            for r_uid, r_eid in rows:
                d = self.eq_defs.get(r_eid)
                if d:
                    opts.append(discord.SelectOption(label=f"{d['name']} (...{r_uid[-6:]})", value=r_uid))
            
            sel = discord.ui.Select(placeholder="挑一件來看看", options=opts)
            async def cb(it):
                if it.user.id != ctx.author.id: return
                await it.message.delete()
                await self.myitem(ctx, it.data['values'][0])

            sel.callback = cb
            v = View(); v.add_item(sel)
            await ctx.send("你的行囊：", view=v)
            return

        inst = await self.get_eq_inst(uid_in, owner=uid)
        if not inst:
            await ctx.send("找不到這件東西。")
            return

        d = self.eq_defs.get(inst["eid"])
        emb = discord.Embed(title=d['name'], description=f"稀有度: {d['rarity']}", color=0x2ecc71)
        emb.set_footer(text=f"UUID: {inst['uuid']}")

        # 算一下目前的屬性顯示
        cur_st = d.get("stats", {}).copy()
        if inst["lv"] > 0:
            for k, v in d.get("stats", {}).items():
                cur_st[k] = round(v * (1 + (0.05 * inst["lv"])))

        mod_list = []
        for mid in inst["mods"]:
            m_d = self.mod_defs.get(mid)
            if m_d:
                effs = []
                for sk, sv in m_d["effects"].items():
                    if "_percent" in sk:
                        bk = sk.replace("_percent","")
                        cur_st[bk] = cur_st.get(bk,0) + round(d.get("stats",{}).get(bk,0) * sv)
                        effs.append(f"{bk}: {sv*100:+.0f}%")
                    else:
                        cur_st[sk] = cur_st.get(sk,0) + sv
                        effs.append(f"{sk}: {sv:+}")
                mod_list.append(f"{m_d['name']}: {', '.join(effs)}")

        st_str = "\n".join([f"{k.title()}: {v}" for k, v in cur_st.items()])
        emb.add_field(name=f"目前數值 (強化 +{inst['lv']})", value=st_str or "無", inline=False)
        emb.add_field(name="修飾詞", value="\n".join(mod_list) if mod_list else "無", inline=False)
        emb.add_field(name="狀態", value="已裝備" if inst["is_eq"] else "未裝備", inline=True)
        await ctx.send(embed=emb)

    @commands.command()
    async def equip(self, ctx, uid_in: str):
        """穿上裝備"""
        uid = str(ctx.author.id)
        if not await get_p_data(uid): return

        inst = await self.get_eq_inst(uid_in, owner=uid)
        if not inst:
            await ctx.send("找不到這件東西。")
            return

        if inst["is_eq"]:
            await ctx.send("已經穿在身上啦。")
            return

        d = self.eq_defs.get(inst["eid"])
        tp = d["armor_type"]
        
        # 檢查槽位夠不夠
        cur_eqs = await self.get_p_eqs(uid)
        same_type = [e for e in cur_eqs if self.eq_defs.get(e["eid"])["armor_type"] == tp]
        
        async with aiosqlite.connect(DB_PATH) as db:
            if len(same_type) >= self.slots.get(tp, 1):
                # 滿了就自動脫掉第一件
                old = same_type[0]
                await db.execute('UPDATE equipment SET is_equipped = 0 WHERE uuid = ?', (old["uuid"],))
                old_d = self.eq_defs.get(old["eid"])
                await ctx.send(f"為了穿上 {d['name']}，先幫你把 {old_d['name']} 脫了。")

            await db.execute('UPDATE equipment SET is_equipped = 1 WHERE uuid = ?', (uid_in,))
            await db.commit()

        await self.update_stats(uid)
        await ctx.send(f"穿好囉！{d['name']} 已經裝備完成。")

    @commands.command()
    async def unequip(self, ctx, uid_in: str = None):
        """脫掉裝備"""
        uid = str(ctx.author.id)
        
        if not uid_in:
            eqs = await self.get_p_eqs(uid)
            if not eqs:
                await ctx.send("你身上光溜溜的，沒東西可以脫。")
                return

            opts = [discord.SelectOption(label=f"{self.eq_defs[e['eid']]['name']} (...{e['uuid'][-6:]})", value=e['uuid']) for e in eqs if e['eid'] in self.eq_defs]
            sel = discord.ui.Select(placeholder="要脫哪一件？", options=opts)
            async def cb(it):
                if it.user.id != ctx.author.id: return
                await it.message.delete()
                await self.unequip(ctx, it.data['values'][0])
            sel.callback = cb
            v = View(); v.add_item(sel)
            await ctx.send("脫裝清單：", view=v)
            return

        inst = await self.get_eq_inst(uid_in, owner=uid)
        if not inst or not inst["is_eq"]:
            await ctx.send("你沒穿這件裝備喔。")
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('UPDATE equipment SET is_equipped = 0 WHERE uuid = ? AND owner_id = ?', (uid_in, uid))
            await db.commit()

        await self.update_stats(uid)
        d = self.eq_defs.get(inst["eid"])
        await ctx.send(f"脫掉 {d['name']} 囉，數值已更新。")

    @commands.command(name="enhance")
    async def enhance(self, ctx, uid_in: str):
        """強化裝備"""
        uid = str(ctx.author.id)
        inst = await self.get_eq_inst(uid_in, owner=uid)
        if not inst: return

        d = self.eq_defs.get(inst["eid"])
        conf = d.get("enhancement_config")
        if not conf:
            await ctx.send("這件裝備不能強化喔。")
            return

        lv = inst["lv"]
        if lv >= conf.get("max_level", 10):
            await ctx.send("已經衝到頂啦！")
            return

        # 計算成本 (隨等級增加)
        req_m = {k: v * (lv + 1) for k, v in conf.get("materials_per_level", {}).items()}
        price = conf.get("cost_per_level", 50) * (lv + 1)

        p = await get_p_data(uid)
        bag = p.get('items', {})
        money = p.get('money', 0)

        deduct = {}
        errs = []
        for m_n, q in req_m.items():
            iid = get_i_id_by_n(m_n)
            if not iid or bag.get(str(iid), 0) < q:
                errs.append(f"{m_n} 不夠")
            else:
                deduct[str(iid)] = q
        
        if errs or money < price:
            await ctx.send(f"資源不夠喔，還差：{', '.join(errs)}{'、金幣' if money < price else ''}")
            return

        # 扣資源
        for iid, q in deduct.items():
            bag[iid] -= q
            if bag[iid] <= 0: del bag[iid]
        await set_p_data(uid, items=bag, money=money - price)

        # 衝裝！
        rate = max(0.1, 0.9 - (lv * 0.08))
        if random.random() <= rate:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute('UPDATE equipment SET enhancement_level = ? WHERE uuid = ?', (lv + 1, uid_in))
                await db.commit()
            await self.update_stats(uid)
            await ctx.send(f"【成功】{d['name']} 衝到了 +{lv+1}！太神啦！")
        else:
            await ctx.send(f"【失敗】爆了... {d['name']} 還是 +{lv}。材料全沒了嗚嗚。")

async def setup(bot: commands.Bot):
    await bot.add_cog(Equipment(bot))
    print('>> 裝備系統準備好了 <<')
