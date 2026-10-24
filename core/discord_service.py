#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create or Destroy — Discord Integration & Command Processor
Zero external dependencies (uses standard library urllib.request & json).
Supports:
- Real Discord Webhook push notifications (embeds + character status updates)
- Command parser for `/checkin` (!打卡), `/roll solo` (!單人骰子), `/roll multi` (!多人骰子),
  `/exchange` (!兌換金幣), `/status` (!狀態), and regular channel messages (+0.5 EXP)
"""
import json
import threading
import urllib.error
import urllib.request


class DiscordService:
    def __init__(self, db):
        self.db = db

    def send_webhook_async(self, title, description, color=0x00F5D4):
        state = self.db.get_full_state()
        webhook_url = state["profile"].get("discord_webhook", "").strip()
        if not webhook_url or not webhook_url.startswith("http"):
            return False

        active_char_id = state["profile"].get("active_character", "xueling")
        char = state["characters"].get(active_char_id, {})

        def _worker():
            try:
                payload = {
                    "username": f"Create or Destroy｜{char.get('name', 'AI 桌寵')}",
                    "embeds": [
                        {
                            "title": title,
                            "description": description,
                            "color": color,
                            "fields": [
                                {
                                    "name": "📊 玩家經驗與金幣",
                                    "value": (
                                        f"累計 EXP：`{state['profile']['total_exp']}`｜"
                                        f"可兌換 EXP：`{state['profile']['available_exp']}`｜"
                                        f"🪙 島民金幣：`{state['profile']['coins']}`"
                                    ),
                                    "inline": False,
                                },
                                {
                                    "name": f"🎭 {char.get('name', '')} 狀態",
                                    "value": (
                                        f"Lv.`{char.get('computed_level', 1)}`｜"
                                        f"體力：`{char.get('stamina', 100)}/100`｜"
                                        f"智慧經驗：`{char.get('wisdom_exp', 0)}`｜"
                                        f"恢復經驗：`{char.get('recovery_exp', 100)}`"
                                    ),
                                    "inline": False,
                                },
                            ],
                            "footer": {"text": "Create or Destroy AI 桌寵養成系統 • 即時同步"},
                        }
                    ],
                }
                req = urllib.request.Request(
                    webhook_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "CreateOrDestroy-Companion/1.0"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as _:
                    pass
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()
        return True

    def process_command(self, raw_text, username="島民玩家"):
        """
        Parses and executes a Discord command or channel message:
        - /checkin, !打卡, !checkin -> Daily check-in (+20 EXP)
        - /roll multi, !多人骰子, !骰子 多人 -> Multiplayer same-round dice (highest roll gets +5 EXP)
        - /roll, /roll solo, !單人骰子, !骰子 -> Solo dice (+1 EXP)
        - /exchange [batches], !兌換 [組數] -> Exchange 50 EXP for 25 Island Shop Coins
        - Any other text -> Channel message (+0.5 EXP)
        """
        text = (raw_text or "").strip()
        if not text:
            return {"ok": False, "error": "請輸入 Discord 指令或留言內容"}

        low = text.lower()

        if low.startswith(("/checkin", "!checkin", "!打卡", "/打卡")):
            force_next = "next" in low or "隔日" in low or "推進" in low
            res = self.db.discord_checkin(username=username, force_next_day=force_next)
            if res.get("ok"):
                self.send_webhook_async("📅 Discord 每日打卡成功 (+20 EXP)", res["message"], 0x00F5D4)
            return res

        if low.startswith(("/roll", "!roll", "!骰子", "/骰子", "!多人骰子", "!單人骰子")):
            is_multi = any(k in low for k in ("multi", "多人", "同輪", "party", "all"))
            mode = "multi" if is_multi else "solo"
            res = self.db.discord_roll_dice(mode=mode, player_name=username)
            if res.get("ok"):
                title = "🎲🏆 Discord 多人同輪骰子對決 (+5 EXP)" if mode == "multi" else "🎲 Discord 單人骰骰子 (+1 EXP)"
                self.send_webhook_async(title, res["message"], 0xFFBE0B)
            return res

        if low.startswith(("/exchange", "!exchange", "!兌換", "/兌換")):
            parts = text.split()
            batches = 1
            if len(parts) > 1 and parts[1].isdigit():
                batches = int(parts[1])
            res = self.db.exchange_exp_for_coins(batches=batches)
            if res.get("ok"):
                self.send_webhook_async("🪙 Create or Destroy 島民商店金幣兌換", res["message"], 0xFF007F)
            return res

        # Otherwise treat as a regular Discord channel message (+0.5 EXP)
        res = self.db.discord_message_exp(username=username, content=text)
        if res.get("ok"):
            self.send_webhook_async("💬 Discord 頻道互動留言 (+0.5 EXP)", res["message"], 0x3A86FF)
        return res
