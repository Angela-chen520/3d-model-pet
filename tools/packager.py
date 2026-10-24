#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create or Destroy — 封包與熱更新打包工具 (Packaging & Hot-Update Builder)
支援三種模式：
1. `python3 tools/packager.py --mode patch --version 1.0.1`
   ➔ 1 秒生成輕量熱更新包 `releases/update_patch_v1.0.1.zip`（僅包含 gamedata/、web/、core/，絕不覆蓋玩家 data/companion_save.db 存檔）。
2. `python3 tools/packager.py --mode portable`
   ➔ 生成完整免安裝綠色便攜包 `releases/CreateOrDestroy_Portable_v1.0.0.zip`（解壓即玩，內含雙擊啟動檔與完整素材庫）。
3. `python3 tools/packager.py --mode exe`
   ➔ 生成 PyInstaller `CreateOrDestroy.spec` 並（若環境已安裝 PyInstaller）自動封包成獨立 `.exe` / 執行檔。
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import zipfile

BASE_DIR = "/home/angela/3d model"
RELEASES_DIR = os.path.join(BASE_DIR, "releases")
GAMEDATA_DIR = os.path.join(BASE_DIR, "gamedata")
os.makedirs(RELEASES_DIR, exist_ok=True)


def get_version():
    ver_path = os.path.join(GAMEDATA_DIR, "version.json")
    if os.path.exists(ver_path):
        with open(ver_path, "r", encoding="utf-8") as f:
            return json.load(f).get("version", "1.0.0")
    return "1.0.0"


def build_hot_update_patch(version, notes):
    ver_path = os.path.join(GAMEDATA_DIR, "version.json")
    ver_data = {
        "app_name": "Create or Destroy — 雪靈 & 凌風 AI 桌寵養成系統",
        "version": version,
        "last_updated": datetime.date.today().isoformat(),
        "patch_notes": notes,
        "hot_update_supported": True,
    }
    with open(ver_path, "w", encoding="utf-8") as f:
        json.dump(ver_data, f, ensure_ascii=False, indent=2)

    out_zip = os.path.join(RELEASES_DIR, f"update_patch_v{version}.zip")
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in ("gamedata", "web", "core"):
            folder_path = os.path.join(BASE_DIR, folder)
            for root, _, files in os.walk(folder_path):
                if "__pycache__" in root:
                    continue
                for fn in files:
                    full_p = os.path.join(root, fn)
                    rel_p = os.path.relpath(full_p, BASE_DIR)
                    zf.write(full_p, rel_p)

    size_kb = round(os.path.getsize(out_zip) / 1024, 1)
    print(f"✅ [熱更新包生成完畢] 路徑: {out_zip} ({size_kb} KB)")
    return out_zip


def build_portable_bundle():
    version = get_version()
    out_zip = os.path.join(RELEASES_DIR, f"CreateOrDestroy_Portable_v{version}.zip")
    include_folders = ("assets", "core", "gamedata", "web", "tools")
    include_files = (
        "app.py",
        "start_companion.py",
        "start.sh",
        "Start_CreateOrDestroy.bat",
        "Create_or_Destroy_規格書.md",
    )

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in include_files:
            full_p = os.path.join(BASE_DIR, fn)
            if os.path.exists(full_p):
                zf.write(full_p, f"CreateOrDestroy/{fn}")

        for folder in include_folders:
            folder_path = os.path.join(BASE_DIR, folder)
            if not os.path.exists(folder_path):
                continue
            for root, _, files in os.walk(folder_path):
                if "__pycache__" in root:
                    continue
                for fn in files:
                    full_p = os.path.join(root, fn)
                    rel_p = os.path.relpath(full_p, BASE_DIR)
                    zf.write(full_p, f"CreateOrDestroy/{rel_p}")

    size_mb = round(os.path.getsize(out_zip) / (1024 * 1024), 2)
    print(f"✅ [免安裝綠色便攜包生成完畢] 路徑: {out_zip} ({size_mb} MB)")
    return out_zip


def build_pyinstaller_spec_and_exe():
    spec_content = """# -*- mode: python ; coding: utf-8 -*-
# Create or Destroy — PyInstaller 三層分離式封包設定檔
# 執行 `pyinstaller CreateOrDestroy.spec` 即可封包出免安裝主程式，同時將 assets/ 與 gamedata/ 保持外掛以支援 .zip 熱更新！

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('web', 'web'),
        ('gamedata', 'gamedata'),
        ('assets', 'assets'),
    ],
    hiddenimports=['sqlite3', 'http.server', 'urllib.request', 'json', 'zipfile'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CreateOrDestroy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CreateOrDestroy',
)
"""
    spec_path = os.path.join(BASE_DIR, "CreateOrDestroy.spec")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(spec_content)
    print(f"✅ 已生成 PyInstaller 封包設定檔：{spec_path}")

    if shutil.which("pyinstaller"):
        print("🚀 偵測到 PyInstaller，正在執行自動封包...")
        subprocess.run(["pyinstaller", "--clean", "-y", spec_path], cwd=BASE_DIR, check=False)
    else:
        print("ℹ️ 目前環境未安裝 pyinstaller，已為您準備好 `CreateOrDestroy.spec` 與免安裝綠色便攜包！")


def main():
    parser = argparse.ArgumentParser(description="Create or Destroy Packaging & Hot-Update Tool")
    parser.add_argument("--mode", choices=["patch", "portable", "exe", "all"], default="all")
    parser.add_argument("--version", default="1.0.1")
    parser.add_argument("--notes", default="初始熱更新包：支援島民商店 23 商品、番茄鐘 +15 智慧/-20 體力與誇張動漫漫符表情")
    args = parser.parse_args()

    if args.mode in ("patch", "all"):
        build_hot_update_patch(args.version, args.notes)
    if args.mode in ("portable", "all"):
        build_portable_bundle()
    if args.mode in ("exe", "all"):
        build_pyinstaller_spec_and_exe()


if __name__ == "__main__":
    main()
