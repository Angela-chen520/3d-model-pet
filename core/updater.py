#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create or Destroy — 3-Layer Hot-Update & Patch Manager (熱更新包管理模組)
Zero external dependencies (uses standard library zipfile, shutil, json, datetime).
Guarantees:
1. NEVER overwrites `data/companion_save.db` (player EXP, coins, wisdom, achievements are 100% preserved).
2. Automatically creates a timestamped backup of `data/companion_save.db` in `data/backups/` before applying any patch.
3. Supports applying `.zip` hot-update packs (`gamedata/`, `assets/`, `web/`, `core/`) and generating hot-update `.zip` patches.
"""
import datetime
import io
import json
import os
import shutil
import zipfile

BASE_DIR = "/home/angela/3d model"
DATA_DIR = os.path.join(BASE_DIR, "data")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
RELEASES_DIR = os.path.join(BASE_DIR, "releases")
GAMEDATA_DIR = os.path.join(BASE_DIR, "gamedata")
DB_PATH = os.path.join(DATA_DIR, "companion_save.db")

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(RELEASES_DIR, exist_ok=True)

ALLOWED_PREFIXES = ("gamedata/", "assets/", "web/", "core/")
PROTECTED_PATHS = {"data/companion_save.db", "companion_save.db"}


class HotUpdateManager:
    def __init__(self, db):
        self.db = db

    def backup_database(self):
        if not os.path.exists(DB_PATH):
            return None
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"companion_save_backup_{ts}.db")
        shutil.copy2(DB_PATH, backup_file)
        return backup_file

    def apply_patch_bytes(self, zip_bytes, patch_name="uploaded_patch.zip"):
        """Applies a hot-update .zip package safely while protecting player save data."""
        backup_path = self.backup_database()
        updated_files = []
        skipped_files = []

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    rel_path = member.filename.replace("\\", "/").lstrip("/")
                    # Prevent path traversal
                    if ".." in rel_path.split("/"):
                        skipped_files.append(rel_path)
                        continue
                    # Never overwrite player save database
                    if rel_path in PROTECTED_PATHS or rel_path.startswith("data/"):
                        skipped_files.append(rel_path)
                        continue
                    if not any(rel_path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
                        skipped_files.append(rel_path)
                        continue

                    target_path = os.path.join(BASE_DIR, rel_path)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with zf.open(member) as src, open(target_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    updated_files.append(rel_path)

            ver_info = self.db.get_version_info()
            with self.db.lock, self.db._connect() as conn:
                self.db.add_log(
                    conn,
                    "熱更新系統",
                    f"📦 成功套用熱更新包【{patch_name}】（更新了 {len(updated_files)} 個檔案，玩家存檔已安全備份並完整保留！目前版本 v{ver_info.get('version')}）",
                )
                conn.commit()

            return {
                "ok": True,
                "patch_name": patch_name,
                "updated_count": len(updated_files),
                "updated_files": updated_files[:20],
                "backup_path": backup_path,
                "version_info": ver_info,
                "message": f"✅ 熱更新包【{patch_name}】套用成功！共更新 {len(updated_files)} 個檔案，玩家存檔與經驗值 100% 保留！",
                "state": self.db.get_full_state(),
            }
        except Exception as e:
            return {"ok": False, "error": f"熱更新包解析失敗：{str(e)}"}

    def create_sample_patch(self, new_version="1.0.1", patch_notes="新增熱更新測試：更新對話詞庫與島民商店設定，不影響玩家存檔"):
        """Generates a real lightweight hot-update .zip package in releases/ for instant testing or distribution."""
        ver_path = os.path.join(GAMEDATA_DIR, "version.json")
        ver_data = self.db.get_version_info()
        ver_data["version"] = new_version
        ver_data["last_updated"] = datetime.date.today().isoformat()
        ver_data["patch_notes"] = patch_notes

        with open(ver_path, "w", encoding="utf-8") as f:
            json.dump(ver_data, f, ensure_ascii=False, indent=2)

        patch_filename = f"update_patch_v{new_version}.zip"
        patch_path = os.path.join(RELEASES_DIR, patch_filename)

        with zipfile.ZipFile(patch_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Pack all gamedata/*.json and web/* files into the lightweight patch
            for folder in ("gamedata", "web"):
                src_dir = os.path.join(BASE_DIR, folder)
                if not os.path.exists(src_dir):
                    continue
                for root, _, files in os.walk(src_dir):
                    for fn in files:
                        full_p = os.path.join(root, fn)
                        rel_p = os.path.relpath(full_p, BASE_DIR)
                        zf.write(full_p, rel_p)

        size_kb = round(os.path.getsize(patch_path) / 1024, 1)
        with self.db.lock, self.db._connect() as conn:
            self.db.add_log(
                conn,
                "熱更新系統",
                f"🛠️ 已打包生成輕量熱更新包 `releases/{patch_filename}`（大小僅 {size_kb} KB，版本號 v{new_version}）！",
            )
            conn.commit()

        return {
            "ok": True,
            "patch_filename": patch_filename,
            "patch_path": patch_path,
            "size_kb": size_kb,
            "version_info": ver_data,
            "message": f"🎉 已成功生成熱更新包 `releases/{patch_filename}`（{size_kb} KB）！之後只需要把這個小壓縮包發給玩家即可一鍵更新，完全不用重新封包整個主程式！",
            "state": self.db.get_full_state(),
        }
