import aiosqlite
import json
import random
import os

# 路徑設定
DB_PATH = 'game_data.db'
curr_dir = os.path.dirname(os.path.abspath(__file__))
items_path = os.path.join(curr_dir, 'items.json')

# 載入物品表
with open(items_path, 'r', encoding='utf-8') as f:
    ITEMS = json.load(f)

async def init_db():
    """初始化資料庫表結構"""
    async with aiosqlite.connect(DB_PATH) as db:
        # 玩家主表
        await db.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                money INTEGER DEFAULT 0,
                items TEXT DEFAULT '{}',
                rank TEXT DEFAULT '普通玩家',
                hp INTEGER DEFAULT 100,
                maxhp INTEGER DEFAULT 100,
                mp INTEGER DEFAULT 50,
                maxmp INTEGER DEFAULT 50,
                atk INTEGER DEFAULT 15,
                defense INTEGER DEFAULT 10,
                crit_rate REAL DEFAULT 0.05,
                crit_damage REAL DEFAULT 1.5,
                speed INTEGER DEFAULT 10,
                current_map_id TEXT DEFAULT 'map1_forest', 
                current_map_x INTEGER DEFAULT 2,           
                current_map_y INTEGER DEFAULT 4            
            )
        ''')

        # 補欄位用
        cols = [
            ('current_map_id', 'TEXT DEFAULT "map1_forest"'),
            ('current_map_x', 'INTEGER DEFAULT 2'),
            ('current_map_y', 'INTEGER DEFAULT 4'),
            ('crit_rate', 'REAL DEFAULT 0.05'),
            ('crit_damage', 'REAL DEFAULT 1.5'),
            ('speed', 'INTEGER DEFAULT 10')
        ]
        for cn, ct in cols:
            try:
                await db.execute(f'ALTER TABLE players ADD COLUMN {cn} {ct}')
            except:
                pass

        # 交易紀錄
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transaction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT,
                transaction_type TEXT,
                item_name TEXT,
                quantity INTEGER,
                price INTEGER,
                other_player_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 技能資料
        await db.execute('''
            CREATE TABLE IF NOT EXISTS player_skills (
                id TEXT PRIMARY KEY,
                skills TEXT DEFAULT '[]',
                equipped_skills TEXT DEFAULT '[]'
            )
        ''')
        
        # 裝備
        await db.execute('''
            CREATE TABLE IF NOT EXISTS equipment (
                uuid TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                equipment_id TEXT NOT NULL, 
                enhancement_level INTEGER DEFAULT 0,
                applied_modifiers TEXT DEFAULT '[]',
                is_equipped INTEGER DEFAULT 0,
                slot_idx INTEGER DEFAULT NULL 
            )
        ''')
        
        # 怪物
        await db.execute('''
            CREATE TABLE IF NOT EXISTS monster_data (
                m_name TEXT PRIMARY KEY,
                base_tier INTEGER NOT NULL DEFAULT 1,
                base_maxhp INTEGER NOT NULL DEFAULT 0,
                base_atk INTEGER NOT NULL DEFAULT 0,
                base_def INTEGER NOT NULL DEFAULT 0,
                skills TEXT DEFAULT '[]',
                drop_money INTEGER DEFAULT 0,
                drop_exp INTEGER DEFAULT 0,
                drop_items TEXT DEFAULT '',
                rarity TEXT DEFAULT 'common',
                intro TEXT DEFAULT '',
                picture_url TEXT DEFAULT ''
            )
        ''')

        # 地圖
        await db.execute('''
            CREATE TABLE IF NOT EXISTS player_map_entry_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT NOT NULL,
                map_id TEXT NOT NULL,
                entry_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 地圖進度
        await db.execute('''
            CREATE TABLE IF NOT EXISTS player_map_state (
                player_id TEXT NOT NULL,
                map_id TEXT NOT NULL,
                state_data TEXT NOT NULL,
                PRIMARY KEY (player_id, map_id)
            )
        ''')
        await db.commit()

