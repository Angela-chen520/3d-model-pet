@echo off
chcp 65001 >nul
title Create or Destroy — 雪靈 ^& 凌風 AI 桌寵養成系統
cd /d "%~dp0"
echo ====================================================================
echo ⚡ 正在啟動 Create or Destroy — 雪靈 (Xueling) ^& 凌風 (Ling Feng) AI 桌寵系統
echo 💾 免安裝額外解碼程式，玩家存檔自動保存於 data\companion_save.db
echo ====================================================================
python app.py
pause
