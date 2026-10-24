#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create or Destroy — 單一檔案封包編譯器 (Single-File Bundle & Native EXE Generator)
解決「解壓縮後有很多散落檔案與資料夾」的問題：
將所有去背角色立繪 (PNG)、14 張誇張動漫漫符表情、23 個島民商店商品圖示 (SVG)、
遊戲資料 (JSON)、介面與邏輯 100% 壓縮封裝進「單一檔案」中，不再有任何散落的 assets/、core/、web/ 資料夾！
"""
import base64
import io
import json
import mimetypes
import os
import stat
import zipfile

BASE_DIR = "/home/angela/3d model"
RELEASES_DIR = os.path.join(BASE_DIR, "releases")
os.makedirs(RELEASES_DIR, exist_ok=True)


def collect_all_assets_as_data_uris():
    """Reads all PNG, SVG, and JSON files and returns a dictionary mapping relative paths to data URIs or JSON objects."""
    asset_map = {}
    for folder in ("assets", "gamedata"):
        folder_path = os.path.join(BASE_DIR, folder)
        for root, _, files in os.walk(folder_path):
            for fn in files:
                full_p = os.path.join(root, fn)
                rel_p = "/" + os.path.relpath(full_p, BASE_DIR).replace("\\", "/")
                if fn.endswith(".png"):
                    with open(full_p, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("ascii")
                    asset_map[rel_p] = f"data:image/png;base64,{b64}"
                elif fn.endswith(".svg"):
                    with open(full_p, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("ascii")
                    asset_map[rel_p] = f"data:image/svg+xml;base64,{b64}"
                elif fn.endswith(".json"):
                    with open(full_p, "r", encoding="utf-8") as f:
                        asset_map[rel_p] = json.load(f)
    return asset_map


def build_single_file_python_executable():
    """
    Packs the entire Python backend + all assets + web UI into ONE single executable file:
    `releases/CreateOrDestroy_SingleApp` (no external folders needed!).
    """
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in ("assets", "gamedata", "web", "core"):
            folder_path = os.path.join(BASE_DIR, folder)
            for root, _, files in os.walk(folder_path):
                if "__pycache__" in root:
                    continue
                for fn in files:
                    full_p = os.path.join(root, fn)
                    rel_p = os.path.relpath(full_p, BASE_DIR).replace("\\", "/")
                    zf.write(full_p, rel_p)

    b64_payload = base64.b64encode(mem_zip.getvalue()).decode("ascii")

    runner_code = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create or Destroy — 單一檔案封裝執行檔 (All-in-One Single Executable)
所有圖片素材、漫符表情、島民商店與系統均已 100% 封裝於本單一檔案內，無須任何外部素材資料夾！
"""
import base64
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
import zipfile

EMBEDDED_ZIP_B64 = "{b64_payload}"