async def get_p_data(p_id):
    """取得玩家數據"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM players WHERE id = ?', (p_id,)) as cur:
            res = await cur.fetchone()
            if res:
                cols = [d[0] for d in cur.description]
                d = dict(zip(cols, res))
                d['items'] = json.loads(d['items']) if d['items'] else {}
                return d
    return None

async def set_p_data(p_id, **kwargs):
    """更新玩家數據"""
    if not kwargs: return
    sql_d = {}
    for k, v in kwargs.items():
        sql_d[k] = json.dumps(v if v is not None else {}) if k == 'items' else v
    clause = ', '.join([f"`{k}` = ?" for k in sql_d.keys()])
    vals = tuple(sql_d.values()) 
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f'UPDATE players SET {clause} WHERE id = ?', (*vals, p_id))
        await db.commit()

async def add_p_sk(p_id, sk_n):
    """給玩家學技能"""
    d = await get_p_skills(p_id)
    if not d: d = {'skills': '[]', 'skill_levels': '{}'}
    sk = json.loads(d['skills'])
    lv = json.loads(d['skill_levels'])
    if sk_n not in sk:
        sk.append(sk_n)
        lv[sk_n] = 1
    await set_p_skills(p_id, skills=sk, skill_levels=lv)

async def update_p_cds(p_id, cds):
    """更新技能CD"""
    await set_p_skills(p_id, cooldowns=cds)

async def get_p_skills(p_id):
    """取得玩家技能清單"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT skills, equipped_skills FROM player_skills WHERE id = ?', (p_id,)) as cur:
            res = await cur.fetchone()
            if res:
                return {
                    'skills': json.loads(res[0]) if res[0] else [],
                    'equipped_skills': json.loads(res[1]) if res[1] else []
                }
    return {'skills': [], 'equipped_skills': []}

async def set_p_skills(p_id, **kwargs):
    """更新玩家技能清單"""
    async with aiosqlite.connect(DB_PATH) as db:
        if 'skills' in kwargs: kwargs['skills'] = json.dumps(kwargs['skills'])
        if 'equipped_skills' in kwargs: kwargs['equipped_skills'] = json.dumps(kwargs['equipped_skills'])
        clause = ', '.join(f'{k} = ?' for k in kwargs)
        vals = tuple(kwargs.values()) + (p_id,)
        await db.execute(f'UPDATE player_skills SET {clause} WHERE id = ?', vals)
        await db.commit()

async def create_p(p_d):
    """建立新玩家"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO players 
            (id, level, exp, money, items, rank, hp, maxhp, mp, maxmp, atk, defense, current_map_id, current_map_x, current_map_y)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            p_d['id'], p_d['level'], p_d['exp'], p_d['money'], p_d['items'], p_d['rank'],
            p_d['hp'], p_d['maxhp'], p_d['mp'], p_d['maxmp'], p_d['atk'], p_d['defense'],
            p_d.get('current_map_id', 'map1_forest'), p_d.get('current_map_x', 2), p_d.get('current_map_y', 4)
        ))
        await db.commit()

async def create_p_sk(sk_d):
    """初始化玩家技能數據"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO player_skills (id, skills, equipped_skills) VALUES (?, ?, ?)', 
                         (sk_d['id'], sk_d['skills'], sk_d['equipped_skills']))
        await db.commit()

async def give_items(p_id, items):
    """給予玩家物品"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT items FROM players WHERE id = ?', (p_id,)) as cur:
            res = await cur.fetchone()
            if res is None: return False
            try: bag = json.loads(res[0]) if res[0] else {}
            except: bag = {}
            for iid, q in items.items():
                iid = str(iid)
                bag[iid] = bag.get(iid, 0) + q
            await set_p_data(p_id, items=bag)
    return True

async def get_rnd_m_n(tier: int):
    """隨機拿怪名"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT m_name FROM monster_data WHERE base_tier <= ?', (tier,)) as cur:
            ms = await cur.fetchall()
            if ms: return random.choice([m[0] for m in ms])
            async with db.execute('SELECT m_name FROM monster_data') as cur2:
                all_m = await cur2.fetchall()
                if all_m: return random.choice([m[0] for m in all_m])
    return None

