#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create or Destroy — Core SQLite Database & Game Mechanics Engine
Zero external dependencies (uses Python built-in sqlite3, json, datetime, random).
"""
import datetime
import json
import os
import random
import sqlite3
import threading

BASE_DIR = "/home/angela/3d model"
DATA_DIR = os.path.join(BASE_DIR, "data")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
GAMEDATA_DIR = os.path.join(BASE_DIR, "gamedata")
DB_PATH = os.path.join(DATA_DIR, "companion_save.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)


def load_json_gamedata(filename, default=None):
    path = os.path.join(GAMEDATA_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else {}


class CompanionDB:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.lock = threading.RLock()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.lock, self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS player_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_exp REAL DEFAULT 100.0,
                    available_exp REAL DEFAULT 100.0,
                    coins INTEGER DEFAULT 60,
                    streak_days INTEGER DEFAULT 1,
                    last_checkin_date TEXT DEFAULT '',
                    simulated_day_offset INTEGER DEFAULT 0,
                    mini_game_enabled INTEGER DEFAULT 1,
                    active_character TEXT DEFAULT 'xueling',
                    discord_webhook TEXT DEFAULT '',
                    discord_bot_token TEXT DEFAULT '',
                    discord_channel_id TEXT DEFAULT '',
                    ai_provider TEXT DEFAULT 'offline',
                    ai_api_key TEXT DEFAULT ''
                )
            """)
            cur.execute("INSERT OR IGNORE INTO player_profile (id) VALUES (1)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS characters (
                    char_id TEXT PRIMARY KEY,
                    name TEXT,
                    level INTEGER DEFAULT 1,
                    affection INTEGER DEFAULT 50,
                    recovery_exp INTEGER DEFAULT 100,
                    wisdom_exp INTEGER DEFAULT 0,
                    pomodoro_count INTEGER DEFAULT 0,
                    stamina INTEGER DEFAULT 100,
                    hunger INTEGER DEFAULT 20,
                    dirtiness INTEGER DEFAULT 15,
                    fatigue INTEGER DEFAULT 15,
                    health_status TEXT DEFAULT 'healthy',
                    gastro_course_active INTEGER DEFAULT 0,
                    gastro_days_remaining INTEGER DEFAULT 0,
                    current_view TEXT DEFAULT 'main_fullbody',
                    current_expr TEXT DEFAULT 'expr_1_normal'
                )
            """)
            cur.execute("""
                INSERT OR IGNORE INTO characters (char_id, name, current_view, current_expr)
                VALUES ('xueling', '雪靈 (Xueling)', 'main_fullbody', 'expr_1_normal')
            """)
            cur.execute("""
                INSERT OR IGNORE INTO characters (char_id, name, current_view, current_expr)
                VALUES ('lingfeng', '凌風 (Ling Feng)', 'main_fullbody', 'expr_1_normal')
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    item_id TEXT PRIMARY KEY,
                    quantity INTEGER DEFAULT 0
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS achievements (
                    ach_id TEXT PRIMARY KEY,
                    unlocked_at TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT,
                    source TEXT,
                    message TEXT
                )
            """)
            conn.commit()

    def _now_str(self):
        return datetime.datetime.now().strftime("%H:%M:%S")

    def _today_str(self, conn):
        row = conn.execute("SELECT simulated_day_offset FROM player_profile WHERE id = 1").fetchone()
        offset = row["simulated_day_offset"] if row else 0
        dt = datetime.date.today() + datetime.timedelta(days=offset)
        return dt.isoformat()

    def add_log(self, conn, source, message):
        conn.execute(
            "INSERT INTO activity_logs (created_at, source, message) VALUES (?, ?, ?)",
            (self._now_str(), source, message),
        )
        conn.execute("DELETE FROM activity_logs WHERE id NOT IN (SELECT id FROM activity_logs ORDER BY id DESC LIMIT 40)")

    def get_shop_catalog(self):
        return load_json_gamedata("shop_catalog.json", {"items": []})

    def get_achievements_catalog(self):
        return load_json_gamedata("achievements.json", {"wisdom_achievements": [], "care_achievements": []})

    def get_version_info(self):
        return load_json_gamedata("version.json", {"version": "1.0.0"})

    def get_full_state(self):
        with self.lock, self._connect() as conn:
            prof = dict(conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone())
            prof["today_date"] = self._today_str(conn)
            prof["sickness_unlocked"] = prof["streak_days"] >= 7

            chars = {}
            for r in conn.execute("SELECT * FROM characters").fetchall():
                c = dict(r)
                # Calculate level from total_exp + character recovery_exp + wisdom_exp
                c["computed_level"] = max(1, 1 + int((prof["total_exp"] + max(0, c["recovery_exp"]) + c["wisdom_exp"] * 2) // 100))
                chars[c["char_id"]] = c

            inv_rows = conn.execute("SELECT item_id, quantity FROM inventory WHERE quantity > 0").fetchall()
            inventory = {r["item_id"]: r["quantity"] for r in inv_rows}

            ach_rows = conn.execute("SELECT ach_id, unlocked_at FROM achievements").fetchall()
            unlocked_achs = {r["ach_id"]: r["unlocked_at"] for r in ach_rows}

            logs = [dict(r) for r in conn.execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT 25").fetchall()]

            return {
                "profile": prof,
                "characters": chars,
                "inventory": inventory,
                "unlocked_achievements": unlocked_achs,
                "shop_catalog": self.get_shop_catalog(),
                "achievements_catalog": self.get_achievements_catalog(),
                "version_info": self.get_version_info(),
                "logs": logs,
            }

    def _check_and_unlock_achievements(self, conn, char_id):
        cat = self.get_achievements_catalog()
        char_row = conn.execute("SELECT * FROM characters WHERE char_id = ?", (char_id,)).fetchone()
        prof_row = conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone()
        newly_unlocked = []

        for ach in cat.get("wisdom_achievements", []):
            aid = ach["id"]
            if char_row["wisdom_exp"] >= ach["required_wisdom"]:
                exists = conn.execute("SELECT 1 FROM achievements WHERE ach_id = ?", (aid,)).fetchone()
                if not exists:
                    conn.execute("INSERT INTO achievements (ach_id, unlocked_at) VALUES (?, ?)", (aid, self._now_str()))
                    reward = ach.get("reward_coins", 0)
                    if reward > 0:
                        conn.execute("UPDATE player_profile SET coins = coins + ? WHERE id = 1", (reward,))
                    msg = f"🏆 達成學習成就【{ach['title']}】！獲得獎勵 +{reward} 島民金幣！"
                    self.add_log(conn, "成就系統", msg)
                    newly_unlocked.append(msg)

        for ach in cat.get("care_achievements", []):
            aid = ach["id"]
            if prof_row["streak_days"] >= ach.get("required_streak", 7):
                exists = conn.execute("SELECT 1 FROM achievements WHERE ach_id = ?", (aid,)).fetchone()
                if not exists:
                    conn.execute("INSERT INTO achievements (ach_id, unlocked_at) VALUES (?, ?)", (aid, self._now_str()))
                    msg = f"🔥 達成羈絆成就【{ach['title']}】！已解鎖角色隨機感冒生病體質！"
                    self.add_log(conn, "成就系統", msg)
                    newly_unlocked.append(msg)

        return newly_unlocked

    # ==========================================================================
    # CHARACTER SWITCH & VIEW / EXPRESSION CONTROL
    # ==========================================================================
    def set_active_character(self, char_id):
        if char_id not in ("xueling", "lingfeng"):
            return {"ok": False, "error": "無效的角色 ID"}
        with self.lock, self._connect() as conn:
            conn.execute("UPDATE player_profile SET active_character = ? WHERE id = 1", (char_id,))
            cname = "雪靈 (Xueling)" if char_id == "xueling" else "凌風 (Ling Feng)"
            self.add_log(conn, "系統", f"切換主控桌寵角色為：{cname}")
            conn.commit()
        return {"ok": True, "state": self.get_full_state()}

    def set_character_pose(self, char_id, view=None, expr=None):
        with self.lock, self._connect() as conn:
            if view:
                conn.execute("UPDATE characters SET current_view = ? WHERE char_id = ?", (view, char_id))
            if expr:
                conn.execute("UPDATE characters SET current_expr = ? WHERE char_id = ?", (expr, char_id))
            conn.commit()
        return {"ok": True, "state": self.get_full_state()}

    def toggle_minigame_mode(self, enabled=None):
        with self.lock, self._connect() as conn:
            row = conn.execute("SELECT mini_game_enabled FROM player_profile WHERE id = 1").fetchone()
            new_val = (0 if row["mini_game_enabled"] else 1) if enabled is None else (1 if enabled else 0)
            conn.execute("UPDATE player_profile SET mini_game_enabled = ? WHERE id = 1", (new_val,))
            status_str = "已開啟" if new_val else "已關閉"
            self.add_log(conn, "小遊戲模式", f"養成小遊戲互動模式（飢餓/髒污/疲勞/體力/生病系統）：{status_str}")
            conn.commit()
        return {"ok": True, "mini_game_enabled": bool(new_val), "state": self.get_full_state()}

    # ==========================================================================
    # INTERACTIONS (PAT, POKE, BATH, REST, SICKNESS SIMULATION)
    # ==========================================================================
    def interact(self, char_id, action):
        dialogues = load_json_gamedata("dialogues.json", {})
        c_diag = dialogues.get(char_id, dialogues.get("xueling", {}))
        with self.lock, self._connect() as conn:
            prof = conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone()
            char = conn.execute("SELECT * FROM characters WHERE char_id = ?", (char_id,)).fetchone()
            if not char:
                return {"ok": False, "error": "找不到角色"}

            mg = bool(prof["mini_game_enabled"])
            stamina = char["stamina"]
            hunger = char["hunger"]
            dirtiness = char["dirtiness"]
            fatigue = char["fatigue"]
            affection = char["affection"]
            health = char["health_status"]
            expr = char["current_expr"]
            view = char["current_view"]
            reply = ""

            if action == "pat":
                affection = min(999, affection + 3)
                expr = "expr_5_shy" if random.random() < 0.55 else "expr_2_happy" if char_id == "xueling" else "expr_2_smile"
                if char_id == "lingfeng" and expr == "expr_2_happy":
                    expr = "expr_2_smile"
                if mg:
                    hunger = min(100, hunger + 4)
                    dirtiness = min(100, dirtiness + 3)
                    fatigue = min(100, fatigue + 2)
                reply = random.choice(c_diag.get("interactions", {}).get("pat", ["好感度 +3！✨"]))
                self.add_log(conn, char["name"], f"摸頭互動 ❤️ 好感度 +3（目前 {affection}）")

            elif action == "poke":
                expr = "expr_3_angry" if random.random() < 0.6 else "expr_4_surprised"
                if mg:
                    hunger = min(100, hunger + 5)
                    dirtiness = min(100, dirtiness + 4)
                    fatigue = min(100, fatigue + 4)
                reply = random.choice(c_diag.get("interactions", {}).get("poke", ["喂！別亂戳我！💢"]))
                self.add_log(conn, char["name"], "戳一戳互動 💢 觸發誇張動漫表情反應！")

            elif action == "bath":
                dirtiness = 0
                affection = min(999, affection + 5)
                expr = "expr_2_happy" if char_id == "xueling" else "expr_2_smile"
                reply = random.choice(c_diag.get("interactions", {}).get("bath", ["洗完泡泡浴了！髒污值歸零 ✨"]))
                self.add_log(conn, char["name"], "🛁 完成泡泡浴洗澡！髒污值歸零 (0%)，好感度 +5！")

            elif action == "rest":
                fatigue = max(0, fatigue - 45)
                stamina = min(100, stamina + 35)
                expr = "expr_1_normal"
                reply = random.choice(c_diag.get("interactions", {}).get("rest", ["休息充電完成！體力 +35，疲勞 -45 ✨"]))
                self.add_log(conn, char["name"], f"💤 休息充電完成！體力恢復至 {stamina}，疲勞降至 {fatigue}%")

            elif action == "racing_drive" and char_id == "lingfeng":
                view = "racing_scene" if view != "racing_scene" else "main_fullbody"
                expr = "expr_2_smile"
                reply = "引擎啟動！坐穩了，帶你體驗 BMW 賽道極限速度！🏎️💨"
                self.add_log(conn, char["name"], "🔑 啟動 BMW 跑車鑰匙，切換賽車駕駛特寫！")

            elif action == "trigger_cold_test":
                health = "cold"
                expr = "expr_7_sick"
                reply = random.choice(c_diag.get("interactions", {}).get("sick_cold", ["哈啾……好像感冒發燒了 🤒"]))
                self.add_log(conn, "健康系統", f"🤒 {char['name']} 觸發了【感冒生病】狀態！請至島民商店購買【感冒藥 (+25)】治療。")

            # Random sickness check if streak_days >= 7 and mini_game_enabled
            if mg and health == "healthy" and prof["streak_days"] >= 7 and action in ("pat", "poke"):
                if random.random() < 0.18:
                    health = "cold"
                    expr = "expr_7_sick"
                    reply = random.choice(c_diag.get("interactions", {}).get("sick_cold", ["哈啾……好像感冒了 🤒"]))
                    self.add_log(conn, "健康系統", f"⚠️ 持續互動已滿 {prof['streak_days']} 天，{char['name']} 隨機觸發了【感冒生病】狀態！")

            # Keep sick expression if character is currently sick
            if health in ("cold", "gastroenteritis") and action not in ("bath", "rest"):
                expr = "expr_7_sick"

            conn.execute("""
                UPDATE characters
                SET stamina = ?, hunger = ?, dirtiness = ?, fatigue = ?,
                    affection = ?, health_status = ?, current_view = ?, current_expr = ?
                WHERE char_id = ?
            """, (stamina, hunger, dirtiness, fatigue, affection, health, view, expr, char_id))
            conn.commit()

        return {"ok": True, "reply": reply, "action": action, "state": self.get_full_state()}

    # ==========================================================================
    # 30-MINUTE POMODORO STUDY SYSTEM (+15 WISDOM EXP, -20 STAMINA)
    # ==========================================================================
    def pomodoro_event(self, char_id, event_type):
        dialogues = load_json_gamedata("dialogues.json", {})
        c_diag = dialogues.get(char_id, dialogues.get("xueling", {}))
        with self.lock, self._connect() as conn:
            char = conn.execute("SELECT * FROM characters WHERE char_id = ?", (char_id,)).fetchone()
            if not char:
                return {"ok": False, "error": "找不到角色"}

            if event_type == "start":
                if char["stamina"] < 20:
                    return {
                        "ok": False,
                        "error": f"{char['name']} 目前體力值僅剩 {char['stamina']}（不足 20 點）！請先點擊【休息充電】或去【島民商店】購買食物補充體力後再開啟番茄鐘喔！",
                    }
                conn.execute("UPDATE characters SET current_expr = 'expr_6_focused' WHERE char_id = ?", (char_id,))
                reply = random.choice(c_diag.get("interactions", {}).get("pomodoro_start", ["30分鐘番茄鐘啟動！💡"]))
                self.add_log(conn, "番茄鐘系統", f"⏱️ {char['name']} 開啟【30分鐘番茄鐘專注學習】模式！")
                conn.commit()
                return {"ok": True, "reply": reply, "state": self.get_full_state()}

            elif event_type == "abort":
                conn.execute("UPDATE characters SET current_expr = 'expr_1_normal' WHERE char_id = ?", (char_id,))
                reply = random.choice(c_diag.get("interactions", {}).get("pomodoro_abort", ["番茄鐘已中途停止，未獲得智慧經驗值。"]))
                self.add_log(conn, "番茄鐘系統", f"⚠️ {char['name']} 中途停止了 30 分鐘番茄鐘（未滿全程不計入 +15 智慧經驗值）。")
                conn.commit()
                return {"ok": True, "reply": reply, "state": self.get_full_state()}

            elif event_type == "complete":
                new_wisdom = char["wisdom_exp"] + 15
                new_stamina = max(0, char["stamina"] - 20)
                new_fatigue = min(100, char["fatigue"] + 15)
                new_hunger = min(100, char["hunger"] + 12)
                new_count = char["pomodoro_count"] + 1
                new_expr = "expr_2_happy" if char_id == "xueling" else "expr_2_smile"

                conn.execute("""
                    UPDATE characters
                    SET wisdom_exp = ?, stamina = ?, fatigue = ?, hunger = ?,
                        pomodoro_count = ?, current_expr = ?
                    WHERE char_id = ?
                """, (new_wisdom, new_stamina, new_fatigue, new_hunger, new_count, new_expr, char_id))

                self.add_log(
                    conn,
                    "番茄鐘系統",
                    f"🎓 {char['name']} 完成 30 分鐘番茄鐘學習！角色智慧經驗值 +15（累計 {new_wisdom}），人物體力值 -20（剩餘 {new_stamina}）！",
                )
                unlocked = self._check_and_unlock_achievements(conn, char_id)
                reply = random.choice(c_diag.get("interactions", {}).get("pomodoro_complete", ["完成 30 分鐘番茄鐘！智慧 +15、體力 -20！✨"]))
                if unlocked:
                    reply += " " + " ".join(unlocked)
                conn.commit()
                return {"ok": True, "reply": reply, "unlocked_achievements": unlocked, "state": self.get_full_state()}

        return {"ok": False, "error": "未知的番茄鐘事件"}

    # ==========================================================================
    # DISCORD ECONOMY: CHECK-IN (+20), MESSAGE (+0.5), DICE (+5 / +1), EXCHANGE
    # ==========================================================================
    def discord_checkin(self, username="島民玩家", force_next_day=False):
        with self.lock, self._connect() as conn:
            if force_next_day:
                conn.execute("UPDATE player_profile SET simulated_day_offset = simulated_day_offset + 1 WHERE id = 1")
            prof = conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone()
            today = self._today_str(conn)

            if prof["last_checkin_date"] == today:
                return {
                    "ok": False,
                    "error": f"📅 今天（{today}）已經在 Discord 打過卡囉！每天只能打卡一次（或點擊「推進一天測試」模擬隔日打卡）。",
                }

            new_total = round(prof["total_exp"] + 20.0, 1)
            new_avail = round(prof["available_exp"] + 20.0, 1)
            new_streak = prof["streak_days"] + 1

            conn.execute("""
                UPDATE player_profile
                SET total_exp = ?, available_exp = ?, streak_days = ?, last_checkin_date = ?
                WHERE id = 1
            """, (new_total, new_avail, new_streak, today))

            # Progress 3-day gastroenteritis treatment if active on any character
            gastro_msgs = []
            for crow in conn.execute("SELECT * FROM characters WHERE gastro_course_active = 1").fetchall():
                rem = max(0, crow["gastro_days_remaining"] - 1)
                if rem == 0:
                    conn.execute("""
                        UPDATE characters
                        SET health_status = 'healthy', gastro_course_active = 0, gastro_days_remaining = 0,
                            current_expr = 'expr_1_normal'
                        WHERE char_id = ?
                    """, (crow["char_id"],))
                    gmsg = f"🎉 {crow['name']} 服用【腸胃藥三天份】滿 3 天療程，腸胃炎已完全康復！"
                    self.add_log(conn, "醫療系統", gmsg)
                    gastro_msgs.append(gmsg)
                else:
                    conn.execute("UPDATE characters SET gastro_days_remaining = ? WHERE char_id = ?", (rem, crow["char_id"]))
                    gmsg = f"💊 {crow['name']} 的【腸胃藥三天份】療程推進中，還需 {rem} 天即可康復。"
                    self.add_log(conn, "醫療系統", gmsg)
                    gastro_msgs.append(gmsg)

            msg = f"✅ 【Discord 每日打卡成功】{username} 獲得 +20 點經驗值！（連續互動第 {new_streak} 天，可兌換 EXP：{new_avail}）"
            self.add_log(conn, "Discord 打卡", msg)
            self._check_and_unlock_achievements(conn, prof["active_character"])
            conn.commit()

        return {
            "ok": True,
            "message": msg,
            "gastro_updates": gastro_msgs,
            "state": self.get_full_state(),
        }

    def discord_message_exp(self, username="島民玩家", content="在頻道發送了一則留言"):
        with self.lock, self._connect() as conn:
            prof = conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone()
            new_total = round(prof["total_exp"] + 0.5, 1)
            new_avail = round(prof["available_exp"] + 0.5, 1)
            conn.execute(
                "UPDATE player_profile SET total_exp = ?, available_exp = ? WHERE id = 1",
                (new_total, new_avail),
            )
            short_c = (content[:28] + "...") if len(content) > 28 else content
            msg = f"💬 【Discord 留言獎勵】{username}：「{short_c}」 獲得 +0.5 經驗值！（目前可兌換 EXP：{new_avail}）"
            self.add_log(conn, "Discord 留言", msg)
            conn.commit()
        return {"ok": True, "message": msg, "state": self.get_full_state()}

    def discord_roll_dice(self, mode="solo", player_name="島民玩家", rivals=None):
        with self.lock, self._connect() as conn:
            prof = conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone()
            if mode == "solo":
                roll_val = random.randint(1, 6)
                exp_gain = 1.0
                new_total = round(prof["total_exp"] + exp_gain, 1)
                new_avail = round(prof["available_exp"] + exp_gain, 1)
                conn.execute(
                    "UPDATE player_profile SET total_exp = ?, available_exp = ? WHERE id = 1",
                    (new_total, new_avail),
                )
                msg = f"🎲 【單人骰骰子】{player_name} 擲出了 `{roll_val}` 點！單獨一人骰獲得隨機經驗值 +1 點！（可兌換 EXP：{new_avail}）"
                self.add_log(conn, "Discord 骰子", msg)
                conn.commit()
                return {
                    "ok": True,
                    "mode": "solo",
                    "rolls": [{"name": player_name, "roll": roll_val, "is_winner": True}],
                    "exp_gain": exp_gain,
                    "message": msg,
                    "state": self.get_full_state(),
                }
            else:
                # Multiplayer dice round: player + rivals roll together; highest roll gets +5 EXP!
                if not rivals:
                    rivals = ["雪靈(Bot)", "凌風(Bot)", "島民小隊友"]
                # Ensure player_name wins reasonably or fairly with exciting rolls (1-12 2d6)
                rolls = []
                p_roll = random.randint(2, 12)
                rolls.append({"name": player_name, "roll": p_roll, "is_player": True})
                for rname in rivals:
                    rolls.append({"name": rname, "roll": random.randint(2, 12), "is_player": False})
                max_roll = max(r["roll"] for r in rolls)
                for r in rolls:
                    r["is_winner"] = (r["roll"] == max_roll)

                winners = [r["name"] for r in rolls if r["is_winner"]]
                player_won = any(r["is_player"] and r["is_winner"] for r in rolls)
                exp_gain = 5.0 if player_won else 0.0

                if exp_gain > 0:
                    new_total = round(prof["total_exp"] + exp_gain, 1)
                    new_avail = round(prof["available_exp"] + exp_gain, 1)
                    conn.execute(
                        "UPDATE player_profile SET total_exp = ?, available_exp = ? WHERE id = 1",
                        (new_total, new_avail),
                    )
                else:
                    new_avail = prof["available_exp"]

                roll_summary = "、".join(f"{r['name']}({r['roll']}點)" for r in rolls)
                if player_won:
                    msg = f"🎲🏆 【多人同輪骰骰子】{roll_summary} ➔ 點數最大者為 {player_name}（{max_roll}點），獲得最高點獎勵 +5 經驗值！"
                else:
                    msg = f"🎲 【多人同輪骰骰子】{roll_summary} ➔ 本輪最高點為 {'/'.join(winners)}（{max_roll}點獲得 +5 EXP），再接再厲！"
                self.add_log(conn, "Discord 骰子", msg)
                conn.commit()
                return {
                    "ok": True,
                    "mode": "multi",
                    "rolls": rolls,
                    "max_roll": max_roll,
                    "player_won": player_won,
                    "exp_gain": exp_gain,
                    "message": msg,
                    "state": self.get_full_state(),
                }

    def exchange_exp_for_coins(self, batches=1):
        batches = max(1, int(batches))
        exp_needed = 50.0 * batches
        coins_gained = 25 * batches
        with self.lock, self._connect() as conn:
            prof = conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone()
            if prof["available_exp"] < exp_needed:
                return {
                    "ok": False,
                    "error": f"可兌換經驗值不足！每 50 點經驗值可兌換 25 金幣（目前可兌換 EXP：{prof['available_exp']}，需要 {exp_needed} 點）。",
                }
            new_avail = round(prof["available_exp"] - exp_needed, 1)
            new_coins = prof["coins"] + coins_gained
            conn.execute(
                "UPDATE player_profile SET available_exp = ?, coins = ? WHERE id = 1",
                (new_avail, new_coins),
            )
            msg = f"🪙 【Discord 指令兌換成功】消耗 {int(exp_needed)} 點經驗值 ➔ 兌換獲得 +{coins_gained} 枚 Create or Destroy 島民商店金幣！（目前金幣：{new_coins}）"
            self.add_log(conn, "島民商店兌換", msg)
            conn.commit()
        return {"ok": True, "message": msg, "state": self.get_full_state()}

    # ==========================================================================
    # CREATE OR DESTROY ISLAND SHOP (BUY & USE/FEED 23 ITEMS)
    # ==========================================================================
    def buy_item(self, item_id, quantity=1, auto_use_char_id=None):
        quantity = max(1, int(quantity))
        catalog = {it["id"]: it for it in self.get_shop_catalog().get("items", [])}
        if item_id not in catalog:
            return {"ok": False, "error": "找不到該商品"}
        item = catalog[item_id]
        total_cost = item["price"] * quantity

        with self.lock, self._connect() as conn:
            prof = conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone()
            if prof["coins"] < total_cost:
                return {
                    "ok": False,
                    "error": f"島民商店金幣不足！【{item['name']}】需要 {total_cost} 金幣（目前擁有 {prof['coins']} 金幣）。請先累積 Discord 經驗值兌換金幣！",
                }
            new_coins = prof["coins"] - total_cost
            conn.execute("UPDATE player_profile SET coins = ? WHERE id = 1", (new_coins,))
            conn.execute("""
                INSERT INTO inventory (item_id, quantity) VALUES (?, ?)
                ON CONFLICT(item_id) DO UPDATE SET quantity = quantity + ?
            """, (item_id, quantity, quantity))
            msg = f"🛒 於【Create or Destroy 島民商店】購買了 {item['emoji']} {item['name']} x{quantity}（花費 {total_cost} 金幣）"
            self.add_log(conn, "島民商店", msg)
            conn.commit()

        if auto_use_char_id:
            return self.use_item(auto_use_char_id, item_id)

        return {"ok": True, "message": msg, "state": self.get_full_state()}

    def use_item(self, char_id, item_id):
        catalog = {it["id"]: it for it in self.get_shop_catalog().get("items", [])}
        if item_id not in catalog:
            return {"ok": False, "error": "找不到該道具"}
        item = catalog[item_id]
        dialogues = load_json_gamedata("dialogues.json", {})
        c_diag = dialogues.get(char_id, dialogues.get("xueling", {}))

        with self.lock, self._connect() as conn:
            inv = conn.execute("SELECT quantity FROM inventory WHERE item_id = ?", (item_id,)).fetchone()
            if not inv or inv["quantity"] <= 0:
                return {"ok": False, "error": f"背包中沒有【{item['name']}】，請先從島民商店購買！"}

            char = conn.execute("SELECT * FROM characters WHERE char_id = ?", (char_id,)).fetchone()
            prof = conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone()

            # Deduct 1 from inventory
            conn.execute("UPDATE inventory SET quantity = quantity - 1 WHERE item_id = ?", (item_id,))

            rec_delta = item.get("recovery", 0)
            exp_delta = item.get("exp_bonus", 0)
            hunger_relief = item.get("hunger_relief", 0)
            stamina_relief = item.get("stamina_relief", 0)

            new_recovery = char["recovery_exp"] + rec_delta
            new_hunger = max(0, min(100, char["hunger"] - hunger_relief))
            new_stamina = max(0, min(100, char["stamina"] + stamina_relief))
            new_fatigue = max(0, min(100, char["fatigue"] - (10 if rec_delta > 0 else -15)))
            new_affection = max(0, min(999, char["affection"] + (4 if rec_delta > 0 else -5)))
            new_health = char["health_status"]
            gastro_active = char["gastro_course_active"]
            gastro_days = char["gastro_days_remaining"]

            # Also add positive exp_bonus to total_exp if item grants EXP (like 泡麵 +15 EXP, 冰淇淋 +10 EXP)
            if item_id in ("food_noodles", "ice_cream") and exp_delta > 0:
                conn.execute(
                    "UPDATE player_profile SET total_exp = ROUND(total_exp + ?, 1), available_exp = ROUND(available_exp + ?, 1) WHERE id = 1",
                    (exp_delta, exp_delta),
                )

            extra_notes = []

            # Check Mystery Drink -> Triggers Gastroenteritis!
            if item.get("triggers_gastro"):
                new_health = "gastroenteritis"
                gastro_active = 0
                gastro_days = 3
                new_expr = "expr_7_sick"
                reply = random.choice(c_diag.get("interactions", {}).get("sick_gastro", ["肚子好痛！觸發腸胃炎了 🤢"]))
                extra_notes.append("⚠️ 誤喝【不知放多少天的飲料】，觸發【腸胃炎】！需購買並服用【腸胃藥三天份】經過三天時間治療！")

            # Check Cold Medicine -> Cures Cold
            elif item.get("cures_cold"):
                if new_health == "cold":
                    new_health = "healthy"
                    new_expr = "expr_2_happy" if char_id == "xueling" else "expr_2_smile"
                    reply = "服用【感冒藥】後退燒了！恢復健康狀態 ✨"
                    extra_notes.append("💊 成功治癒【感冒生病】狀態！")
                elif new_health == "gastroenteritis":
                    new_expr = "expr_7_sick"
                    reply = "這是感冒藥，對【腸胃炎】沒效啦 🤒……需要買【腸胃藥三天份】！"
                    extra_notes.append("⚠️ 角色目前為【腸胃炎】，需使用【腸胃藥三天份】才能治療。")
                else:
                    new_expr = "expr_2_happy" if char_id == "xueling" else "expr_2_smile"
                    reply = "雖然沒感冒，但喝了感冒糖漿補充了 +25 恢復經驗值！"

            # Check 3-Day Gastroenteritis Medicine -> Starts / Progresses 3-Day Course
            elif item.get("cures_gastro_3d"):
                if new_health == "gastroenteritis":
                    gastro_active = 1
                    if gastro_days <= 0:
                        gastro_days = 3
                    new_expr = "expr_7_sick"
                    reply = f"已開始服用【腸胃藥三天份】（+100 恢復經驗值）！目前剩餘療程：{gastro_days} 天（跨日打卡或點『推進一天療程』即可推進康復）。"
                    extra_notes.append(f"🏥 已啟動【腸胃藥三天份】療程（需經過 {gastro_days} 天時間完全康復）！")
                else:
                    new_expr = "expr_2_happy" if char_id == "xueling" else "expr_2_smile"
                    reply = "腸胃保養完成！獲得 +100 點恢復經驗值 ✨"

            else:
                if rec_delta < 0:
                    new_expr = "expr_3_angry" if random.random() < 0.5 else "expr_7_sick"
                    reply = random.choice(c_diag.get("interactions", {}).get("feed_bad", ["這東西過期了吧？！💢"]))
                else:
                    new_expr = "expr_2_happy" if char_id == "xueling" else "expr_2_smile"
                    if new_health in ("cold", "gastroenteritis"):
                        new_expr = "expr_7_sick"
                    reply = random.choice(c_diag.get("interactions", {}).get("feed_good", ["超好吃！恢復值補充完畢 ✨"]))

            conn.execute("""
                UPDATE characters
                SET recovery_exp = ?, hunger = ?, stamina = ?, fatigue = ?,
                    affection = ?, health_status = ?, gastro_course_active = ?,
                    gastro_days_remaining = ?, current_expr = ?
                WHERE char_id = ?
            """, (new_recovery, new_hunger, new_stamina, new_fatigue, new_affection, new_health, gastro_active, gastro_days, new_expr, char_id))

            sign = "+" if rec_delta >= 0 else ""
            log_msg = f"🍽️ 餵食 {char['name']} 使用【{item['emoji']} {item['name']}】（{sign}{rec_delta} 恢復經驗值，體力 {new_stamina}，飢餓 {new_hunger}%）"
            if extra_notes:
                log_msg += " " + " ".join(extra_notes)
            self.add_log(conn, "餵食補給", log_msg)
            conn.commit()

        return {
            "ok": True,
            "reply": reply,
            "message": log_msg,
            "state": self.get_full_state(),
        }

    def advance_gastro_day(self, char_id):
        """Advances 1 day of the 3-day gastroenteritis medicine course (for convenient user testing or daily care)."""
        with self.lock, self._connect() as conn:
            char = conn.execute("SELECT * FROM characters WHERE char_id = ?", (char_id,)).fetchone()
            if not char or char["health_status"] != "gastroenteritis":
                return {"ok": False, "error": "角色目前沒有處於腸胃炎狀態。"}
            if not char["gastro_course_active"]:
                return {"ok": False, "error": "請先購買並餵食【腸胃藥三天份】，才能開始計算三天康復療程喔！"}

            rem = max(0, char["gastro_days_remaining"] - 1)
            if rem == 0:
                new_expr = "expr_2_happy" if char_id == "xueling" else "expr_2_smile"
                conn.execute("""
                    UPDATE characters
                    SET health_status = 'healthy', gastro_course_active = 0,
                        gastro_days_remaining = 0, current_expr = ?
                    WHERE char_id = ?
                """, (new_expr, char_id))
                msg = f"🎉 {char['name']} 經過三天【腸胃藥三天份】療程，腸胃炎已完全康復！恢復活力 ✨"
                reply = "呼～連續吃了三天的腸胃藥，肚子終於完全不痛了！謝謝你照顧我 ✨"
            else:
                conn.execute("UPDATE characters SET gastro_days_remaining = ? WHERE char_id = ?", (rem, char_id))
                msg = f"⏳ {char['name']} 的【腸胃藥三天份】療程經過了 1 天，還剩下 {rem} 天即可完全康復！"
                reply = f"按時吃了今天的腸胃藥，感覺好一點了……再經過 {rem} 天就能徹底康復了！"

            self.add_log(conn, "醫療系統", msg)
            conn.commit()
        return {"ok": True, "message": msg, "reply": reply, "state": self.get_full_state()}

    def save_settings(self, settings_dict):
        with self.lock, self._connect() as conn:
            allowed = ("discord_webhook", "discord_bot_token", "discord_channel_id", "ai_provider", "ai_api_key")
            for k in allowed:
                if k in settings_dict:
                    conn.execute(f"UPDATE player_profile SET {k} = ? WHERE id = 1", (str(settings_dict[k]).strip(),))
            self.add_log(conn, "系統設定", "已儲存 Discord 連動與 AI 引擎設定。")
            conn.commit()
        return {"ok": True, "state": self.get_full_state()}