def main():
    # Extract runtime assets to a hidden cache directory while keeping player save data in ./data/companion_save.db
    exe_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(tempfile.gettempdir(), "CreateOrDestroy_Runtime_v1")
    os.makedirs(cache_dir, exist_ok=True)

    raw_zip = base64.b64decode(EMBEDDED_ZIP_B64)
    with zipfile.ZipFile(io.BytesIO(raw_zip), "r") as zf:
        zf.extractall(cache_dir)

    # Check if a hot-update patch exists next to the executable (in updates/ or update_patch*.zip)
    for fn in sorted(os.listdir(exe_dir)):
        if fn.startswith("update_patch") and fn.endswith(".zip"):
            try:
                with zipfile.ZipFile(os.path.join(exe_dir, fn), "r") as uzf:
                    uzf.extractall(cache_dir)
                print(f"📦 已自動載入外部熱更新包: {{fn}}")
            except Exception:
                pass

    sys.path.insert(0, cache_dir)
    import core.database as db_mod
    # Store player save database right next to the executable so progress is permanently saved!
    save_dir = os.path.join(exe_dir, "save_data")
    os.makedirs(save_dir, exist_ok=True)
    db_mod.BASE_DIR = cache_dir
    db_mod.DATA_DIR = save_dir
    db_mod.BACKUP_DIR = os.path.join(save_dir, "backups")
    db_mod.GAMEDATA_DIR = os.path.join(cache_dir, "gamedata")
    db_mod.DB_PATH = os.path.join(save_dir, "companion_save.db")
    os.makedirs(db_mod.BACKUP_DIR, exist_ok=True)

    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import json, mimetypes, socket, urllib.parse
    from core.ai_engine import CompanionAIEngine
    from core.database import CompanionDB
    from core.discord_service import DiscordService
    from core.updater import HotUpdateManager

    DB = CompanionDB(db_mod.DB_PATH)
    AI_ENGINE = CompanionAIEngine(DB)
    DISCORD_SVC = DiscordService(DB)
    UPDATER = HotUpdateManager(DB)

    class SingleFileHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass
        def _send_json(self, payload, status=200):
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def _read_json_body(self):
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {{}}
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = urllib.parse.unquote(parsed.path)
            if path == "/api/state":
                return self._send_json({{"ok": True, "state": DB.get_full_state()}})
            if path in ("/", "/index.html"):
                path = "/web/index.html"
            full_path = os.path.join(cache_dir, path.lstrip("/"))
            if not os.path.isfile(full_path):
                self.send_error(404)
                return
            ctype, _ = mimetypes.guess_type(full_path)
            if full_path.endswith(".svg"): ctype = "image/svg+xml"
            elif full_path.endswith(".js"): ctype = "application/javascript; charset=utf-8"
            elif full_path.endswith(".css"): ctype = "text/css; charset=utf-8"
            elif full_path.endswith(".html"): ctype = "text/html; charset=utf-8"
            with open(full_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            body = self._read_json_body()
            if path == "/api/switch_char": return self._send_json(DB.set_active_character(body.get("char_id", "xueling")))
            if path == "/api/pose": return self._send_json(DB.set_character_pose(body.get("char_id", "xueling"), view=body.get("view"), expr=body.get("expr")))
            if path == "/api/minigame": return self._send_json(DB.toggle_minigame_mode(body.get("enabled")))
            if path == "/api/interact": return self._send_json(DB.interact(body.get("char_id", "xueling"), body.get("action", "pat")))
            if path == "/api/pomodoro": return self._send_json(DB.pomodoro_event(body.get("char_id", "xueling"), body.get("event_type", "start")))
            if path == "/api/shop/buy": return self._send_json(DB.buy_item(body.get("item_id"), quantity=body.get("quantity", 1), auto_use_char_id=body.get("auto_use_char_id")))
            if path == "/api/shop/use": return self._send_json(DB.use_item(body.get("char_id", "xueling"), body.get("item_id")))
            if path == "/api/gastro/advance": return self._send_json(DB.advance_gastro_day(body.get("char_id", "xueling")))
            if path == "/api/discord/command": return self._send_json(DISCORD_SVC.process_command(body.get("command", ""), username=body.get("username", "島民玩家")))
            if path == "/api/chat": return self._send_json(AI_ENGINE.generate_reply(body.get("char_id", "xueling"), body.get("message", "")))
            if path == "/api/settings": return self._send_json(DB.save_settings(body))
            return self._send_json({{"ok": False}}, status=404)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    url = f"http://127.0.0.1:{{port}}"
    server = ThreadingHTTPServer(("127.0.0.1", port), SingleFileHandler)
    print(f"⚡ Create or Destroy 單一執行檔已啟動: {{url}}")

    def open_win():
        for bin_name in ["google-chrome", "chromium", "microsoft-edge", r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"]:
            exe = shutil.which(bin_name) or (bin_name if os.path.exists(bin_name) else None)
            if exe:
                try:
                    subprocess.Popen([exe, f"--app={{url}}", "--window-size=550,840"])
                    return
                except Exception:
                    pass
        webbrowser.open(url)

    threading.Timer(0.5, open_win).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
'''
    out_single_py = os.path.join(RELEASES_DIR, "CreateOrDestroy_單一執行檔.pyw")
    with open(out_single_py, "w", encoding="utf-8") as f:
        f.write(runner_code)
    os.chmod(out_single_py, os.stat(out_single_py).st_mode | stat.S_IEXEC)
    return out_single_py


def build_zero_dependency_windows_exe_bundle():
    """
    Builds a 100% self-contained single-file bundle + Windows native .exe auto-compiler (`CreateOrDestroy_桌寵.exe` generator using built-in Windows .NET `csc.exe`)
    so that even on a Windows PC WITHOUT Python installed, clicking it immediately generates and launches a real native `CreateOrDestroy_桌寵.exe`!
    """
    asset_map = collect_all_assets_as_data_uris()

    with open(os.path.join(BASE_DIR, "web", "index.html"), "r", encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(BASE_DIR, "web", "style.css"), "r", encoding="utf-8") as f:
        css = f.read()
    with open(os.path.join(BASE_DIR, "web", "app.js"), "r", encoding="utf-8") as f:
        js = f.read()

    # Create an embedded offline backend adapter in JS so the single file works 100% standalone even without Python!
    offline_adapter_js = f"""
// ==========================================================================
// 100% Embedded Single-File Standalone Runtime (All PNGs, SVGs, JSONs & Local Save DB Built-In!)
// ==========================================================================
const EMBEDDED_ASSETS = {json.dumps(asset_map, ensure_ascii=False)};

(function() {{
  const origFetch = window.fetch.bind(window);
  const SAVE_KEY = "CreateOrDestroy_Standalone_Save_v1";

  function loadLocalDB() {{
    try {{
      const raw = localStorage.getItem(SAVE_KEY);
      if (raw) return JSON.parse(raw);
    }} catch(e) {{}}
    return {{
      profile: {{
        total_exp: 100.0, available_exp: 100.0, coins: 60, streak_days: 1,
        last_checkin_date: "", simulated_day_offset: 0, mini_game_enabled: 1,
        active_character: "xueling", discord_webhook: "", ai_provider: "offline", ai_api_key: ""
      }},
      characters: {{
        xueling: {{ char_id: "xueling", name: "雪靈 (Xueling)", computed_level: 2, affection: 50, recovery_exp: 100, wisdom_exp: 0, pomodoro_count: 0, stamina: 100, hunger: 20, dirtiness: 15, fatigue: 15, health_status: "healthy", gastro_course_active: 0, gastro_days_remaining: 0, current_view: "main_fullbody", current_expr: "expr_1_normal" }},
        lingfeng: {{ char_id: "lingfeng", name: "凌風 (Ling Feng)", computed_level: 2, affection: 50, recovery_exp: 100, wisdom_exp: 0, pomodoro_count: 0, stamina: 100, hunger: 20, dirtiness: 15, fatigue: 15, health_status: "healthy", gastro_course_active: 0, gastro_days_remaining: 0, current_view: "main_fullbody", current_expr: "expr_1_normal" }}
      }},
      inventory: {{}},
      unlocked_achievements: {{}},
      logs: [{{ created_at: new Date().toTimeString().slice(0,8), source: "系統", message: "⚡ 歡迎啟動 Create or Destroy 獨立桌寵正式版！" }}]
    }};
  }}

  function saveLocalDB(db) {{
    for (const cid of ["xueling", "lingfeng"]) {{
      const c = db.characters[cid];
      c.computed_level = Math.max(1, 1 + Math.floor((db.profile.total_exp + Math.max(0, c.recovery_exp) + c.wisdom_exp * 2) / 100));
    }}
    db.profile.sickness_unlocked = db.profile.streak_days >= 7;
    try {{ localStorage.setItem(SAVE_KEY, JSON.stringify(db)); }} catch(e) {{}}
  }}

  function addLog(db, src, msg) {{
    db.logs.unshift({{ created_at: new Date().toTimeString().slice(0,8), source: src, message: msg }});
    if (db.logs.length > 30) db.logs.length = 30;
  }}

  function buildFullState(db) {{
    saveLocalDB(db);
    return {{
      profile: db.profile,
      characters: db.characters,
      inventory: db.inventory,
      unlocked_achievements: db.unlocked_achievements,
      shop_catalog: EMBEDDED_ASSETS["/gamedata/shop_catalog.json"],
      achievements_catalog: EMBEDDED_ASSETS["/gamedata/achievements.json"],
      version_info: EMBEDDED_ASSETS["/gamedata/version.json"],
      logs: db.logs
    }};
  }}

  // Intercept image src assignments to use embedded Base64 PNG/SVG data URIs when running standalone
  const origSetAttr = Element.prototype.setAttribute;
  Object.defineProperty(HTMLImageElement.prototype, "src", {{
    set(val) {{
      if (typeof val === "string") {{
        const clean = val.replace(/^https?:\\/\\/[^/]+/, "");
        if (EMBEDDED_ASSETS[clean]) {{
          this.setAttribute("src", EMBEDDED_ASSETS[clean]);
          return;
        }}
      }}
      this.setAttribute("src", val);
    }},
    get() {{ return this.getAttribute("src"); }}
  }});

  window.addEventListener("DOMContentLoaded", () => {{
    document.querySelectorAll("img").forEach(img => {{
      const s = img.getAttribute("src");
      if (s && EMBEDDED_ASSETS[s]) img.setAttribute("src", EMBEDDED_ASSETS[s]);
    }});
  }});

  window.fetch = async function(url, options = {{}}) {{
    if (window.location.protocol !== "file:") {{
      try {{ return await origFetch(url, options); }} catch(e) {{}}
    }}
    const path = String(url).split("?")[0];
    if (path === "/assets/asset_manifest.json") {{
      return new Response(JSON.stringify(EMBEDDED_ASSETS["/assets/asset_manifest.json"]));
    }}
    const db = loadLocalDB();
    const body = options.body ? JSON.parse(options.body) : {{}};
    const diag = EMBEDDED_ASSETS["/gamedata/dialogues.json"] || {{}};

    if (path === "/api/state") {{
      return new Response(JSON.stringify({{ ok: true, state: buildFullState(db) }}));
    }}
    if (path === "/api/switch_char") {{
      db.profile.active_character = body.char_id;
      addLog(db, "系統", "切換桌寵角色為：" + db.characters[body.char_id].name);
      return new Response(JSON.stringify({{ ok: true, state: buildFullState(db) }}));
    }}
    if (path === "/api/pose") {{
      const c = db.characters[body.char_id];
      if (body.view) c.current_view = body.view;
      if (body.expr) c.current_expr = body.expr;
      return new Response(JSON.stringify({{ ok: true, state: buildFullState(db) }}));
    }}
    if (path === "/api/minigame") {{
      db.profile.mini_game_enabled = db.profile.mini_game_enabled ? 0 : 1;
      return new Response(JSON.stringify({{ ok: true, mini_game_enabled: Boolean(db.profile.mini_game_enabled), state: buildFullState(db) }}));
    }}
    if (path === "/api/interact") {{
      const c = db.characters[body.char_id];
      const act = body.action;
      let reply = "好感度提升 ✨";
      if (act === "pat") {{ c.affection += 3; c.current_expr = "expr_5_shy"; reply = "嘿嘿，被摸頭好開心 ✨ 好感度 +3！"; }}
      else if (act === "poke") {{ c.current_expr = "expr_3_angry"; reply = "喂！不要亂戳我的臉啦 💢"; }}
      else if (act === "bath") {{ c.dirtiness = 0; c.affection += 5; c.current_expr = body.char_id === "xueling" ? "expr_2_happy" : "expr_2_smile"; reply = "洗完香噴噴的泡泡浴了！髒污值歸零 ✨"; }}
      else if (act === "rest") {{ c.stamina = Math.min(100, c.stamina + 35); c.fatigue = Math.max(0, c.fatigue - 45); c.current_expr = "expr_1_normal"; reply = "休息充電完成！體力恢復 +35 ✨"; }}
      else if (act === "racing_drive") {{ c.current_view = c.current_view === "racing_scene" ? "main_fullbody" : "racing_scene"; reply = "引擎啟動！帶你體驗 BMW 賽道極限速度 🏎️💨"; }}
      else if (act === "trigger_cold_test") {{ c.health_status = "cold"; c.current_expr = "expr_7_sick"; reply = "哈啾……頭好暈，好像感冒發燒了 🤒"; }}
      addLog(db, c.name, reply);
      return new Response(JSON.stringify({{ ok: true, reply, action: act, state: buildFullState(db) }}));
    }}
    if (path === "/api/pomodoro") {{
      const c = db.characters[body.char_id];
      if (body.event_type === "start") {{
        if (c.stamina < 20) return new Response(JSON.stringify({{ ok: false, error: "體力不足 20 點！請先點擊休息充電或餵食補充體力喔！" }}));
        c.current_expr = "expr_6_focused";
        return new Response(JSON.stringify({{ ok: true, reply: "⏱️ 30分鐘番茄鐘啟動！進入極限專注狀態 💡", state: buildFullState(db) }}));
      }}
      if (body.event_type === "abort") {{
        c.current_expr = "expr_1_normal";
        return new Response(JSON.stringify({{ ok: true, reply: "番茄鐘已中途停止，未獲得智慧經驗值。", state: buildFullState(db) }}));
      }}
      if (body.event_type === "complete") {{
        c.wisdom_exp += 15; c.stamina = Math.max(0, c.stamina - 20); c.pomodoro_count += 1;
        c.current_expr = body.char_id === "xueling" ? "expr_2_happy" : "expr_2_smile";
        const unlocked = [];
        for (const ach of (EMBEDDED_ASSETS["/gamedata/achievements.json"].wisdom_achievements || [])) {{
          if (c.wisdom_exp >= ach.required_wisdom && !db.unlocked_achievements[ach.id]) {{
            db.unlocked_achievements[ach.id] = "已解鎖";
            db.profile.coins += (ach.reward_coins || 15);
            unlocked.push(`🏆 解鎖學習成就【${{ach.title}}】(+${{ach.reward_coins}} 金幣)！`);
          }}
        }}
        addLog(db, "番茄鐘", `🎓 完成 30 分鐘番茄鐘！智慧經驗 +15（累計 ${{c.wisdom_exp}}），體力 -20（剩餘 ${{c.stamina}}）`);
        return new Response(JSON.stringify({{ ok: true, reply: "🎓 完成 30 分鐘專注學習！獲得 +15 智慧經驗值、消耗 -20 體力值！", unlocked_achievements: unlocked, state: buildFullState(db) }}));
      }}
    }}
    if (path === "/api/shop/buy" || path === "/api/shop/use") {{
      const items = EMBEDDED_ASSETS["/gamedata/shop_catalog.json"].items;
      const it = items.find(x => x.id === body.item_id);
      if (path === "/api/shop/buy") {{
        if (db.profile.coins < it.price) return new Response(JSON.stringify({{ ok: false, error: `島民金幣不足！需要 ${{it.price}} 金幣。` }}));
        db.profile.coins -= it.price;
        db.inventory[it.id] = (db.inventory[it.id] || 0) + 1;
        if (!body.auto_use_char_id) {{
          return new Response(JSON.stringify({{ ok: true, message: `🛒 已購買 ${{it.name}}！`, state: buildFullState(db) }}));
        }}
        body.char_id = body.auto_use_char_id;
      }}
      if ((db.inventory[it.id] || 0) <= 0) return new Response(JSON.stringify({{ ok: false, error: "背包沒有此商品！" }}));
      db.inventory[it.id] -= 1;
      const c = db.characters[body.char_id];
      c.recovery_exp += it.recovery;
      c.hunger = Math.max(0, Math.min(100, c.hunger - (it.hunger_relief || 0)));
      c.stamina = Math.max(0, Math.min(100, c.stamina + (it.stamina_relief || 0)));
      let reply = `使用了 ${{it.emoji}} ${{it.name}}（${{it.effect_label}}）！`;
      if (it.triggers_gastro) {{ c.health_status = "gastroenteritis"; c.gastro_days_remaining = 3; c.gastro_course_active = 0; c.current_expr = "expr_7_sick"; reply = "🤢 肚子好痛！誤喝不知放多少天的飲料觸發【腸胃炎】了！快買【腸胃藥三天份】救我！"; }}
      else if (it.cures_cold) {{ c.health_status = "healthy"; c.current_expr = "expr_1_normal"; reply = "💊 服用感冒藥後退燒康復了 ✨"; }}
      else if (it.cures_gastro_3d) {{ c.gastro_course_active = 1; if (c.gastro_days_remaining <= 0) c.gastro_days_remaining = 3; reply = `🏥 已服用【腸胃藥三天份】（+100 恢復經驗值），經過 ${{c.gastro_days_remaining}} 天即可完全康復！`; }}
      addLog(db, "島民商店", reply);
      return new Response(JSON.stringify({{ ok: true, message: reply, reply, state: buildFullState(db) }}));
    }}
    if (path === "/api/gastro/advance") {{
      const c = db.characters[body.char_id];
      if (!c.gastro_course_active) return new Response(JSON.stringify({{ ok: false, error: "請先購買並服用【腸胃藥三天份】！" }}));
      c.gastro_days_remaining = Math.max(0, c.gastro_days_remaining - 1);
      let msg = `⏳ 腸胃藥療程經過 1 天，還剩 ${{c.gastro_days_remaining}} 天康復！`;
      if (c.gastro_days_remaining === 0) {{ c.health_status = "healthy"; c.gastro_course_active = 0; c.current_expr = "expr_1_normal"; msg = "🎉 經過三天腸胃藥療程，腸胃炎已完全康復！"; }}
      return new Response(JSON.stringify({{ ok: true, message: msg, reply: msg, state: buildFullState(db) }}));
    }}
    if (path === "/api/discord/command") {{
      const cmd = (body.command || "").trim().toLowerCase();
      if (cmd.startsWith("/checkin") || cmd.startsWith("!打卡")) {{
        db.profile.total_exp += 20; db.profile.available_exp += 20; db.profile.streak_days += 1;
        const msg = `✅ 【Discord 每日打卡】獲得 +20 EXP！（連續 ${{db.profile.streak_days}} 天）`;
        addLog(db, "Discord", msg);
        return new Response(JSON.stringify({{ ok: true, message: msg, state: buildFullState(db) }}));
      }}
      if (cmd.startsWith("/roll") || cmd.startsWith("!骰子")) {{
        if (cmd.includes("multi") || cmd.includes("多人")) {{
          const rolls = [
            {{ name: "島民玩家", roll: Math.floor(Math.random()*6)+7, is_player: true }},
            {{ name: "雪靈(Bot)", roll: Math.floor(Math.random()*10)+2, is_player: false }},
            {{ name: "凌風(Bot)", roll: Math.floor(Math.random()*10)+2, is_player: false }}
          ];
          const maxR = Math.max(...rolls.map(r => r.roll));
          rolls.forEach(r => r.is_winner = (r.roll === maxR));
          const won = rolls[0].is_winner;
          if (won) {{ db.profile.total_exp += 5; db.profile.available_exp += 5; }}
          const msg = won ? `🎲🏆 多人同輪骰子最高點（${{maxR}}點）！獲得 +5 EXP！` : `🎲 多人同輪骰子最高點為 ${{maxR}} 點！`;
          return new Response(JSON.stringify({{ ok: true, mode: "multi", rolls, message: msg, state: buildFullState(db) }}));
        }} else {{
          const rv = Math.floor(Math.random()*6)+1;
          db.profile.total_exp += 1; db.profile.available_exp += 1;
          const msg = `🎲 單人骰骰子擲出 ${{rv}} 點！獲得 +1 EXP！`;
          return new Response(JSON.stringify({{ ok: true, mode: "solo", rolls: [{{ name: "島民玩家", roll: rv, is_winner: true }}], exp_gain: 1, message: msg, state: buildFullState(db) }}));
        }}
      }}
      if (cmd.startsWith("/exchange") || cmd.startsWith("!兌換")) {{
        if (db.profile.available_exp < 50) return new Response(JSON.stringify({{ ok: false, error: "可兌換 EXP 不足 50 點！" }}));
        db.profile.available_exp -= 50; db.profile.coins += 25;
        const msg = "🪙 消耗 50 EXP 成功兌換 +25 枚島民商店金幣！";
        return new Response(JSON.stringify({{ ok: true, message: msg, state: buildFullState(db) }}));
      }}
      db.profile.total_exp = Number((db.profile.total_exp + 0.5).toFixed(1));
      db.profile.available_exp = Number((db.profile.available_exp + 0.5).toFixed(1));
      return new Response(JSON.stringify({{ ok: true, message: "💬 Discord 頻道留言獲得 +0.5 EXP！", state: buildFullState(db) }}));
    }}
    if (path === "/api/chat") {{
      const c = db.characters[body.char_id];
      const reply = `收到你的訊息：「${{body.message}}」✨ 我會一直在桌面上陪你專注學習！（目前體力 ${{c.stamina}}、智慧 ${{c.wisdom_exp}} 點）`;
      return new Response(JSON.stringify({{ ok: true, char_id: body.char_id, char_name: c.name, reply, state: buildFullState(db) }}));
    }}
    return new Response(JSON.stringify({{ ok: true, state: buildFullState(db) }}));
  }};
}})();
"""

    # Inline CSS, Embedded Assets Adapter, and JS into ONE standalone file
    standalone_html = html.replace(
        '<link rel="stylesheet" href="/web/style.css" />',
        f"<style>\n{css}\n</style>",
    ).replace(
        '<script src="/web/app.js"></script>',
        f"<script>\n{offline_adapter_js}\n\n{js}\n</script>",
    )

    # Save standalone core file
    standalone_core_path = os.path.join(RELEASES_DIR, "CreateOrDestroy_桌寵單一執行包.html")
    with open(standalone_core_path, "w", encoding="utf-8") as f:
        f.write(standalone_html)

    # Create a Windows script that compiles a real native `CreateOrDestroy_桌寵.exe` using Windows built-in .NET `csc.exe` and runs it!
    win_exe_builder_bat = r"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"

if not exist "CreateOrDestroy_桌寵.exe" (
    if exist "%CSC%" (
        echo ⚡ 正在使用 Windows 內建 .NET 編譯器為您生成單一執行檔 CreateOrDestroy_桌寵.exe ...
        > "_pet_launcher.cs" (
            echo using System;
            echo using System.Diagnostics;
            echo using System.IO;
            echo class Program {
            echo     [STAThread]
            echo     static void Main() {
            echo         string dir = AppDomain.CurrentDomain.BaseDirectory;
            echo         string core = Path.Combine(dir, "CreateOrDestroy_桌寵單一執行包.html");
            echo         string url = new Uri(core).AbsoluteUri;
            echo         string[] edges = new string[] {
            echo             @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            echo             @"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            echo             @"C:\Program Files\Google\Chrome\Application\chrome.exe"
            echo         };
            echo         foreach (string e in edges) {
            echo             if (File.Exists(e)) {
            echo                 Process.Start(e, "--app=\"" + url + "\" --window-size=540,840");
            echo                 return;
            echo             }
            echo         }
            echo         Process.Start(core);
            echo     }
            echo }
        )
        "%CSC%" /nologo /target:winexe /out:"CreateOrDestroy_桌寵.exe" "_pet_launcher.cs" >nul 2>&1
        del /q "_pet_launcher.cs" >nul 2>&1
    )
)

if exist "CreateOrDestroy_桌寵.exe" (
    start "" "CreateOrDestroy_桌寵.exe"
) else (
    start msedge "--app=%~dp0CreateOrDestroy_桌寵單一執行包.html" --window-size=540,840 2>nul || start "" "%~dp0CreateOrDestroy_桌寵單一執行包.html"
)
"""

    # Pack into `releases/CreateOrDestroy_單一執行版_v1.0.0.zip` — NO loose folders!
    clean_zip_path = os.path.join(RELEASES_DIR, "CreateOrDestroy_單一執行版_v1.0.0.zip")
    with zipfile.ZipFile(clean_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("啟動桌寵_點我直接執行.bat", win_exe_builder_bat)
        zf.write(standalone_core_path, "CreateOrDestroy_桌寵單一執行包.html")

    return standalone_core_path, clean_zip_path


if __name__ == "__main__":
    p1 = build_single_file_python_executable()
    p2, p3 = build_zero_dependency_windows_exe_bundle()
    print(f"✅ 1. Python 單一封裝執行檔: {p1} ({round(os.path.getsize(p1)/1024/1024, 2)} MB)")
    print(f"✅ 2. 100% 內嵌免安裝單一核心包: {p2} ({round(os.path.getsize(p2)/1024/1024, 2)} MB)")
    print(f"✅ 3. 乾淨無資料夾發佈包: {p3} ({round(os.path.getsize(p3)/1024/1024, 2)} MB)")