async def get_rnd_m():
    """隨機拿怪數據"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT m_name FROM monster_data') as cur:
            ms = await cur.fetchall()
            if not ms: return None
            m_n = random.choice([m[0] for m in ms])
            return await get_m_data(m_n)
        
def get_i_info(iid):
    """拿物品資訊"""
    return ITEMS.get(str(iid))

def get_i_info_by_n(i_n):
    """名字查物品"""
    for iid, d in ITEMS.items():
        if d['name'].lower() == i_n.lower(): return d
    return None

def get_i_id_by_n(i_n):
    """名字查ID"""
    for iid, d in ITEMS.items():
        if d['name'] == i_n: return iid
    return None

async def get_m_data(m_n, tier=None):
    """拿怪物資料含倍率"""
    async with aiosqlite.connect(DB_PATH) as db:
        q = '''SELECT m_name, base_tier, base_maxhp, base_atk, base_def,
                      skills, drop_money, drop_exp, drop_items,
                      rarity, intro, picture_url
               FROM monster_data WHERE m_name = ?'''
        async with db.execute(q, (m_n,)) as cur:
            res = await cur.fetchone()
            if not res: return None
            db_n, db_t, db_hp, db_atk, db_def = res[0], res[1] or 1, res[2] or 0, res[3] or 0, res[4] or 0
            db_sk, db_m, db_e, db_i = res[5], res[6] or 0, res[7] or 0, res[8] or ''
            db_r, db_intro, db_p = res[9], res[10] or '', res[11] or ''
            sk = json.loads(db_sk) if db_sk else []
            c_hp, c_atk, c_def, c_t = db_hp, db_atk, db_def, db_t
            if tier is not None and tier > db_t:
                diff = tier - db_t
                c_hp = int(db_hp * (1 + 0.25 * diff))
                c_atk = int(db_atk * (1 + 0.20 * diff))
                c_def = int(db_def * (1 + 0.15 * diff))
                c_t = tier
            return {
                'm_name': db_n, 'base_tier': db_t, 'current_tier': c_t,
                'm_maxhp': c_hp, 'm_atk': c_atk, 'm_def': c_def,
                'skills': sk, 'dropmoney': db_m, 'dropexp': db_e,
                'dropitem': db_i, 'rarity': db_r, 'm_intro': db_intro, 'picture': db_p
            }
    return None

async def add_t_log(p_id, t_t, i_n, q, pr, o_id):
    """存交易紀錄"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO transaction_history 
            (player_id, transaction_type, item_name, quantity, price, other_player_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (p_id, t_t, i_n, q, pr, o_id))
        await db.commit()

async def get_p_t_log(p_id, limit=30):
    """拿交易紀錄"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA timezone = '+08:00'")
        q = '''
            SELECT id, player_id, transaction_type, item_name, quantity, price, other_player_id,
                   datetime(timestamp, '+8 hours') as timestamp_utc8
            FROM transaction_history
            WHERE player_id = ? OR other_player_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        '''
        async with db.execute(q, (p_id, p_id, limit)) as cur:
            return await cur.fetchall()

async def add_exp(p_id: str, exp_g: int):
    """加經驗、檢查升級"""
    d = await get_p_data(p_id)
    if not d: return None, "找不到人"
    lv, exp = d['level'], d['exp'] + exp_g
    msgs = []
    while exp >= (100 + (lv - 1) * 20):
        exp -= (100 + (lv - 1) * 20)
        lv += 1
        msgs.append(f"恭喜升到等級 {lv}！")
    await set_p_data(p_id, level=lv, exp=exp)
    return {
        'old_level': d['level'], 'new_level': lv,
        'old_exp': d['exp'], 'new_exp': exp,
        'exp_gain': exp_g, 'level_up_messages': msgs
    }, None

async def get_eq_items(uid):
    """拿穿戴裝備"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM equipment WHERE owner_id = ? AND is_equipped = 1', (uid,)) as cur:
            return await cur.fetchall()

async def log_map_in(p_id: str, mid: str):
    """紀錄進地圖"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO player_map_entry_logs (player_id, map_id) VALUES (?, ?)", (p_id, mid))
        await db.commit()

async def get_today_map_cnt(p_id: str, mid: str) -> int:
    """今天進幾次"""
    async with aiosqlite.connect(DB_PATH) as db:
        q = "SELECT COUNT(*) FROM player_map_entry_logs WHERE player_id = ? AND map_id = ? AND DATE(entry_timestamp) = DATE('now', 'localtime')"
        async with db.execute(q, (p_id, mid)) as cur:
            res = await cur.fetchone()
            return res[0] if res else 0

async def save_map_progress(p_id: str, mid: str, state: str):
    """存地圖狀態"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO player_map_state (player_id, map_id, state_data) VALUES (?, ?, ?)", (p_id, mid, state))
        await db.commit()

async def load_map_progress(p_id: str, mid: str):
    """拿地圖狀態"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT state_data FROM player_map_state WHERE player_id = ? AND map_id = ?", (p_id, mid)) as cur:
            res = await cur.fetchone()
            return res[0] if res else None

async def del_map_progress(p_id: str, mid: str):
    """刪地圖狀態"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM player_map_state WHERE player_id = ? AND map_id = ?", (p_id, mid))
        await db.commit()

async def setup(bot):
    await init_db()
    print('>> 資料庫系統 <<')
