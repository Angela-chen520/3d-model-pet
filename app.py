#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create or Destroy — 雪靈 (Xueling) & 凌風 (Ling Feng) AI 桌寵養成系統主程式
100% 免額外安裝解碼器（純 Python 標準庫驅動 + 原生桌面 App 視窗啟動器）。
"""
import argparse
import json
import mimetypes
import os
import shutil
import socket
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.ai_engine import CompanionAIEngine
from core.database import CompanionDB
from core.discord_service import DiscordService
from core.updater import HotUpdateManager

DB = CompanionDB()
AI_ENGINE = CompanionAIEngine(DB)
DISCORD_SVC = DiscordService(DB)
UPDATER = HotUpdateManager(DB)


class CompanionHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet standard HTTP logs to keep console clean
        pass

    def _send_json(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        if path == "/api/state":
            return self._send_json({"ok": True, "state": DB.get_full_state()})

        if path in ("/download", "/installer.exe", "/CreateOrDestroy_Pet_Installer.exe"):
            path = "/releases/CreateOrDestroy_桌寵_Installer.exe"

        if path in ("/", "/index.html"):
            path = "/web/index.html"

        # Serve static files safely from BASE_DIR
        rel = urllib.parse.unquote(path.lstrip("/"))
        if ".." in rel.split("/"):
            self.send_error(403, "Forbidden")
            return

        full_path = os.path.join(BASE_DIR, rel)
        if not os.path.isfile(full_path):
            self.send_error(404, "Not Found")
            return

        ctype, _ = mimetypes.guess_type(full_path)
        if full_path.endswith(".svg"):
            ctype = "image/svg+xml"
        elif full_path.endswith(".js"):
            ctype = "application/javascript; charset=utf-8"
        elif full_path.endswith(".css"):
            ctype = "text/css; charset=utf-8"
        elif full_path.endswith(".html"):
            ctype = "text/html; charset=utf-8"
        elif full_path.endswith(".exe") or full_path.endswith(".zip"):
            ctype = "application/octet-stream"

        with open(full_path, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        if full_path.endswith(".exe"):
            self.send_header("Content-Disposition", 'attachment; filename="CreateOrDestroy_Pet_Installer.exe"')
        elif full_path.endswith(".zip"):
            self.send_header("Content-Disposition", 'attachment; filename="CreateOrDestroy_NativePet_v2.zip"')
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            if path == "/api/updater/apply":
                length = int(self.headers.get("Content-Length", 0))
                zip_bytes = self.rfile.read(length) if length > 0 else b""
                qs = urllib.parse.parse_qs(parsed.query)
                fname = qs.get("filename", ["update_patch.zip"])[0]
                return self._send_json(UPDATER.apply_patch_bytes(zip_bytes, patch_name=fname))

            body = self._read_json_body()

            if path == "/api/switch_char":
                return self._send_json(DB.set_active_character(body.get("char_id", "xueling")))

            if path == "/api/pose":
                return self._send_json(
                    DB.set_character_pose(
                        body.get("char_id", "xueling"),
                        view=body.get("view"),
                        expr=body.get("expr"),
                    )
                )

            if path == "/api/minigame":
                return self._send_json(DB.toggle_minigame_mode(body.get("enabled")))

            if path == "/api/interact":
                return self._send_json(
                    DB.interact(body.get("char_id", "xueling"), body.get("action", "pat"))
                )

            if path == "/api/pomodoro":
                res = DB.pomodoro_event(body.get("char_id", "xueling"), body.get("event_type", "start"))
                if res.get("ok") and body.get("event_type") == "complete":
                    DISCORD_SVC.send_webhook_async(
                        "🎓 30分鐘番茄鐘學習完成 (+15 智慧經驗值 / -20 體力值)",
                        res.get("reply", ""),
                        0x9D4EDD,
                    )
                return self._send_json(res)

            if path == "/api/shop/buy":
                return self._send_json(
                    DB.buy_item(
                        body.get("item_id"),
                        quantity=body.get("quantity", 1),
                        auto_use_char_id=body.get("auto_use_char_id"),
                    )
                )

            if path == "/api/shop/use":
                return self._send_json(
                    DB.use_item(body.get("char_id", "xueling"), body.get("item_id"))
                )

            if path == "/api/gastro/advance":
                return self._send_json(DB.advance_gastro_day(body.get("char_id", "xueling")))

            if path == "/api/discord/command":
                return self._send_json(
                    DISCORD_SVC.process_command(
                        body.get("command", ""),
                        username=body.get("username", "島民玩家"),
                    )
                )

            if path == "/api/chat":
                return self._send_json(
                    AI_ENGINE.generate_reply(
                        body.get("char_id", "xueling"),
                        body.get("message", ""),
                    )
                )

            if path == "/api/settings":
                return self._send_json(DB.save_settings(body))

            if path == "/api/updater/create":
                return self._send_json(
                    UPDATER.create_sample_patch(
                        new_version=body.get("new_version", "1.0.1"),
                        patch_notes=body.get("patch_notes", "熱更新測試"),
                    )
                )

            return self._send_json({"ok": False, "error": f"未知的 API 路徑: {path}"}, status=404)
        except Exception as e:
            return self._send_json({"ok": False, "error": str(e)}, status=500)


def find_free_port(preferred=8765):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def launch_desktop_window(url):
    """Tries to open a clean native-style --app desktop window first, falling back to default browser."""
    candidates = [
        "google-chrome",
        "chromium",
        "chromium-browser",
        "microsoft-edge",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    for bin_name in candidates:
        exe = shutil.which(bin_name) or (bin_name if os.path.exists(bin_name) else None)
        if exe:
            try:
                subprocess.Popen(
                    [exe, f"--app={url}", "--window-size=550,840"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except Exception:
                pass
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="Create or Destroy AI Desktop Companion Server")
    parser.add_argument("--port", type=int, default=8765, help="Port number (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Run server without opening browser window")
    args = parser.parse_args()

    port = find_free_port(args.port)
    url = f"http://127.0.0.1:{port}"
    server = ThreadingHTTPServer(("0.0.0.0", port), CompanionHTTPHandler)

    print("=" * 68)
    print("⚡ Create or Destroy — 雪靈 (Xueling) & 凌風 (Ling Feng) AI 桌寵養成系統")
    print(f"🌐 本地端桌寵服務已啟動：{url}")
    print("💾 玩家獨立存檔路徑：data/companion_save.db（熱更新自動保護）")
    print("=" * 68)

    if not args.no_browser:
        threading.Timer(0.6, lambda: launch_desktop_window(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 正在安全儲存並關閉 Create or Destroy 桌寵系統...")
        server.server_close()


if __name__ == "__main__":
    main()
