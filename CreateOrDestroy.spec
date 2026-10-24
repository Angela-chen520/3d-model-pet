# -*- mode: python ; coding: utf-8 -*-
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
