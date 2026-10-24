#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create or Destroy — AI Persona Dialogue Engine (雪靈 Xueling & 凌風 Ling Feng)
100% Zero external dependencies. Supports:
1. Built-in Context-Aware Persona Engine (Offline, zero-latency, reads live character stats & keywords)
2. Optional Google Gemini Free Tier API (via standard library urllib.request)
3. Optional Local Ollama LLM (http://127.0.0.1:11434/api/generate)
"""
import json
import os
import random
import urllib.error
import urllib.request

from core.database import load_json_gamedata


class CompanionAIEngine:
    def __init__(self, db):
        self.db = db

    def generate_reply(self, char_id, user_message):
        user_message = (user_message or "").strip()
        state = self.db.get_full_state()
        prof = state["profile"]
        char = state["characters"].get(char_id, state["characters"]["xueling"])
        dialogues = load_json_gamedata("dialogues.json", {})
        c_diag = dialogues.get(char_id, dialogues.get("xueling", {}))

        provider = prof.get("ai_provider", "offline")
        api_key = prof.get("ai_api_key", "").strip()

        # Determine appropriate expression based on message & status
        suggested_expr = self._detect_expression(char_id, char, user_message)

        reply_text = None
        if provider == "gemini" and api_key:
            reply_text = self._call_gemini_api(c_diag, char, prof, user_message, api_key)
        elif provider == "ollama":
            reply_text = self._call_ollama_api(c_diag, char, prof, user_message)

        if not reply_text:
            reply_text = self._offline_persona_reply(char_id, c_diag, char, prof, user_message)

        # Update character expression & log the chat
        self.db.set_character_pose(char_id, expr=suggested_expr)
        return {
            "ok": True,
            "char_id": char_id,
            "char_name": char["name"],
            "user_message": user_message,
            "reply": reply_text,
            "expression": suggested_expr,
            "state": self.db.get_full_state(),
        }

    def _detect_expression(self, char_id, char, msg):
        if char["health_status"] in ("cold", "gastroenteritis"):
            return "expr_7_sick"
        msg_low = msg.lower()
        if any(k in msg_low for k in ("喜歡", "愛", "可愛", "帥", "抱", "親", "漂亮", "嫁", "約會", "love")):
            return "expr_5_shy"
        if any(k in msg_low for k in ("笨", "討厭", "醜", "廢", "生氣", "滾", "戳", "怒")):
            return "expr_3_angry"
        if any(k in msg_low for k in ("驚", "什麼", "居然", "天啊", "嚇", "中獎", "?!", "？！")):
            return "expr_4_surprised"
        if any(k in msg_low for k in ("番茄鐘", "學習", "讀書", "工作", "專注", "智慧", "寫程式", "考試")):
            return "expr_6_focused"
        if any(k in msg_low for k in ("生病", "感冒", "腸胃炎", "痛", "累", "餓", "不舒服")):
            return "expr_7_sick"
        return "expr_2_happy" if char_id == "xueling" else "expr_2_smile"

    def _offline_persona_reply(self, char_id, c_diag, char, prof, msg):
        # 1. Check if character has urgent physical condition
        if char["health_status"] == "gastroenteritis":
            if any(k in msg for k in ("藥", "腸胃", "好點", "痛", "生病", "怎麼了")):
                return random.choice(c_diag.get("interactions", {}).get("sick_gastro", ["肚子好痛……快買腸胃藥三天份救我 🤢"]))
        elif char["health_status"] == "cold":
            if any(k in msg for k in ("藥", "感冒", "發燒", "生病", "怎麼了")):
                return random.choice(c_diag.get("interactions", {}).get("sick_cold", ["頭好暈……需要吃感冒藥 🤒"]))

        # 2. Match keyword rules from dialogues.json
        for kw_group, response in c_diag.get("keywords", {}).items():
            keywords = [k.strip() for k in kw_group.split("|") if k.strip()]
            if any(k in msg for k in keywords):
                return response

        # 3. Context-aware dynamic responses
        if any(k in msg for k in ("狀態", "報告", "體力", "數值", "目前")):
            health_map = {"healthy": "健康良好 ✨", "cold": "感冒發燒中 🤒", "gastroenteritis": f"腸胃炎治療中（剩 {char['gastro_days_remaining']} 天）🤢"}
            h_str = health_map.get(char["health_status"], "健康")
            return (
                f"向你報告目前狀態！📊 等級 Lv.{char['computed_level']}｜"
                f"體力：{char['stamina']}/100｜智慧經驗：{char['wisdom_exp']} 點｜"
                f"恢復經驗：{char['recovery_exp']}｜飢餓：{char['hunger']}%｜髒污：{char['dirtiness']}%｜"
                f"健康：{h_str}｜島民金幣：{prof['coins']} 枚！"
            )

        if any(k in msg for k in ("早安", "午安", "晚安", "你好", "嗨", "哈囉", "hi", "hello")):
            return random.choice(c_diag.get("greetings", ["嗨！今天要一起開啟番茄鐘還是去島民商店逛逛呢？✨"]))

        # 4. General affectionate / character-flavored reply
        if char_id == "xueling":
            pool = [
                f"收到！「{msg}」～雪靈會一直在桌面上陪著你喔！需要開啟 30 分鐘番茄鐘一起專注學習嗎？✨",
                f"嘻嘻，聽你說話心情都變好了！（目前好感度 {char['affection']} ❤️）要不要去 Discord 骰個骰子賺經驗值？🎲",
                f"沒問題！對了，現在我們已經累積了 {char['wisdom_exp']} 點智慧經驗值，繼續加油解鎖全部學習成就吧！💡",
            ]
        else:
            pool = [
                f"了解。「{msg}」——交給我吧。累的時候記得讓我休息充電，或者開 BMW M4 去兜風。🏎️",
                f"嗯，我一直在聽（好感度 {char['affection']} ❤️）。要是想提升效率，隨時啟動 30 分鐘番茄鐘，我陪你衝刺。💡",
                f"放心，不管是專注學習還是 Discord 多人骰子對決，我都會挺你到底。✨",
            ]
        return random.choice(pool)

    def _call_gemini_api(self, c_diag, char, prof, user_message, api_key):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            sys_prompt = (
                f"{c_diag.get('persona', '')}\n"
                f"目前角色狀態：體力 {char['stamina']}/100、智慧經驗 {char['wisdom_exp']}、飢餓 {char['hunger']}%、"
                f"健康狀態 {char['health_status']}、好感度 {char['affection']}。請用繁體中文、不超過 70 字簡短生動地回應玩家。"
            )
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": f"【系統設定】{sys_prompt}\n\n【玩家對你說】{user_message}"}]}
                ]
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            return None

    def _call_ollama_api(self, c_diag, char, prof, user_message):
        try:
            url = "http://127.0.0.1:11434/api/generate"
            prompt = f"{c_diag.get('persona', '')}\n請用繁體中文簡短回覆玩家：{user_message}"
            payload = {"model": "qwen2.5:7b", "prompt": prompt, "stream": False}
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "").strip()
        except Exception:
            return None
