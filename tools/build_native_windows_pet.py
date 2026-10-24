#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create or Destroy — 華碩天選姬 (TX Mascot) 同級 Windows 原生透明懸浮桌寵封裝器
直接生成真實的 Windows GUI 執行檔 (.exe)：
  1. releases/CreateOrDestroy_桌寵_Installer.exe (單一 .exe 安裝啟動器，對標 TX Mascot Installer.exe)
  2. releases/CreateOrDestroy_桌寵.exe (單一 .exe 免安裝直開版)
  3. releases/CreateOrDestroy_真正桌面寵物_v2.0.zip

特點：
  - 完全不開任何網頁瀏覽器！不是網頁版！
  - 採用 Win32 UpdateLayeredWindow (Per-Pixel Alpha 32-bit ARGB) 100% 去背透明懸浮於 Windows 桌面與工作列上方
  - 平時滑鼠未移上去時自動隱藏按鈕（桌面上 100% 只有雪靈/凌風自己邁步走動、呼吸、蹦跳、切換 14 種浮誇動漫表情）
  - 滑鼠移到角色身上時自動浮現快捷膠囊按鈕；左鍵按住可拎起角色在螢幕任意拖曳 + 放開後真實重力掉落 Q 彈著陸
  - 右鍵選單與右下角 Windows 系統匣常駐圖示 (System Tray Icon)：內建 30 分鐘番茄鐘 (+15智慧/-20體力)、23 種道具島民商店、Discord 單人+1/多人+5 骰子、AI 對話視窗
"""

import base64
import io
import os
import struct
import zipfile

BASE_DIR = "/home/angela/3d model"
RELEASES_DIR = os.path.join(BASE_DIR, "releases")
os.makedirs(RELEASES_DIR, exist_ok=True)


def build_assets_binary_pack():
    """
    Packs all 24 transparent character PNG sprites (Xueling & Ling Feng turnarounds + 14 exaggerated expressions)
    into a single binary resource stream `[int32 count] -> [int32 key_len][utf8 key][int32 data_len][png bytes]`.
    """
    sprite_list = [
        # Xueling turnaround & fullbody
        ("xueling_fullbody", "assets/xueling/turnaround/main_fullbody.png"),
        ("xueling_front", "assets/xueling/turnaround/turn_1_front.png"),
        ("xueling_left45", "assets/xueling/turnaround/turn_2_left45.png"),
        ("xueling_side", "assets/xueling/turnaround/turn_3_side.png"),
        ("xueling_back", "assets/xueling/turnaround/turn_5_back.png"),
        # Xueling 7 exaggerated expressions
        ("xueling_expr_1_normal", "assets/xueling/expressions/expr_1_normal.png"),
        ("xueling_expr_2_happy", "assets/xueling/expressions/expr_2_happy.png"),
        ("xueling_expr_3_angry", "assets/xueling/expressions/expr_3_angry.png"),
        ("xueling_expr_4_surprised", "assets/xueling/expressions/expr_4_surprised.png"),
        ("xueling_expr_5_shy", "assets/xueling/expressions/expr_5_shy.png"),
        ("xueling_expr_6_focused", "assets/xueling/expressions/expr_6_focused.png"),
        ("xueling_expr_7_sick", "assets/xueling/expressions/expr_7_sick.png"),
        # Ling Feng turnaround & racing
        ("lingfeng_fullbody", "assets/lingfeng/turnaround/main_fullbody.png"),
        ("lingfeng_front", "assets/lingfeng/turnaround/turn_1_front.png"),
        ("lingfeng_side", "assets/lingfeng/turnaround/turn_2_side.png"),
        ("lingfeng_back", "assets/lingfeng/turnaround/turn_3_back.png"),
        ("lingfeng_racing", "assets/lingfeng/turnaround/racing_scene.png"),
        # Ling Feng 7 exaggerated expressions
        ("lingfeng_expr_1_normal", "assets/lingfeng/expressions/expr_1_normal.png"),
        ("lingfeng_expr_2_happy", "assets/lingfeng/expressions/expr_2_smile.png"),
        ("lingfeng_expr_3_angry", "assets/lingfeng/expressions/expr_3_angry.png"),
        ("lingfeng_expr_4_surprised", "assets/lingfeng/expressions/expr_4_surprised.png"),
        ("lingfeng_expr_5_shy", "assets/lingfeng/expressions/expr_5_shy.png"),
        ("lingfeng_expr_6_focused", "assets/lingfeng/expressions/expr_6_focused.png"),
        ("lingfeng_expr_7_sick", "assets/lingfeng/expressions/expr_7_sick.png"),
    ]

    chunks = [struct.pack("<i", len(sprite_list))]
    for key, rel_path in sprite_list:
        full_path = os.path.join(BASE_DIR, rel_path)
        with open(full_path, "rb") as f:
            png_bytes = f.read()
        key_bytes = key.encode("utf-8")
        chunks.append(struct.pack("<i", len(key_bytes)))
        chunks.append(key_bytes)
        chunks.append(struct.pack("<i", len(png_bytes)))
        chunks.append(png_bytes)

    return b"".join(chunks)


CSHARP_NATIVE_PET_SOURCE = r"""using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

namespace CreateOrDestroyNativePet
{
    // =========================================================================
    // WIN32 PER-PIXEL ALPHA LAYERED WINDOW API (天選姬同級 100% 透明去背懸浮桌面核心)
    // =========================================================================
    internal static class NativeMethods
    {
        public const int WS_EX_LAYERED = 0x00080000;
        public const int WS_EX_TOPMOST = 0x00000008;
        public const byte AC_SRC_OVER = 0x00;
        public const byte AC_SRC_ALPHA = 0x01;
        public const int ULW_ALPHA = 0x00000002;

        [StructLayout(LayoutKind.Sequential)]
        public struct Point { public int x; public int y; public Point(int x, int y) { this.x = x; this.y = y; } }

        [StructLayout(LayoutKind.Sequential)]
        public struct Size { public int cx; public int cy; public Size(int cx, int cy) { this.cx = cx; this.cy = cy; } }

        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct BLENDFUNCTION
        {
            public byte BlendOp;
            public byte BlendFlags;
            public byte SourceConstantAlpha;
            public byte AlphaFormat;
        }

        [DllImport("user32.dll", ExactSpelling = true, SetLastError = true)]
        public static extern bool UpdateLayeredWindow(IntPtr hwnd, IntPtr hdcDst, ref Point pptDst, ref Size psize, IntPtr hdcSrc, ref Point pprSrc, int crKey, ref BLENDFUNCTION pblend, int dwFlags);

        [DllImport("user32.dll", ExactSpelling = true, SetLastError = true)]
        public static extern IntPtr GetDC(IntPtr hWnd);

        [DllImport("user32.dll", ExactSpelling = true)]
        public static extern int ReleaseDC(IntPtr hWnd, IntPtr hDC);

        [DllImport("gdi32.dll", ExactSpelling = true, SetLastError = true)]
        public static extern IntPtr CreateCompatibleDC(IntPtr hDC);

        [DllImport("gdi32.dll", ExactSpelling = true, SetLastError = true)]
        public static extern bool DeleteDC(IntPtr hdc);

        [DllImport("gdi32.dll", ExactSpelling = true)]
        public static extern IntPtr SelectObject(IntPtr hDC, IntPtr hObject);

        [DllImport("gdi32.dll", ExactSpelling = true, SetLastError = true)]
        public static extern bool DeleteObject(IntPtr hObject);
    }

    public class ShopItem
    {
        public string Id;
        public string Category;
        public string Name;
        public int Price;
        public int Recovery;
        public int HungerRelief;
        public int StaminaRelief;
        public bool TriggersGastro;
        public bool CuresCold;
        public bool CuresGastro3D;
        public string Desc;

        public ShopItem(string id, string cat, string name, int price, int rec, int hunger, int stam, bool bad, bool cold, bool gastro, string desc)
        {
            Id = id; Category = cat; Name = name; Price = price; Recovery = rec;
            HungerRelief = hunger; StaminaRelief = stam;
            TriggersGastro = bad; CuresCold = cold; CuresGastro3D = gastro; Desc = desc;
        }
    }

    public class CharState
    {
        public string Id;
        public string Name;
        public int Affection = 55;
        public int RecoveryExp = 100;
        public int WisdomExp = 0;
        public int PomodoroCount = 0;
        public int Stamina = 100;
        public int Hunger = 20;
        public int Dirtiness = 15;
        public int Fatigue = 15;
        public string Health = "healthy";
        public int GastroDaysRemaining = 0;
        public bool GastroCourseActive = false;
        public string CurrentExpr = "expr_1_normal";
        public string CurrentView = "front";

        public int GetLevel(double totalExp)
        {
            int lv = 1 + (int)((totalExp + Math.Max(0, RecoveryExp) + WisdomExp * 2) / 100.0);
            return Math.Max(1, lv);
        }
    }

    public class FloatingParticle
    {
        public string Text;
        public float X;
        public float Y;
        public float VX;
        public float VY;
        public int Life;
        public Color Color;
    }

    // =========================================================================
    // 主透明懸浮桌寵視窗 (對標華碩天選姬 TX Mascot 桌面體驗)
    // =========================================================================
    public class TransparentPetForm : Form
    {
        private Dictionary<string, Bitmap> sprites = new Dictionary<string, Bitmap>();
        public Dictionary<string, CharState> Chars = new Dictionary<string, CharState>();
        public List<ShopItem> ShopCatalog = new List<ShopItem>();
        public List<string> UnlockedAchievements = new List<string>();

        public string ActiveChar = "xueling";
        public double TotalExp = 100.0;
        public double AvailableExp = 100.0;
        public int Coins = 60;
        public int StreakDays = 1;

        // 桌寵自主移動與物理引擎狀態
        public bool AutoWalkEnabled = true;
        public bool ChibiBigHeadMode = true; // 預設開啟 Q版二頭身大頭動態走路模式
        public bool PinInAirMode = false;    // 是否允許固定在螢幕任意高度
        public string MoveState = "walk";    // idle, walk, jump, drag, fall
        public float PosX = 600f;
        public float PosY = 400f;
        public float VelX = 2.5f;
        public float VelY = 0f;
        public int WalkDir = -1;
        public float AnimPhase = 0f;
        public int StateTicks = 90;
        public float FloorY = 500f;

        // 滑鼠拖曳狀態
        private bool isDragging = false;
        private Point dragCursorStart;
        private Point dragFormStart;
        private bool dragMoved = false;

        // 對話氣泡與特效粒子
        public string SpeechText = "嗨！我是真正的桌面寵物雪靈 ✨ 我現在直接站在你的 Windows 桌面上自己走動囉！（滑鼠移到我身上或按右鍵有選單）";
        public int SpeechTimer = 240;
        private List<FloatingParticle> particles = new List<FloatingParticle>();
        private Random rng = new Random();

        // 番茄鐘狀態 (30分鐘 = 1800秒)
        public bool PomoRunning = false;
        public int PomoRemainingSec = 1800;
        private int pomoTickCounter = 0;

        // 畫布尺寸與底部快捷膠囊按鈕區 (滑鼠移到角色身上才浮現，平時完全隱藏！)
        private const int CANVAS_W = 360;
        private const int CANVAS_H = 450;
        private Rectangle rectBtnPat = new Rectangle(22, 405, 62, 30);
        private Rectangle rectBtnPomo = new Rectangle(88, 405, 66, 30);
        private Rectangle rectBtnShop = new Rectangle(158, 405, 62, 30);
        private Rectangle rectBtnDice = new Rectangle(224, 405, 62, 30);
        private Rectangle rectBtnMenu = new Rectangle(290, 405, 52, 30);
        private Rectangle rectExprBubble = new Rectangle(232, 85, 118, 125);

        private Timer renderTimer;
        private ContextMenuStrip petMenu;
        private NotifyIcon trayIcon;
        private string saveFilePath;

        public TransparentPetForm()
        {
            this.FormBorderStyle = FormBorderStyle.None;
            this.ShowInTaskbar = false; // 像天選姬一樣常駐在右下角系統匣，不佔用工作列長條按鈕
            this.Text = "Create or Destroy — 雪靈 & 凌風 桌面寵物";
            this.Size = new Size(CANVAS_W, CANVAS_H);
            this.TopMost = true;
            this.DoubleBuffered = true;

            saveFilePath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "pet_save_data.txt");

            LoadEmbeddedSprites();
            InitGameData();
            LoadSaveData();

            Rectangle workArea = Screen.PrimaryScreen.WorkingArea;
            FloorY = workArea.Bottom - CANVAS_H + 8;
            PosX = workArea.Right - CANVAS_W - 90;
            PosY = FloorY;
            this.Location = new Point((int)PosX, (int)PosY);

            BuildContextMenu();
            InitTrayIcon();

            this.MouseDown += OnPetMouseDown;
            this.MouseMove += OnPetMouseMove;
            this.MouseUp += OnPetMouseUp;
            this.MouseDoubleClick += OnPetMouseDoubleClick;

            renderTimer = new Timer();
            renderTimer.Interval = 33; // ~30 FPS
            renderTimer.Tick += OnRenderTick;
            renderTimer.Start();
        }

        protected override CreateParams CreateParams
        {
            get
            {
                CreateParams cp = base.CreateParams;
                cp.ExStyle |= NativeMethods.WS_EX_LAYERED | NativeMethods.WS_EX_TOPMOST;
                return cp;
            }
        }

        private void LoadEmbeddedSprites()
        {
            Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("_pet_assets.bin");
            if (stream == null) stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("pet_assets.bin");
            if (stream == null)
            {
                string localBin = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "_pet_assets.bin");
                if (File.Exists(localBin)) stream = File.OpenRead(localBin);
            }
            if (stream == null) return;

            using (BinaryReader br = new BinaryReader(stream))
            {
                int count = br.ReadInt32();
                for (int i = 0; i < count; i++)
                {
                    int klen = br.ReadInt32();
                    string key = Encoding.UTF8.GetString(br.ReadBytes(klen));
                    int dlen = br.ReadInt32();
                    byte[] pngBytes = br.ReadBytes(dlen);
                    using (MemoryStream ms = new MemoryStream(pngBytes))
                    {
                        Bitmap bmp = new Bitmap(ms);
                        sprites[key] = new Bitmap(bmp);
                    }
                }
            }
        }

        private void InitGameData()
        {
            CharState xl = new CharState();
            xl.Id = "xueling"; xl.Name = "雪靈 (Xueling)";
            Chars["xueling"] = xl;

            CharState lf = new CharState();
            lf.Id = "lingfeng"; lf.Name = "凌風 (Ling Feng)";
            Chars["lingfeng"] = lf;

            ShopCatalog.Add(new ShopItem("cake", "食物", "🍰 蛋糕", 10, 5, 18, 5, false, false, false, "甜蜜草莓鮮奶油蛋糕 (+5恢復)"));
            ShopCatalog.Add(new ShopItem("pancake", "食物", "🥞 鬆餅", 10, 5, 18, 5, false, false, false, "蜂蜜奶油厚鬆餅 (+5恢復)"));
            ShopCatalog.Add(new ShopItem("choco_cake", "食物", "🍫 巧克力蛋糕", 10, 5, 18, 5, false, false, false, "濃郁黑巧克力蛋糕 (+5恢復)"));
            ShopCatalog.Add(new ShopItem("bagel", "食物", "🥯 貝果", 10, 5, 20, 5, false, false, false, "現烤嚼勁藍莓貝果 (+5恢復)"));
            ShopCatalog.Add(new ShopItem("plain_rice_ball", "食物", "🍙 原味飯糰", 15, 7, 25, 8, false, false, false, "海苔包覆飽滿飯糰 (+7恢復)"));
            ShopCatalog.Add(new ShopItem("tuna_rice_ball", "食物", "🍙 鮪魚飯糰", 15, 7, 25, 8, false, false, false, "特調美乃滋鮪魚飯糰 (+7恢復)"));
            ShopCatalog.Add(new ShopItem("salmon_roe_rice_ball", "食物", "🍣 鮭魚卵飯糰", 15, 7, 25, 8, false, false, false, "晶瑩剔透鮭魚卵飯糰 (+7恢復)"));
            ShopCatalog.Add(new ShopItem("bento", "食物", "🍱 便當", 20, 10, 40, 15, false, false, false, "營養滿分豪華雙主菜便當 (+10恢復)"));

            ShopCatalog.Add(new ShopItem("vitality_drink", "飲料", "⚡ 蠻牛", 5, 2, 5, 20, false, false, false, "機能提神飲料 (+2恢復/+20體力)"));
            ShopCatalog.Add(new ShopItem("energy_drink", "飲料", "🔋 能量飲", 5, 2, 5, 20, false, false, false, "電競選手專屬能量飲 (+2恢復/+20體力)"));
            ShopCatalog.Add(new ShopItem("coffee", "飲料", "☕ 咖啡", 5, 2, 5, 18, false, false, false, "現磨冰鎮美式咖啡 (+2恢復/+18體力)"));
            ShopCatalog.Add(new ShopItem("black_tea", "飲料", "🍵 紅茶", 5, 2, 8, 10, false, false, false, "清香回甘冰鎮紅茶 (+2恢復)"));
            ShopCatalog.Add(new ShopItem("green_tea", "飲料", "🍃 綠茶", 5, 2, 8, 10, false, false, false, "日式無糖鮮萃綠茶 (+2恢復)"));
            ShopCatalog.Add(new ShopItem("milk_tea", "飲料", "🥤 奶茶", 10, 4, 12, 12, false, false, false, "香濃絲滑厚奶茶 (+4恢復)"));
            ShopCatalog.Add(new ShopItem("boba_milk_tea", "飲料", "🧋 珍珠奶茶", 15, 6, 18, 15, false, false, false, "Q彈黑糖波霸珍珠奶茶 (+6恢復)"));
            ShopCatalog.Add(new ShopItem("bad_mystery_drink", "飲料", "🧪 不知放多少天的飲料", 5, -20, 0, -15, true, false, false, "⚠️ 散發詭異氣味！(-20恢復，直接觸發3天腸胃炎)"));

            ShopCatalog.Add(new ShopItem("towel", "生活與醫療", "🧣 毛巾", 5, 5, 0, 10, false, false, false, "柔軟吸水運動毛巾 (+5恢復)"));
            ShopCatalog.Add(new ShopItem("toothbrush", "生活與醫療", "🪥 牙刷", 5, 5, 0, 8, false, false, false, "極細軟毛護理牙刷 (+5恢復)"));
            ShopCatalog.Add(new ShopItem("mouthwash", "生活與醫療", "🫧 漱口水", 5, 5, 0, 8, false, false, false, "薄荷清新抗菌漱口水 (+5恢復)"));
            ShopCatalog.Add(new ShopItem("advanced_toothbrush", "生活與醫療", "✨ 高級牙刷", 10, 10, 0, 12, false, false, false, "音波震動亮白高級牙刷 (+10恢復)"));
            ShopCatalog.Add(new ShopItem("Cold_medicine", "生活與醫療", "💊 感冒藥", 20, 50, 0, 25, false, true, false, "專治角色感冒發燒 (+50恢復，立即治癒感冒)"));
            ShopCatalog.Add(new ShopItem("gastro_medicine_3d", "生活與醫療", "🏥 腸胃藥三天份", 35, 100, 0, 30, false, false, true, "專治腸胃炎 (+100恢復，啟動3天腸胃炎康復療程)"));
            ShopCatalog.Add(new ShopItem("first_aid_kit", "生活與醫療", "🧰 綜合急救箱", 50, 120, 0, 50, false, true, true, "全方位醫療急救箱 (+120恢復)"));
        }

        public void SaveData()
        {
            try
            {
                CharState xl = Chars["xueling"];
                CharState lf = Chars["lingfeng"];
                string content = string.Format(
                    "{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}|{8}|{9}|{10}|{11}|{12}|{13}|{14}",
                    ActiveChar, TotalExp, AvailableExp, Coins, StreakDays,
                    xl.Affection, xl.RecoveryExp, xl.WisdomExp, xl.Stamina, xl.Health,
                    lf.Affection, lf.RecoveryExp, lf.WisdomExp, lf.Stamina, lf.Health
                );
                File.WriteAllText(saveFilePath, content, Encoding.UTF8);
            }
            catch { }
        }

        private void LoadSaveData()
        {
            try
            {
                if (!File.Exists(saveFilePath)) return;
                string[] p = File.ReadAllText(saveFilePath, Encoding.UTF8).Split('|');
                if (p.Length >= 15)
                {
                    ActiveChar = p[0];
                    double.TryParse(p[1], out TotalExp);
                    double.TryParse(p[2], out AvailableExp);
                    int.TryParse(p[3], out Coins);
                    int.TryParse(p[4], out StreakDays);
                    int.TryParse(p[5], out Chars["xueling"].Affection);
                    int.TryParse(p[6], out Chars["xueling"].RecoveryExp);
                    int.TryParse(p[7], out Chars["xueling"].WisdomExp);
                    int.TryParse(p[8], out Chars["xueling"].Stamina);
                    Chars["xueling"].Health = p[9];
                    int.TryParse(p[10], out Chars["lingfeng"].Affection);
                    int.TryParse(p[11], out Chars["lingfeng"].RecoveryExp);
                    int.TryParse(p[12], out Chars["lingfeng"].WisdomExp);
                    int.TryParse(p[13], out Chars["lingfeng"].Stamina);
                    Chars["lingfeng"].Health = p[14];
                }
            }
            catch { }
        }

        public CharState CurChar { get { return Chars[ActiveChar]; } }

        public void Say(string text, int durationTicks = 180)
        {
            SpeechText = text;
            SpeechTimer = durationTicks;
        }

        public void SpawnParticles(string symbol, int count, Color col)
        {
            for (int i = 0; i < count; i++)
            {
                FloatingParticle fp = new FloatingParticle();
                fp.Text = symbol;
                fp.X = 140 + rng.Next(-55, 55);
                fp.Y = 175 + rng.Next(-35, 35);
                fp.VX = (float)(rng.NextDouble() * 3.0 - 1.5);
                fp.VY = -(float)(rng.NextDouble() * 2.5 + 1.6);
                fp.Life = 28 + rng.Next(18);
                fp.Color = col;
                particles.Add(fp);
            }
        }

        private void OnRenderTick(object sender, EventArgs e)
        {
            AnimPhase += 0.28f;
            if (SpeechTimer > 0) SpeechTimer--;

            if (PomoRunning)
            {
                pomoTickCounter++;
                if (pomoTickCounter >= 30)
                {
                    pomoTickCounter = 0;
                    PomoRemainingSec--;
                    if (PomoRemainingSec <= 0)
                    {
                        CompletePomodoroSession();
                    }
                }
            }

            for (int i = particles.Count - 1; i >= 0; i--)
            {
                FloatingParticle p = particles[i];
                p.X += p.VX;
                p.Y += p.VY;
                p.Life--;
                if (p.Life <= 0) particles.RemoveAt(i);
            }

            Rectangle workArea = Screen.FromControl(this).WorkingArea;
            if (!PinInAirMode)
            {
                FloorY = workArea.Bottom - CANVAS_H + 8;
            }

            if (MoveState == "drag")
            {
                if (rng.Next(100) < 12) SpawnParticles("⚡", 1, Color.Gold);
            }
            else if (MoveState == "fall")
            {
                VelY += 1.65f;
                PosY += VelY;
                if (PosY >= FloorY)
                {
                    PosY = FloorY;
                    if (Math.Abs(VelY) > 5.0f)
                    {
                        VelY = -VelY * 0.42f;
                        SpawnParticles("✨", 3, Color.Aqua);
                    }
                    else
                    {
                        VelY = 0f;
                        MoveState = AutoWalkEnabled ? "walk" : "idle";
                        StateTicks = 90;
                        CurChar.CurrentExpr = "expr_2_happy";
                        Say("呼～安全著陸在桌面上囉 ✨", 110);
                    }
                }
                this.Location = new Point((int)PosX, (int)PosY);
            }
            else
            {
                StateTicks--;
                if (StateTicks <= 0)
                {
                    if (!AutoWalkEnabled)
                    {
                        MoveState = "idle";
                        StateTicks = 120;
                    }
                    else
                    {
                        int r = rng.Next(100);
                        if (r < 60)
                        {
                            MoveState = "walk";
                            WalkDir = rng.Next(2) == 0 ? -1 : 1;
                            CurChar.CurrentView = "front";
                            StateTicks = 80 + rng.Next(110);
                        }
                        else if (r < 78)
                        {
                            MoveState = "jump";
                            VelY = -11.0f;
                            StateTicks = 50;
                            SpawnParticles("✨", 3, Color.Gold);
                        }
                        else
                        {
                            MoveState = "idle";
                            string[] views = new string[] { "front", "front", "left45", "side" };
                            CurChar.CurrentView = views[rng.Next(views.Length)];
                            StateTicks = 60 + rng.Next(75);
                        }
                    }

                    if (!PomoRunning && CurChar.Health == "healthy" && rng.Next(100) < 35)
                    {
                        string[] exprs = new string[] { "expr_1_normal", "expr_2_happy", "expr_5_shy", "expr_4_surprised", "expr_6_focused" };
                        CurChar.CurrentExpr = exprs[rng.Next(exprs.Length)];
                        string[] lines = ActiveChar == "xueling"
                            ? new string[] {
                                "達達達～在主人的電腦桌面上散步好開心 ✨",
                                "左鍵按住我可以把我拎起來拖到螢幕任何角落喔！",
                                "要不要開啟 30 分鐘番茄鐘呀？完成有 +15 智慧經驗值喔 💡",
                                "滑鼠移到我身上或點右鍵可以打開【🏪島民商店】餵我吃點心喔 🧋"
                            }
                            : new string[] {
                                "凌風正在你的桌面上巡邏待命 🏎️💨",
                                "需要專注衝刺時，點【🍅番茄鐘】我陪你一起進入極限專注狀態 💡",
                                "左鍵點我可以互動，右鍵點我有完整功能選單與角色切換喔 ✨"
                            };
                        Say(lines[rng.Next(lines.Length)], 150);
                    }
                }

                if (MoveState == "walk" && AutoWalkEnabled)
                {
                    PosX += WalkDir * VelX;
                    int minX = workArea.Left + 10;
                    int maxX = workArea.Right - CANVAS_W - 10;
                    if (PosX <= minX) { PosX = minX; WalkDir = 1; }
                    if (PosX >= maxX) { PosX = maxX; WalkDir = -1; }
                    this.Location = new Point((int)PosX, (int)PosY);
                }
                else if (MoveState == "jump")
                {
                    VelY += 1.25f;
                    PosY += VelY;
                    if (PosY >= FloorY)
                    {
                        PosY = FloorY;
                        if (StateTicks > 20) VelY = -7.5f;
                        else { VelY = 0f; MoveState = "idle"; }
                    }
                    this.Location = new Point((int)PosX, (int)PosY);
                }
            }

            RenderLayeredPetCanvas();
        }

        private void RenderLayeredPetCanvas()
        {
            bool isHovered = this.Bounds.Contains(Cursor.Position) || isDragging;

            using (Bitmap canvas = new Bitmap(CANVAS_W, CANVAS_H, PixelFormat.Format32bppArgb))
            using (Graphics g = Graphics.FromImage(canvas))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAliasGridFit;
                g.Clear(Color.Transparent);

                CharState c = CurChar;
                int lv = c.GetLevel(TotalExp);

                // 1. 腳下柔和全息光環陰影
                using (GraphicsPath shadowPath = new GraphicsPath())
                {
                    shadowPath.AddEllipse(90, 378, 140, 20);
                    using (PathGradientBrush pgb = new PathGradientBrush(shadowPath))
                    {
                        pgb.CenterColor = Color.FromArgb(95, 0, 229, 255);
                        pgb.SurroundColors = new Color[] { Color.FromArgb(0, 0, 229, 255) };
                        g.FillPath(pgb, shadowPath);
                    }
                }

                // 2. 取得角色立繪與誇張表情貼圖
                string bodyKey = ActiveChar + "_front";
                if (c.CurrentView == "fullbody") bodyKey = ActiveChar + "_fullbody";
                else if (c.CurrentView == "left45" && sprites.ContainsKey(ActiveChar + "_left45")) bodyKey = ActiveChar + "_left45";
                else if (c.CurrentView == "side" && sprites.ContainsKey(ActiveChar + "_side")) bodyKey = ActiveChar + "_side";
                else if (c.CurrentView == "back" && sprites.ContainsKey(ActiveChar + "_back")) bodyKey = ActiveChar + "_back";
                else if (c.CurrentView == "racing" && sprites.ContainsKey("lingfeng_racing")) bodyKey = "lingfeng_racing";

                if (!sprites.ContainsKey(bodyKey)) bodyKey = ActiveChar + "_fullbody";
                Bitmap bodyBmp = sprites.ContainsKey(bodyKey) ? sprites[bodyKey] : null;

                string exprKey = ActiveChar + "_" + c.CurrentExpr;
                if (!sprites.ContainsKey(exprKey)) exprKey = ActiveChar + "_expr_1_normal";
                Bitmap exprBmp = sprites.ContainsKey(exprKey) ? sprites[exprKey] : null;

                float bobY = 0f;
                float tiltAngle = 0f;
                float legStep = 0f;

                if (MoveState == "walk")
                {
                    bobY = -(float)Math.Abs(Math.Sin(AnimPhase)) * 9.0f;
                    tiltAngle = (float)Math.Sin(AnimPhase) * 2.8f;
                    legStep = (float)Math.Sin(AnimPhase) * 7.5f;
                }
                else if (MoveState == "drag")
                {
                    bobY = -8.0f;
                    tiltAngle = (float)Math.Sin(AnimPhase * 1.7f) * 7.5f;
                    legStep = (float)Math.Cos(AnimPhase * 2.0f) * 6.0f;
                }
                else
                {
                    bobY = (float)Math.Sin(AnimPhase * 0.45f) * 3.8f;
                }

                // 3. 繪製去背透明角色主體 (雙腿交替邁步 + 浮誇動漫表情)
                if (bodyBmp != null)
                {
                    GraphicsState state = g.Save();
                    float centerX = 160f;
                    float centerY = 252f + bobY;
                    g.TranslateTransform(centerX, centerY);
                    g.RotateTransform(tiltAngle);
                    if (WalkDir > 0 && c.CurrentView != "racing")
                    {
                        g.ScaleTransform(-1f, 1f);
                    }

                    if (ChibiBigHeadMode && exprBmp != null && c.CurrentView == "front")
                    {
                        int bw = bodyBmp.Width;
                        int bh = bodyBmp.Height;
                        int splitY = (int)(bh * 0.64f);
                        int neckY = (int)(bh * 0.34f);

                        Rectangle srcLegL = new Rectangle(0, splitY, bw / 2, bh - splitY);
                        Rectangle srcLegR = new Rectangle(bw / 2, splitY, bw - bw / 2, bh - splitY);
                        float legL_Y = 58f - Math.Max(0f, legStep * 1.1f);
                        float legR_Y = 58f - Math.Max(0f, -legStep * 1.1f);
                        g.DrawImage(bodyBmp, new RectangleF(-52f + legStep * 0.4f, legL_Y, 52f, 82f), srcLegL, GraphicsUnit.Pixel);
                        g.DrawImage(bodyBmp, new RectangleF(0f - legStep * 0.4f, legR_Y, 52f, 82f), srcLegR, GraphicsUnit.Pixel);

                        Rectangle srcTorso = new Rectangle(0, neckY, bw, splitY - neckY);
                        g.DrawImage(bodyBmp, new RectangleF(-54f, -15f, 108f, 80f), srcTorso, GraphicsUnit.Pixel);

                        g.DrawImage(exprBmp, new RectangleF(-68f, -128f, 136f, 138f));
                    }
                    else
                    {
                        int bw = bodyBmp.Width;
                        int bh = bodyBmp.Height;
                        int splitY = (int)(bh * 0.68f);
                        Rectangle srcUpper = new Rectangle(0, 0, bw, splitY);
                        Rectangle srcLegL = new Rectangle(0, splitY, bw / 2, bh - splitY);
                        Rectangle srcLegR = new Rectangle(bw / 2, splitY, bw - bw / 2, bh - splitY);

                        g.DrawImage(bodyBmp, new RectangleF(-68f + legStep * 0.35f, 42f - Math.Max(0f, legStep), 68f, 92f), srcLegL, GraphicsUnit.Pixel);
                        g.DrawImage(bodyBmp, new RectangleF(0f - legStep * 0.35f, 42f - Math.Max(0f, -legStep), 68f, 92f), srcLegR, GraphicsUnit.Pixel);
                        g.DrawImage(bodyBmp, new RectangleF(-68f, -135f, 136f, 182f), srcUpper, GraphicsUnit.Pixel);
                    }
                    g.Restore(state);
                }

                if (exprBmp != null && !ChibiBigHeadMode && isHovered)
                {
                    FillRoundedRect(g, rectExprBubble, 14, Color.FromArgb(215, 12, 20, 38), Color.FromArgb(240, 0, 229, 255), 2f);
                    g.DrawImage(exprBmp, new Rectangle(rectExprBubble.X + 7, rectExprBubble.Y + 4, 104, 104));
                }

                // 4. 繪製動態漫符特效粒子
                using (Font fPart = new Font("Segoe UI Emoji", 14f, FontStyle.Bold))
                {
                    foreach (FloatingParticle p in particles)
                    {
                        int alpha = Math.Min(255, p.Life * 9);
                        using (SolidBrush bPart = new SolidBrush(Color.FromArgb(alpha, p.Color)))
                        {
                            g.DrawString(p.Text, fPart, bPart, p.X, p.Y);
                        }
                    }
                }

                // 5. 頭頂狀態膠囊 (僅在番茄鐘倒數中、生病中，或滑鼠移到角色身上時顯示！平時完全隱藏不擋桌面)
                if (isHovered || PomoRunning || c.Health != "healthy")
                {
                    Rectangle hudRect = new Rectangle(24, 72, 285, 28);
                    Color hudBorder = PomoRunning ? Color.FromArgb(255, 0, 245, 212) : Color.FromArgb(210, 0, 229, 255);
                    FillRoundedRect(g, hudRect, 13, Color.FromArgb(220, 10, 16, 32), hudBorder, 1.8f);
                    using (Font fHud = new Font("Microsoft JhengHei UI", 8.8f, FontStyle.Bold))
                    using (SolidBrush bHud = new SolidBrush(Color.White))
                    {
                        string hudStr;
                        if (PomoRunning)
                        {
                            int mm = PomoRemainingSec / 60;
                            int ss = PomoRemainingSec % 60;
                            hudStr = string.Format("🍅 專注倒數 {0:00}:{1:00} | 💡智慧 {2} | ⚡體力 {3}", mm, ss, c.WisdomExp, c.Stamina);
                        }
                        else
                        {
                            string hTag = c.Health == "healthy" ? "✨健康" : (c.Health == "cold" ? "🤒感冒中" : "🤢腸胃炎");
                            hudStr = string.Format("{0} Lv.{1} | 🪙{2} | ⚡體力{3} | {4}", ActiveChar == "xueling" ? "❄️雪靈" : "🏎️凌風", lv, Coins, c.Stamina, hTag);
                        }
                        StringFormat sf = new StringFormat();
                        sf.Alignment = StringAlignment.Center;
                        sf.LineAlignment = StringAlignment.Center;
                        g.DrawString(hudStr, fHud, bHud, hudRect, sf);
                    }
                }

                // 6. 頭頂漫畫對話氣泡
                if (SpeechTimer > 0 && !string.IsNullOrEmpty(SpeechText))
                {
                    Rectangle bubbleRect = new Rectangle(12, 8, 325, 58);
                    FillRoundedRect(g, bubbleRect, 12, Color.FromArgb(238, 255, 255, 255), Color.FromArgb(255, 0, 195, 255), 2.2f);
                    using (Font fBubble = new Font("Microsoft JhengHei UI", 9.0f, FontStyle.Bold))
                    using (SolidBrush bText = new SolidBrush(Color.FromArgb(255, 18, 28, 48)))
                    {
                        RectangleF textRect = new RectangleF(bubbleRect.X + 8, bubbleRect.Y + 5, bubbleRect.Width - 16, bubbleRect.Height - 10);
                        g.DrawString(SpeechText, fBubble, bText, textRect);
                    }
                }

                // 7. 腳下 5 顆懸浮快捷膠囊按鈕 (像天選姬一樣：滑鼠移到角色身上才浮現！平時隱藏讓桌面超乾淨)
                if (isHovered)
                {
                    DrawCapsuleButton(g, rectBtnPat, "👋摸頭", Color.FromArgb(225, 20, 34, 62), Color.FromArgb(255, 255, 105, 180));
                    DrawCapsuleButton(g, rectBtnPomo, PomoRunning ? "⏹️停止" : "🍅番茄鐘", Color.FromArgb(225, 20, 34, 62), Color.FromArgb(255, 0, 245, 212));
                    DrawCapsuleButton(g, rectBtnShop, "🏪商店", Color.FromArgb(225, 20, 34, 62), Color.FromArgb(255, 255, 195, 15));
                    DrawCapsuleButton(g, rectBtnDice, "🎲骰子", Color.FromArgb(225, 20, 34, 62), Color.FromArgb(255, 165, 105, 255));
                    DrawCapsuleButton(g, rectBtnMenu, "⚙️選單", Color.FromArgb(225, 20, 34, 62), Color.FromArgb(255, 0, 229, 255));
                }

                ApplyPerPixelAlphaBitmap(canvas);
            }
        }

        private void DrawCapsuleButton(Graphics g, Rectangle r, string label, Color bg, Color border)
        {
            FillRoundedRect(g, r, 10, bg, border, 1.6f);
            using (Font f = new Font("Microsoft JhengHei UI", 8.5f, FontStyle.Bold))
            using (SolidBrush sb = new SolidBrush(Color.White))
            {
                StringFormat sf = new StringFormat();
                sf.Alignment = StringAlignment.Center;
                sf.LineAlignment = StringAlignment.Center;
                g.DrawString(label, f, sb, r, sf);
            }
        }

        private void FillRoundedRect(Graphics g, Rectangle r, int radius, Color fill, Color border, float borderW)
        {
            int d = radius * 2;
            using (GraphicsPath path = new GraphicsPath())
            {
                path.AddArc(r.X, r.Y, d, d, 180, 90);
                path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
                path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
                path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
                path.CloseFigure();
                using (SolidBrush sb = new SolidBrush(fill)) g.FillPath(sb, path);
                using (Pen pen = new Pen(border, borderW)) g.DrawPath(pen, path);
            }
        }

        private void ApplyPerPixelAlphaBitmap(Bitmap bmp)
        {
            IntPtr screenDc = NativeMethods.GetDC(IntPtr.Zero);
            IntPtr memDc = NativeMethods.CreateCompatibleDC(screenDc);
            IntPtr hBitmap = IntPtr.Zero;
            IntPtr oldBitmap = IntPtr.Zero;
            try
            {
                hBitmap = bmp.GetHbitmap(Color.FromArgb(0));
                oldBitmap = NativeMethods.SelectObject(memDc, hBitmap);
                NativeMethods.Size size = new NativeMethods.Size(bmp.Width, bmp.Height);
                NativeMethods.Point pointSource = new NativeMethods.Point(0, 0);
                NativeMethods.Point topPos = new NativeMethods.Point(this.Left, this.Top);
                NativeMethods.BLENDFUNCTION blend = new NativeMethods.BLENDFUNCTION();
                blend.BlendOp = NativeMethods.AC_SRC_OVER;
                blend.BlendFlags = 0;
                blend.SourceConstantAlpha = 255;
                blend.AlphaFormat = NativeMethods.AC_SRC_ALPHA;

                NativeMethods.UpdateLayeredWindow(this.Handle, screenDc, ref topPos, ref size, memDc, ref pointSource, 0, ref blend, NativeMethods.ULW_ALPHA);
            }
            finally
            {
                NativeMethods.ReleaseDC(IntPtr.Zero, screenDc);
                if (hBitmap != IntPtr.Zero)
                {
                    NativeMethods.SelectObject(memDc, oldBitmap);
                    NativeMethods.DeleteObject(hBitmap);
                }
                NativeMethods.DeleteDC(memDc);
            }
        }

        private void OnPetMouseDown(object sender, MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Right)
            {
                petMenu.Show(Cursor.Position);
                return;
            }
            if (e.Button != MouseButtons.Left) return;

            if (rectBtnPat.Contains(e.Location)) { TriggerInteraction("pat"); return; }
            if (rectBtnPomo.Contains(e.Location)) { TogglePomodoro(); return; }
            if (rectBtnShop.Contains(e.Location)) { OpenNativeShopDialog(); return; }
            if (rectBtnDice.Contains(e.Location)) { OpenNativeDiscordDialog(); return; }
            if (rectBtnMenu.Contains(e.Location)) { petMenu.Show(Cursor.Position); return; }
            if (!ChibiBigHeadMode && rectExprBubble.Contains(e.Location)) { CycleExpression(); return; }

            isDragging = true;
            dragMoved = false;
            dragCursorStart = Cursor.Position;
            dragFormStart = this.Location;
        }

        private void OnPetMouseMove(object sender, MouseEventArgs e)
        {
            if (!isDragging) return;
            Point cur = Cursor.Position;
            int dx = cur.X - dragCursorStart.X;
            int dy = cur.Y - dragCursorStart.Y;
            if (Math.Abs(dx) > 5 || Math.Abs(dy) > 5)
            {
                if (!dragMoved)
                {
                    dragMoved = true;
                    MoveState = "drag";
                    CurChar.CurrentExpr = "expr_4_surprised";
                    Say("哇啊啊⚡！主人要把我拎去螢幕哪裡？！", 120);
                }
                PosX = dragFormStart.X + dx;
                PosY = dragFormStart.Y + dy;
                this.Location = new Point((int)PosX, (int)PosY);
            }
        }

        private void OnPetMouseUp(object sender, MouseEventArgs e)
        {
            if (!isDragging) return;
            isDragging = false;
            if (dragMoved)
            {
                if (PinInAirMode)
                {
                    FloorY = PosY;
                    MoveState = AutoWalkEnabled ? "walk" : "idle";
                    CurChar.CurrentExpr = "expr_2_happy";
                    Say("📌 已固定在這個高度陪你囉 ✨", 110);
                }
                else if (PosY < FloorY - 12)
                {
                    MoveState = "fall";
                    VelY = 1.0f;
                }
                else
                {
                    PosY = FloorY;
                    MoveState = AutoWalkEnabled ? "walk" : "idle";
                    CurChar.CurrentExpr = "expr_2_happy";
                }
            }
            else
            {
                TriggerInteraction("pat");
            }
        }

        private void OnPetMouseDoubleClick(object sender, MouseEventArgs e)
        {
            OpenNativeChatAndStatusDialog();
        }

        public void TriggerInteraction(string action)
        {
            CharState c = CurChar;
            if (action == "pat")
            {
                c.Affection += 3;
                c.CurrentExpr = "expr_5_shy";
                MoveState = "jump";
                VelY = -8.5f;
                SpawnParticles("💕", 6, Color.HotPink);
                Say(string.Format("嘿嘿～被主人摸摸頭好開心 💕 好感度 +3（目前 {0}）！", c.Affection));
            }
            else if (action == "poke")
            {
                c.CurrentExpr = "expr_3_angry";
                SpawnParticles("💢", 6, Color.Crimson);
                Say("喂💢！不要一直戳我的臉啦！我會生氣喔！");
            }
            else if (action == "bath")
            {
                c.Dirtiness = 0;
                c.Affection += 5;
                c.CurrentExpr = "expr_2_happy";
                SpawnParticles("🫧", 7, Color.Cyan);
                Say("洗完香噴噴的泡泡浴囉 ✨ 髒污值歸零，好感度 +5！");
            }
            else if (action == "rest")
            {
                c.Stamina = Math.Min(100, c.Stamina + 35);
                c.Fatigue = Math.Max(0, c.Fatigue - 40);
                c.CurrentExpr = "expr_1_normal";
                SpawnParticles("💤", 5, Color.LightSkyBlue);
                Say(string.Format("休息充電完成 ✨ 體力恢復 +35（目前體力 {0}/100）！", c.Stamina));
            }
            SaveData();
        }

        public void CycleExpression()
        {
            string[] list = new string[] {
                "expr_1_normal", "expr_2_happy", "expr_3_angry",
                "expr_4_surprised", "expr_5_shy", "expr_6_focused", "expr_7_sick"
            };
            int idx = Array.IndexOf(list, CurChar.CurrentExpr);
            CurChar.CurrentExpr = list[(idx + 1) % list.Length];
            SpawnParticles("✨", 4, Color.Gold);
        }

        public void TogglePomodoro()
        {
            if (PomoRunning)
            {
                PomoRunning = false;
                CurChar.CurrentExpr = "expr_1_normal";
                Say("⏹️ 番茄鐘已中途停止，未獲得智慧經驗值。");
                return;
            }
            if (CurChar.Stamina < 20)
            {
                CurChar.CurrentExpr = "expr_7_sick";
                Say("⚠️ 體力不足 20 點！無法啟動番茄鐘，請先點右鍵【💤休息充電】或去【🏪商店】買飲料補充體力喔！");
                return;
            }
            PomoRunning = true;
            PomoRemainingSec = 1800;
            pomoTickCounter = 0;
            CurChar.CurrentExpr = "expr_6_focused";
            SpawnParticles("💡", 6, Color.Cyan);
            Say("🍅 30分鐘番茄鐘啟動！進入極限專注狀態 💡（完成可獲 +15 智慧經驗值，消耗 -20 體力值）");
        }

        public void CompletePomodoroSession()
        {
            PomoRunning = false;
            PomoRemainingSec = 1800;
            CharState c = CurChar;
            c.WisdomExp += 15;
            c.Stamina = Math.Max(0, c.Stamina - 20);
            c.PomodoroCount += 1;
            c.CurrentExpr = "expr_2_happy";
            MoveState = "jump";
            VelY = -10f;
            SpawnParticles("🎓", 8, Color.Gold);

            string achMsg = "";
            int[] thresholds = new int[] { 15, 45, 90, 150, 300 };
            string[] titles = new string[] { "初級專注學徒", "進階時間管理大師", "高階電競智多星", "傳奇智慧領航員", "Create or Destroy 宗師" };
            for (int i = 0; i < thresholds.Length; i++)
            {
                if (c.WisdomExp >= thresholds[i] && !UnlockedAchievements.Contains(titles[i]))
                {
                    UnlockedAchievements.Add(titles[i]);
                    Coins += 20;
                    achMsg = string.Format(" 🏆解鎖成就【{0}】(+20金幣)！", titles[i]);
                }
            }

            SaveData();
            Say(string.Format("🎉 完成 30 分鐘番茄鐘！智慧經驗 +15（累計 {0}），體力 -20（剩餘 {1}）！{2}", c.WisdomExp, c.Stamina, achMsg), 260);
        }

        private void BuildContextMenu()
        {
            petMenu = new ContextMenuStrip();
            petMenu.Font = new Font("Microsoft JhengHei UI", 9.5f, FontStyle.Bold);

            petMenu.Items.Add("🐾 切換：自動在桌面散步走動 / 固定原地", null, delegate {
                AutoWalkEnabled = !AutoWalkEnabled;
                MoveState = AutoWalkEnabled ? "walk" : "idle";
                Say(AutoWalkEnabled ? "🐾 已開啟【自動在桌面散步走動】模式 ✨" : "📌 已切換為【乖乖站在原地】模式！");
            });

            petMenu.Items.Add("🧲 切換：落地工作列模式 / 允許懸浮螢幕任意高度", null, delegate {
                PinInAirMode = !PinInAirMode;
                if (!PinInAirMode) { MoveState = "fall"; VelY = 1.0f; }
                Say(PinInAirMode ? "📌 已開啟【自由高度懸浮】，拖曳到哪裡就會停在哪裡！" : "🧲 已開啟【物理重力落地】，放開會自動降落工作列上方！");
            });

            petMenu.Items.Add("🎨 切換：Q版二頭身大頭模式 / 原比例全身立繪模式", null, delegate {
                ChibiBigHeadMode = !ChibiBigHeadMode;
                Say(ChibiBigHeadMode ? "✨ 已切換為【Q版二頭身大頭模式】，浮誇表情更明顯囉！" : "🧍 已切換為【原比例全身立繪模式】！");
            });

            petMenu.Items.Add("🔄 切換角色：雪靈 (Xueling) ⇄ 凌風 (Ling Feng)", null, delegate {
                ActiveChar = (ActiveChar == "xueling") ? "lingfeng" : "xueling";
                MoveState = "jump"; VelY = -9.5f;
                SpawnParticles("✨", 6, Color.Cyan);
                Say(ActiveChar == "xueling" ? "❄️ 雪靈報到！我會在桌面上陪你一起學習與冒險 ✨" : "🏎️ 凌風就位！需要專注衝刺或擲骰子對決隨時找我！");
                SaveData();
            });

            petMenu.Items.Add("🏎️ 切換凌風 BMW 賽車姿勢 / 正面立繪", null, delegate {
                if (ActiveChar != "lingfeng") ActiveChar = "lingfeng";
                CurChar.CurrentView = (CurChar.CurrentView == "racing") ? "front" : "racing";
                Say(CurChar.CurrentView == "racing" ? "🏎️💨 引擎全開！切換為 BMW 藍色跑車駕駛模式！" : "🧍 已切回凌風正面立繪模式！");
            });

            petMenu.Items.Add(new ToolStripSeparator());

            ToolStripMenuItem exprMenu = new ToolStripMenuItem("🎭 切換 7 種誇張動漫表情");
            exprMenu.DropDownItems.Add("1. 普通 (Normal)", null, delegate { CurChar.CurrentExpr = "expr_1_normal"; });
            exprMenu.DropDownItems.Add("2. 超開心閃耀 (Happy ✨)", null, delegate { CurChar.CurrentExpr = "expr_2_happy"; SpawnParticles("✨", 6, Color.Gold); });
            exprMenu.DropDownItems.Add("3. 暴怒爆青筋 (Angry 💢)", null, delegate { CurChar.CurrentExpr = "expr_3_angry"; SpawnParticles("💢", 6, Color.Crimson); });
            exprMenu.DropDownItems.Add("4. 大震驚雷擊 (Shocked ⚡)", null, delegate { CurChar.CurrentExpr = "expr_4_surprised"; SpawnParticles("⚡", 6, Color.Yellow); });
            exprMenu.DropDownItems.Add("5. 害羞冒愛心 (Shy 💕)", null, delegate { CurChar.CurrentExpr = "expr_5_shy"; SpawnParticles("💕", 6, Color.HotPink); });
            exprMenu.DropDownItems.Add("6. 番茄鐘極限專注 (Focused 💡)", null, delegate { CurChar.CurrentExpr = "expr_6_focused"; SpawnParticles("💡", 6, Color.Cyan); });
            exprMenu.DropDownItems.Add("7. 重感冒/腸胃炎 (Sick 🤒)", null, delegate { CurChar.CurrentExpr = "expr_7_sick"; SpawnParticles("🤒", 6, Color.OrangeRed); });
            petMenu.Items.Add(exprMenu);

            ToolStripMenuItem actMenu = new ToolStripMenuItem("👋 親密照顧互動 (摸頭/洗澡/休息)");
            actMenu.DropDownItems.Add("👋 摸摸頭 (+3 好感度)", null, delegate { TriggerInteraction("pat"); });
            actMenu.DropDownItems.Add("💢 戳戳臉 (暴怒反應)", null, delegate { TriggerInteraction("poke"); });
            actMenu.DropDownItems.Add("🛁 洗泡泡浴 (髒污歸零/+5好感)", null, delegate { TriggerInteraction("bath"); });
            actMenu.DropDownItems.Add("💤 休息充電 (+35 體力值)", null, delegate { TriggerInteraction("rest"); });
            actMenu.DropDownItems.Add("🤒 [測試] 模擬角色感冒生病", null, delegate {
                CurChar.Health = "cold"; CurChar.CurrentExpr = "expr_7_sick";
                Say("哈啾🤒……頭好暈喔，好像感冒發燒了，快去【🏪商店】買感冒藥救我！");
            });
            petMenu.Items.Add(actMenu);

            petMenu.Items.Add(new ToolStripSeparator());

            petMenu.Items.Add("🍅 啟動 / 停止 30 分鐘番茄鐘 (+15智慧 / -20體力)", null, delegate { TogglePomodoro(); });
            petMenu.Items.Add("⚡ [快速測試] 立即完成番茄鐘 (+15智慧 / -20體力)", null, delegate {
                if (CurChar.Stamina < 20) { Say("⚠️ 體力不足 20 點！請先休息充電或買飲料補充體力！"); return; }
                CompletePomodoroSession();
            });

            petMenu.Items.Add("🏪 打開【Create or Destroy 島民商店 (23種道具)】", null, delegate { OpenNativeShopDialog(); });
            petMenu.Items.Add("🎲 打開【Discord 每日打卡 & 多人同輪骰子 (+5/+1 EXP)】", null, delegate { OpenNativeDiscordDialog(); });
            petMenu.Items.Add("💬 打開【AI 角色對話 & 六維養成狀態視窗】", null, delegate { OpenNativeChatAndStatusDialog(); });

            petMenu.Items.Add(new ToolStripSeparator());
            petMenu.Items.Add("❌ 結束桌面寵物程式", null, delegate {
                trayIcon.Visible = false;
                SaveData();
                Application.Exit();
            });
        }

        private void InitTrayIcon()
        {
            trayIcon = new NotifyIcon();
            trayIcon.Text = "Create or Destroy — 雪靈 & 凌風 桌面寵物 (右鍵開啟選單)";
            trayIcon.Icon = SystemIcons.Application;
            trayIcon.ContextMenuStrip = petMenu;
            trayIcon.Visible = true;
            trayIcon.BalloonTipTitle = "⚡ Create or Destroy 桌面寵物已啟動";
            trayIcon.BalloonTipText = "雪靈正在您的電腦桌面上散步！左鍵可拎起拖曳，右鍵點擊角色或此圖示可展開完整選單。";
            trayIcon.ShowBalloonTip(3000);
            trayIcon.DoubleClick += delegate {
                this.Activate();
                Say("主人我在這裡喔 ✨！");
            };
        }

        public void OpenNativeShopDialog()
        {
            Form dlg = new Form();
            dlg.Text = "🏪 Create or Destroy 島民商店 (23種完整道具 & 醫療系統)";
            dlg.Size = new Size(560, 520);
            dlg.StartPosition = FormStartPosition.CenterScreen;
            dlg.BackColor = Color.FromArgb(15, 23, 42);
            dlg.ForeColor = Color.White;
            dlg.Font = new Font("Microsoft JhengHei UI", 9.5f, FontStyle.Regular);
            dlg.TopMost = true;

            Label lblTop = new Label();
            lblTop.Dock = DockStyle.Top;
            lblTop.Height = 42;
            lblTop.TextAlign = ContentAlignment.MiddleLeft;
            lblTop.Padding = new Padding(12, 0, 0, 0);
            lblTop.Font = new Font("Microsoft JhengHei UI", 10.5f, FontStyle.Bold);
            lblTop.ForeColor = Color.Gold;
            Action updateHeader = delegate {
                lblTop.Text = string.Format("🪙 島民金幣：{0} 枚  |  💎 可兌換 EXP：{1:0.0}  |  目前照顧：{2} (恢復經驗 {3})", Coins, AvailableExp, CurChar.Name, CurChar.RecoveryExp);
            };
            updateHeader();

            FlowLayoutPanel flow = new FlowLayoutPanel();
            flow.Dock = DockStyle.Fill;
            flow.AutoScroll = true;
            flow.Padding = new Padding(10);

            foreach (ShopItem item in ShopCatalog)
            {
                ShopItem curItem = item;
                Panel card = new Panel();
                card.Size = new Size(505, 58);
                card.BackColor = curItem.TriggersGastro ? Color.FromArgb(55, 20, 32) : Color.FromArgb(26, 38, 64);
                card.Margin = new Padding(4);

                Label lName = new Label();
                lName.Text = string.Format("【{0}】{1}  —  🪙 {2} 金幣", curItem.Category, curItem.Name, curItem.Price);
                lName.Font = new Font("Microsoft JhengHei UI", 9.5f, FontStyle.Bold);
                lName.ForeColor = curItem.TriggersGastro ? Color.LightCoral : Color.Cyan;
                lName.Location = new Point(10, 7);
                lName.AutoSize = true;

                Label lDesc = new Label();
                lDesc.Text = curItem.Desc;
                lDesc.ForeColor = Color.Silver;
                lDesc.Location = new Point(10, 31);
                lDesc.AutoSize = true;

                Button btnBuy = new Button();
                btnBuy.Text = "購買並使用";
                btnBuy.Size = new Size(105, 36);
                btnBuy.Location = new Point(388, 11);
                btnBuy.BackColor = Color.FromArgb(0, 180, 216);
                btnBuy.ForeColor = Color.White;
                btnBuy.FlatStyle = FlatStyle.Flat;
                btnBuy.Click += delegate {
                    if (Coins < curItem.Price)
                    {
                        MessageBox.Show("島民金幣不足！可至【🎲 Discord 骰子】打卡或用 50 EXP 兌換 25 金幣喔！", "金幣不足");
                        return;
                    }
                    Coins -= curItem.Price;
                    CharState c = CurChar;
                    c.RecoveryExp += curItem.Recovery;
                    c.Hunger = Math.Max(0, Math.Min(100, c.Hunger - curItem.HungerRelief));
                    c.Stamina = Math.Max(0, Math.Min(100, c.Stamina + curItem.StaminaRelief));

                    if (curItem.TriggersGastro)
                    {
                        c.Health = "gastroenteritis";
                        c.GastroDaysRemaining = 3;
                        c.GastroCourseActive = false;
                        c.CurrentExpr = "expr_7_sick";
                        SpawnParticles("🤢", 7, Color.LimeGreen);
                        Say("🤢 肚子好痛！喝了【不知放多少天的飲料】觸發 3 天腸胃炎了！快買【🏥腸胃藥三天份】救我！");
                    }
                    else if (curItem.CuresCold)
                    {
                        if (c.Health == "cold") c.Health = "healthy";
                        c.CurrentExpr = "expr_2_happy";
                        SpawnParticles("💊", 6, Color.Gold);
                        Say("💊 服用感冒藥後退燒康復了 ✨ 恢復經驗值 +" + curItem.Recovery + "！");
                    }
                    else if (curItem.CuresGastro3D)
                    {
                        c.GastroCourseActive = true;
                        c.Health = "healthy";
                        c.GastroDaysRemaining = 0;
                        c.CurrentExpr = "expr_2_happy";
                        SpawnParticles("🏥", 7, Color.Cyan);
                        Say("🏥 已服用【腸胃藥三天份】（恢復經驗 +100），腸胃炎已順利治癒康復 ✨！");
                    }
                    else
                    {
                        c.CurrentExpr = "expr_2_happy";
                        SpawnParticles("✨", 5, Color.Gold);
                        Say(string.Format("好美味！使用了 {0}，恢復經驗 {1}，體力 {2}/100 ✨", curItem.Name, curItem.Recovery >= 0 ? "+" + curItem.Recovery : curItem.Recovery.ToString(), c.Stamina));
                    }
                    SaveData();
                    updateHeader();
                };

                card.Controls.Add(lName);
                card.Controls.Add(lDesc);
                card.Controls.Add(btnBuy);
                flow.Controls.Add(card);
            }

            dlg.Controls.Add(flow);
            dlg.Controls.Add(lblTop);
            dlg.Show();
        }

        public void OpenNativeDiscordDialog()
        {
            Form dlg = new Form();
            dlg.Text = "🎲 Discord 頻道連動：打卡 & 多人同輪骰子派對";
            dlg.Size = new Size(500, 420);
            dlg.StartPosition = FormStartPosition.CenterScreen;
            dlg.BackColor = Color.FromArgb(18, 25, 46);
            dlg.ForeColor = Color.White;
            dlg.Font = new Font("Microsoft JhengHei UI", 9.5f, FontStyle.Regular);
            dlg.TopMost = true;

            Label lblStats = new Label();
            lblStats.Location = new Point(16, 14);
            lblStats.Size = new Size(460, 30);
            lblStats.Font = new Font("Microsoft JhengHei UI", 10.5f, FontStyle.Bold);
            lblStats.ForeColor = Color.Cyan;

            TextBox txtLog = new TextBox();
            txtLog.Multiline = true;
            txtLog.ReadOnly = true;
            txtLog.ScrollBars = ScrollBars.Vertical;
            txtLog.Location = new Point(16, 170);
            txtLog.Size = new Size(452, 195);
            txtLog.BackColor = Color.FromArgb(10, 15, 28);
            txtLog.ForeColor = Color.White;
            txtLog.Font = new Font("Consolas", 10f);
            txtLog.Text = "⚡ 歡迎來到 Create or Destroy Discord 互動頻道！\r\n" +
                          "• 單獨一人骰骰子：每次獲得 +1 EXP\r\n" +
                          "• 多人一起同輪骰骰子：點數最大獲勝者獲得 +5 EXP！\r\n" +
                          "• 每 50 點 EXP 可兌換 25 枚島民商店金幣！\r\n";

            Action refreshStats = delegate {
                lblStats.Text = string.Format("✨ 總經驗：{0:0.0} EXP  |  💎 可兌換：{1:0.0} EXP  |  🪙 金幣：{2}", TotalExp, AvailableExp, Coins);
            };
            refreshStats();

            Button btnCheckin = new Button();
            btnCheckin.Text = "📅 每日打卡 (+20 EXP)";
            btnCheckin.Location = new Point(16, 55);
            btnCheckin.Size = new Size(218, 44);
            btnCheckin.BackColor = Color.FromArgb(40, 167, 69);
            btnCheckin.FlatStyle = FlatStyle.Flat;
            btnCheckin.Click += delegate {
                TotalExp += 20; AvailableExp += 20; StreakDays += 1;
                string m = string.Format("✅ 【每日打卡成功】獲得 +20 EXP！（連續打卡 {0} 天）", StreakDays);
                txtLog.AppendText("\r\n" + m);
                Say(m); SpawnParticles("📅", 5, Color.Lime);
                SaveData(); refreshStats();
            };

            Button btnExch = new Button();
            btnExch.Text = "🪙 50 EXP 兌換 25 金幣";
            btnExch.Location = new Point(250, 55);
            btnExch.Size = new Size(218, 44);
            btnExch.BackColor = Color.FromArgb(218, 145, 0);
            btnExch.FlatStyle = FlatStyle.Flat;
            btnExch.Click += delegate {
                if (AvailableExp < 50) { MessageBox.Show("可兌換 EXP 不足 50 點！快去打卡或擲骰子累積吧！"); return; }
                AvailableExp -= 50; Coins += 25;
                string m = "🪙 成功消耗 50 EXP 兌換 +25 枚島民商店金幣！";
                txtLog.AppendText("\r\n" + m);
                Say(m); SpawnParticles("🪙", 6, Color.Gold);
                SaveData(); refreshStats();
            };

            Button btnSolo = new Button();
            btnSolo.Text = "🎲 單人骰骰子 (+1 EXP)";
            btnSolo.Location = new Point(16, 110);
            btnSolo.Size = new Size(218, 46);
            btnSolo.BackColor = Color.FromArgb(0, 140, 210);
            btnSolo.FlatStyle = FlatStyle.Flat;
            btnSolo.Click += delegate {
                int r = rng.Next(1, 7);
                TotalExp += 1; AvailableExp += 1;
                string m = string.Format("🎲 【單人骰骰子】你擲出了 {0} 點！單獨一人骰獲得 +1 EXP！", r);
                txtLog.AppendText("\r\n" + m);
                Say(m); SpawnParticles("🎲", 5, Color.Cyan);
                SaveData(); refreshStats();
            };

            Button btnMulti = new Button();
            btnMulti.Text = "🎲🏆 多人同輪比大小 (最高點 +5 EXP)";
            btnMulti.Location = new Point(250, 110);
            btnMulti.Size = new Size(218, 46);
            btnMulti.BackColor = Color.FromArgb(138, 43, 226);
            btnMulti.FlatStyle = FlatStyle.Flat;
            btnMulti.Click += delegate {
                int pRoll = rng.Next(6, 13);
                int b1Roll = rng.Next(2, 12);
                int b2Roll = rng.Next(2, 12);
                int maxR = Math.Max(pRoll, Math.Max(b1Roll, b2Roll));
                bool won = (pRoll == maxR);
                if (won) { TotalExp += 5; AvailableExp += 5; }
                string m = string.Format(
                    "🎲 【多人同輪骰子】你:{0}點 | 雪靈:{1}點 | 凌風:{2}點 ➔ {3}",
                    pRoll, b1Roll, b2Roll,
                    won ? "👑你擲出同輪最高點！獲得 +5 EXP！" : "本輪由夥伴最高點勝出，再骰一次搶 +5 EXP！"
                );
                txtLog.AppendText("\r\n" + m);
                CurChar.CurrentExpr = won ? "expr_2_happy" : "expr_4_surprised";
                Say(m); SpawnParticles("🏆", 7, Color.Gold);
                SaveData(); refreshStats();
            };

            dlg.Controls.Add(lblStats);
            dlg.Controls.Add(btnCheckin);
            dlg.Controls.Add(btnExch);
            dlg.Controls.Add(btnSolo);
            dlg.Controls.Add(btnMulti);
            dlg.Controls.Add(txtLog);
            dlg.Show();
        }

        public void OpenNativeChatAndStatusDialog()
        {
            Form dlg = new Form();
            dlg.Text = "💬 與桌寵 AI 對話 & 六維養成狀態 — " + CurChar.Name;
            dlg.Size = new Size(480, 440);
            dlg.StartPosition = FormStartPosition.CenterScreen;
            dlg.BackColor = Color.FromArgb(15, 23, 42);
            dlg.ForeColor = Color.White;
            dlg.Font = new Font("Microsoft JhengHei UI", 9.5f, FontStyle.Regular);
            dlg.TopMost = true;

            CharState c = CurChar;
            Label lblInfo = new Label();
            lblInfo.Location = new Point(14, 12);
            lblInfo.Size = new Size(440, 52);
            lblInfo.ForeColor = Color.Aquamarine;
            lblInfo.Font = new Font("Microsoft JhengHei UI", 9.5f, FontStyle.Bold);
            lblInfo.Text = string.Format(
                "🌟 {0} Lv.{1}  |  ❤️ 好感：{2}  |  🧠 智慧經驗：{3} (完成 {4} 次番茄鐘)\r\n⚡ 體力：{5}/100  |  💚 恢復經驗：{6}  |  🩺 健康：{7}",
                c.Name, c.GetLevel(TotalExp), c.Affection, c.WisdomExp, c.PomodoroCount, c.Stamina, c.RecoveryExp, c.Health
            );

            TextBox txtChat = new TextBox();
            txtChat.Multiline = true;
            txtChat.ReadOnly = true;
            txtChat.ScrollBars = ScrollBars.Vertical;
            txtChat.Location = new Point(14, 70);
            txtChat.Size = new Size(436, 260);
            txtChat.BackColor = Color.FromArgb(10, 15, 28);
            txtChat.ForeColor = Color.White;
            txtChat.Text = string.Format("【{0}】：{1}\r\n", c.Name, SpeechText);

            TextBox txtInput = new TextBox();
            txtInput.Location = new Point(14, 344);
            txtInput.Size = new Size(330, 32);
            txtInput.BackColor = Color.FromArgb(28, 40, 68);
            txtInput.ForeColor = Color.White;

            Button btnSend = new Button();
            btnSend.Text = "發送對話";
            btnSend.Location = new Point(352, 341);
            btnSend.Size = new Size(98, 34);
            btnSend.BackColor = Color.FromArgb(0, 180, 216);
            btnSend.FlatStyle = FlatStyle.Flat;

            EventHandler sendAction = delegate {
                string msg = txtInput.Text.Trim();
                if (string.IsNullOrEmpty(msg)) return;
                txtInput.Text = "";
                txtChat.AppendText("\r\n【你】：" + msg + "\r\n");

                string reply;
                if (msg.Contains("累") || msg.Contains("休息"))
                {
                    CurChar.CurrentExpr = "expr_5_shy";
                    reply = "辛苦了主人 💕 工作累了就按右鍵點【💤休息充電】或去買杯珍珠奶茶犒賞自己吧！";
                }
                else if (msg.Contains("番茄") || msg.Contains("讀書") || msg.Contains("工作") || msg.Contains("專注"))
                {
                    CurChar.CurrentExpr = "expr_6_focused";
                    reply = "沒問題 💡 點擊我腳下的【🍅番茄鐘】，我馬上在桌面頭頂幫你倒數 30 分鐘（+15智慧 / -20體力）！";
                }
                else if (msg.Contains("餓") || msg.Contains("吃") || msg.Contains("飲料"))
                {
                    CurChar.CurrentExpr = "expr_2_happy";
                    reply = "好耶 ✨ 快點開【🏪商店】買便當或蛋糕，但千萬別買到『不知放多少天的飲料』喔，會得腸胃炎的！";
                }
                else
                {
                    CurChar.CurrentExpr = "expr_2_happy";
                    reply = string.Format("收到你的訊息：「{0}」✨ 我會一直在你的 Windows 桌面上散步陪著你！（好感度 +1）", msg);
                    CurChar.Affection += 1;
                }
                txtChat.AppendText(string.Format("【{0}】：{1}\r\n", CurChar.Name, reply));
                Say(reply, 220);
                SpawnParticles("💬", 5, Color.Cyan);
                SaveData();
            };

            btnSend.Click += sendAction;
            txtInput.KeyDown += delegate(object s, KeyEventArgs ke) {
                if (ke.KeyCode == Keys.Enter) { ke.SuppressKeyPress = true; sendAction(s, ke); }
            };

            dlg.Controls.Add(lblInfo);
            dlg.Controls.Add(txtChat);
            dlg.Controls.Add(txtInput);
            dlg.Controls.Add(btnSend);
            dlg.Show();
        }
    }

    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new TransparentPetForm());
        }
    }
}
"""


def make_coff_idata_obj(dll_imports):
    """
    Generates a standard x86-64 COFF (.obj) file with a .idata$2 section, COFF RVA relocations
    (IMAGE_REL_AMD64_ADDR32NB = 3), and global __imp_<func> symbols for GNU ld -m i386pep.
    """
    num_dlls = len(dll_imports)
    idt_size = (num_dlls + 1) * 20
    total_funcs = sum(len(funcs) for _, funcs in dll_imports)
    ilt_offset = idt_size
    ilt_size = (total_funcs + num_dlls) * 8
    iat_offset = ilt_offset + ilt_size
    iat_size = ilt_size
    strings_offset = iat_offset + iat_size

    sec_data = bytearray(strings_offset)
    str_blob = bytearray()
    relocs = []
    func_hn_offsets = {}
    dll_name_offsets = {}

    for dll_name, funcs in dll_imports:
        d_off = strings_offset + len(str_blob)
        dll_name_offsets[dll_name] = d_off
        str_blob += dll_name.encode("ascii") + b"\x00"
        if len(str_blob) % 2:
            str_blob += b"\x00"
        for fn in funcs:
            f_off = strings_offset + len(str_blob)
            func_hn_offsets[(dll_name, fn)] = f_off
            str_blob += b"\x00\x00" + fn.encode("ascii") + b"\x00"
            if len(str_blob) % 2:
                str_blob += b"\x00"

    sec_data += str_blob
    cur_ilt = ilt_offset
    cur_iat = iat_offset
    iat_sym_offsets = {}

    for dll_idx, (dll_name, funcs) in enumerate(dll_imports):
        idt_pos = dll_idx * 20
        struct.pack_into("<I", sec_data, idt_pos + 0, cur_ilt)
        relocs.append((idt_pos + 0, 0, 3))
        struct.pack_into("<I", sec_data, idt_pos + 12, dll_name_offsets[dll_name])
        relocs.append((idt_pos + 12, 0, 3))
        struct.pack_into("<I", sec_data, idt_pos + 16, cur_iat)
        relocs.append((idt_pos + 16, 0, 3))

        for fn in funcs:
            hn_off = func_hn_offsets[(dll_name, fn)]
            struct.pack_into("<Q", sec_data, cur_ilt, hn_off)
            relocs.append((cur_ilt, 0, 3))
            struct.pack_into("<Q", sec_data, cur_iat, hn_off)
            relocs.append((cur_iat, 0, 3))
            iat_sym_offsets[fn] = cur_iat
            cur_ilt += 8
            cur_iat += 8
        cur_ilt += 8
        cur_iat += 8

    symtab = bytearray()
    strtab = bytearray(b"\x00\x00\x00\x00")

    def add_sym(name, value, sec_num, sclass):
        name_b = name.encode("ascii")
        if len(name_b) <= 8:
            name_field = name_b.ljust(8, b"\x00")
        else:
            str_off = len(strtab)
            strtab.extend(name_b + b"\x00")
            name_field = struct.pack("<II", 0, str_off)
        symtab.extend(name_field + struct.pack("<IHHBB", value, sec_num, 0, sclass, 0))

    add_sym(".idata$2", 0, 1, 3)
    for _, funcs in dll_imports:
        for fn in funcs:
            add_sym(f"__imp_{fn}", iat_sym_offsets[fn], 1, 2)
    struct.pack_into("<I", strtab, 0, len(strtab))
    reloc_bytes = bytearray()
    for r_va, r_sym, r_type in relocs:
        reloc_bytes += struct.pack("<IIH", r_va, r_sym, r_type)

    raw_data_ptr = 60
    reloc_ptr = raw_data_ptr + len(sec_data)
    symtab_ptr = reloc_ptr + len(reloc_bytes)
    num_syms = 1 + total_funcs
    coff_hdr = struct.pack("<HHIIIHH", 0x8664, 1, 0, symtab_ptr, num_syms, 0, 0)
    sec_hdr = struct.pack("<8sIIIIIIHHI", b".idata$2", 0, 0, len(sec_data), raw_data_ptr, reloc_ptr, 0, len(relocs), 0, 0xC0400040)
    return coff_hdr + sec_hdr + sec_data + reloc_bytes + symtab + strtab, iat_offset, iat_size


def patch_pe64_writable_idata_and_checksum(exe_path, iat_offset, iat_size):
    pe = bytearray(open(exe_path, "rb").read())
    pe_off = struct.unpack_from("<I", pe, 0x3C)[0]
    num_secs = struct.unpack_from("<H", pe, pe_off + 6)[0]
    opt_size = struct.unpack_from("<H", pe, pe_off + 20)[0]
    opt_off = pe_off + 24
    sec_table_off = opt_off + opt_size

    idata_rva = 0
    for i in range(num_secs):
        sh_off = sec_table_off + i * 40
        name = bytes(pe[sh_off:sh_off + 8]).rstrip(b"\x00")
        if name in (b".idata", b".data", b".bss"):
            chars = struct.unpack_from("<I", pe, sh_off + 36)[0]
            struct.pack_into("<I", pe, sh_off + 36, chars | 0x80000000)
            if name == b".idata":
                idata_rva = struct.unpack_from("<I", pe, sh_off + 12)[0]

    if idata_rva:
        struct.pack_into("<II", pe, opt_off + 112 + 12 * 8, idata_rva + iat_offset, iat_size)

    # Recompute standard PE CheckSum (at opt_off + 64)
    struct.pack_into("<I", pe, opt_off + 64, 0)
    if len(pe) % 2:
        pe.append(0)
    chk = 0
    for i in range(0, len(pe), 2):
        val = struct.unpack_from("<H", pe, i)[0]
        chk += val
        chk = (chk & 0xFFFF) + (chk >> 16)
    chk = (chk & 0xFFFF) + (chk >> 16)
    chk += len(pe)
    struct.pack_into("<I", pe, opt_off + 64, chk)
    open(exe_path, "wb").write(pe)


NATIVE_WIN64_LAUNCHER_C = r"""
typedef unsigned short WCHAR;
typedef unsigned int DWORD;
typedef int BOOL;
typedef void* HANDLE;

typedef struct _STARTUPINFOW {
    DWORD cb;
    WCHAR *lpReserved;
    WCHAR *lpDesktop;
    WCHAR *lpTitle;
    DWORD dwX;
    DWORD dwY;
    DWORD dwXSize;
    DWORD dwYSize;
    DWORD dwXCountChars;
    DWORD dwYCountChars;
    DWORD dwFillAttribute;
    DWORD dwFlags;
    unsigned short wShowWindow;
    unsigned short cbReserved2;
    unsigned char *lpReserved2;
    HANDLE hStdInput;
    HANDLE hStdOutput;
    HANDLE hStdError;
} STARTUPINFOW;

typedef struct _PROCESS_INFORMATION {
    HANDLE hProcess;
    HANDLE hThread;
    DWORD dwProcessId;
    DWORD dwThreadId;
} PROCESS_INFORMATION;

__attribute__((visibility("hidden"))) extern __attribute__((ms_abi)) DWORD (*__imp_GetEnvironmentVariableW)(const WCHAR*, WCHAR*, DWORD);
__attribute__((visibility("hidden"))) extern __attribute__((ms_abi)) BOOL  (*__imp_CreateDirectoryW)(const WCHAR*, void*);
__attribute__((visibility("hidden"))) extern __attribute__((ms_abi)) HANDLE (*__imp_CreateFileW)(const WCHAR*, DWORD, DWORD, void*, DWORD, DWORD, HANDLE);
__attribute__((visibility("hidden"))) extern __attribute__((ms_abi)) BOOL  (*__imp_WriteFile)(HANDLE, const void*, DWORD, DWORD*, void*);
__attribute__((visibility("hidden"))) extern __attribute__((ms_abi)) BOOL  (*__imp_CloseHandle)(HANDLE);
__attribute__((visibility("hidden"))) extern __attribute__((ms_abi)) DWORD (*__imp_GetFileAttributesW)(const WCHAR*);
__attribute__((visibility("hidden"))) extern __attribute__((ms_abi)) BOOL  (*__imp_CopyFileW)(const WCHAR*, const WCHAR*, BOOL);
__attribute__((visibility("hidden"))) extern __attribute__((ms_abi)) BOOL  (*__imp_CreateProcessW)(const WCHAR*, WCHAR*, void*, void*, BOOL, DWORD, void*, const WCHAR*, STARTUPINFOW*, PROCESS_INFORMATION*);
__attribute__((visibility("hidden"))) extern __attribute__((ms_abi)) DWORD (*__imp_WaitForSingleObject)(HANDLE, DWORD);
__attribute__((visibility("hidden"))) extern __attribute__((ms_abi)) void  (*__imp_ExitProcess)(unsigned int);
__attribute__((visibility("hidden"))) extern __attribute__((ms_abi)) int   (*__imp_MessageBoxW)(void*, const WCHAR*, const WCHAR*, unsigned int);

__attribute__((visibility("hidden"))) extern const unsigned char g_cs_data[];
__attribute__((visibility("hidden"))) extern const unsigned int g_cs_size;
__attribute__((visibility("hidden"))) extern const unsigned char g_bin_data[];
__attribute__((visibility("hidden"))) extern const unsigned int g_bin_size;

/* Keep all buffers in .data so stack frame stays tiny (<128 bytes) and never hits Windows 4KB stack guard page */
__attribute__((section(".data"))) static WCHAR g_appDir[520] = {1};
__attribute__((section(".data"))) static WCHAR g_csPath[520] = {1};
__attribute__((section(".data"))) static WCHAR g_binPath[520] = {1};
__attribute__((section(".data"))) static WCHAR g_outExe[520] = {1};
__attribute__((section(".data"))) static WCHAR g_cmdLine[2048] = {1};
__attribute__((section(".data"))) static STARTUPINFOW g_si = {sizeof(STARTUPINFOW)};
__attribute__((section(".data"))) static PROCESS_INFORMATION g_pi = {0};

static void w_copy(WCHAR *dst, const WCHAR *src) {
    while (*src) { *dst++ = *src++; }
    *dst = 0;
}

static void w_cat(WCHAR *dst, const WCHAR *src) {
    while (*dst) dst++;
    while (*src) { *dst++ = *src++; }
    *dst = 0;
}

static BOOL write_file_bytes(const WCHAR *path, const unsigned char *data, DWORD size) {
    HANDLE h = __imp_CreateFileW(path, 0x40000000U /* GENERIC_WRITE */, 0, 0, 2 /* CREATE_ALWAYS */, 0x80 /* FILE_ATTRIBUTE_NORMAL */, 0);
    if (h == (HANDLE)(long long)-1) return 0;
    DWORD written = 0;
    BOOL ok = __imp_WriteFile(h, data, size, &written, 0);
    __imp_CloseHandle(h);
    return ok && (written == size);
}

static void zero_mem(void *ptr, unsigned int n) {
    unsigned char *p = (unsigned char *)ptr;
    for (unsigned int i = 0; i < n; i++) p[i] = 0;
}

__attribute__((ms_abi)) int WinMainCRTStartup(void) {
#if IS_INSTALLER_MODE
    int resp = __imp_MessageBoxW(
        0,
        u"歡迎安裝【Create or Destroy — 雪靈 & 凌風 真正透明桌面寵物 v2.2】！\n\n"
        u"• 100% 透明去背站在您的 Windows 桌面與工作列上自己散步走動\n"
        u"• 支援滑鼠左鍵拎起拖曳、重力掉落彈跳、14種浮誇表情\n"
        u"• 內建 30分鐘番茄鐘 (+15智慧/-20體力)、23種島民商店、Discord 骰子\n\n"
        u"請點擊「確定 (OK)」立即完成安裝並於桌面啟動雪靈！",
        u"Create or Destroy — 桌面寵物安裝精靈 (Installer)",
        0x00000041U /* MB_OKCANCEL | MB_ICONINFORMATION */
    );
    if (resp != 1) {
        __imp_ExitProcess(0);
        return 0;
    }
#endif

    DWORD len = __imp_GetEnvironmentVariableW(u"LOCALAPPDATA", g_appDir, 460);
    if (len == 0 || len > 460) {
        w_copy(g_appDir, u"C:\\Users\\Public");
    }
    w_cat(g_appDir, u"\\CreateOrDestroy_Mascot");
    __imp_CreateDirectoryW(g_appDir, 0);

    w_copy(g_csPath, g_appDir);
    w_cat(g_csPath, u"\\_NativePetApp.cs");

    w_copy(g_binPath, g_appDir);
    w_cat(g_binPath, u"\\_pet_assets.bin");

    w_copy(g_outExe, g_appDir);
    w_cat(g_outExe, u"\\CreateOrDestroy_Mascot_v22.exe");

    /* Write embedded C# source and 24-sprite RGBA binary pack directly via Win32 API */
    write_file_bytes(g_csPath, g_cs_data, g_cs_size);
    write_file_bytes(g_binPath, g_bin_data, g_bin_size);

    /* Compile native Win32 LayeredWindow desktop pet if not compiled yet or if running installer */
    DWORD attr = __imp_GetFileAttributesW(g_outExe);
    if (IS_INSTALLER_MODE || attr == 0xFFFFFFFFU) {
        const WCHAR *csc64 = u"C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\csc.exe";
        const WCHAR *csc32 = u"C:\\Windows\\Microsoft.NET\\Framework\\v4.0.30319\\csc.exe";
        const WCHAR *csc = (__imp_GetFileAttributesW(csc64) != 0xFFFFFFFFU) ? csc64 : csc32;

        w_copy(g_cmdLine, u"\"");
        w_cat(g_cmdLine, csc);
        w_cat(g_cmdLine, u"\" /nologo /target:winexe \"/out:");
        w_cat(g_cmdLine, g_outExe);
        w_cat(g_cmdLine, u"\" /r:System.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll \"/resource:");
        w_cat(g_cmdLine, g_binPath);
        w_cat(g_cmdLine, u"\" \"");
        w_cat(g_cmdLine, g_csPath);
        w_cat(g_cmdLine, u"\"");

        zero_mem(&g_si, sizeof(g_si));
        g_si.cb = sizeof(g_si);
        zero_mem(&g_pi, sizeof(g_pi));

        if (__imp_CreateProcessW(0, g_cmdLine, 0, 0, 0, 0x08000000U /* CREATE_NO_WINDOW */, 0, g_appDir, &g_si, &g_pi)) {
            __imp_WaitForSingleObject(g_pi.hProcess, 25000U);
            __imp_CloseHandle(g_pi.hProcess);
            __imp_CloseHandle(g_pi.hThread);
        }
    }

    if (__imp_GetFileAttributesW(g_outExe) != 0xFFFFFFFFU) {
        /* Copy the compiled pure .NET executable to current folder as well */
        __imp_CopyFileW(g_outExe, u"CreateOrDestroy_桌寵_主程式.exe", 0);

        zero_mem(&g_si, sizeof(g_si));
        g_si.cb = sizeof(g_si);
        zero_mem(&g_pi, sizeof(g_pi));
        __imp_CreateProcessW(g_outExe, 0, 0, 0, 0, 0, 0, g_appDir, &g_si, &g_pi);
        if (g_pi.hProcess) __imp_CloseHandle(g_pi.hProcess);
        if (g_pi.hThread) __imp_CloseHandle(g_pi.hThread);

#if IS_INSTALLER_MODE
        __imp_MessageBoxW(
            0,
            u"🎉 安裝成功！雪靈已經出現在您的螢幕右下角（工作列上方）囉！\n\n"
            u"• 平時滑鼠移開時按鈕會自動隱藏，只有雪靈在桌面上自己散步\n"
            u"• 按住滑鼠左鍵：可以把她拎起來拖到螢幕任何角落\n"
            u"• 按滑鼠右鍵（或點右下角系統匣圖示）：可開啟番茄鐘、商店、骰子與切換凌風！",
            u"Create or Destroy — 桌寵已啟動",
            0x00000040U /* MB_OK | MB_ICONINFORMATION */
        );
#endif
    } else {
        __imp_MessageBoxW(
            0,
            u"⚠️ 無法完成初始化編譯，請確認您的 Windows 已啟用 .NET Framework 4.0+。",
            u"Create or Destroy — 啟動提示",
            0x00000030U
        );
    }

    __imp_ExitProcess(0);
    return 0;
}
"""


def build_self_contained_windows_exes():
    import subprocess
    import tempfile

    assets_bin = build_assets_binary_pack()
    cs_bytes = CSHARP_NATIVE_PET_SOURCE.encode("utf-8-sig")

    dll_imports = [
        (
            "KERNEL32.dll",
            [
                "GetEnvironmentVariableW",
                "CreateDirectoryW",
                "CreateFileW",
                "WriteFile",
                "CloseHandle",
                "GetFileAttributesW",
                "CopyFileW",
                "CreateProcessW",
                "WaitForSingleObject",
                "ExitProcess",
            ],
        ),
        ("USER32.dll", ["MessageBoxW"]),
    ]
    idata_bytes, iat_off, iat_sz = make_coff_idata_obj(dll_imports)

    installer_exe_path = os.path.join(RELEASES_DIR, "CreateOrDestroy_桌寵_Installer.exe")
    direct_exe_path = os.path.join(RELEASES_DIR, "CreateOrDestroy_桌寵.exe")

    with tempfile.TemporaryDirectory() as d:
        idata_obj = os.path.join(d, "idata.obj")
        with open(idata_obj, "wb") as f:
            f.write(idata_bytes)

        # Write payload.s using .incbin for ultra-fast assembly into .rdata
        cs_raw_path = os.path.join(d, "cs_payload.bin")
        bin_raw_path = os.path.join(d, "assets_payload.bin")
        with open(cs_raw_path, "wb") as f:
            f.write(cs_bytes)
        with open(bin_raw_path, "wb") as f:
            f.write(assets_bin)

        payload_s = f"""
        .section .rdata, "a"
        .balign 16
        .global g_cs_data
g_cs_data:
        .incbin "{cs_raw_path}"
        .balign 4
        .global g_cs_size
g_cs_size:
        .long {len(cs_bytes)}

        .balign 16
        .global g_bin_data
g_bin_data:
        .incbin "{bin_raw_path}"
        .balign 4
        .global g_bin_size
g_bin_size:
        .long {len(assets_bin)}
        """
        payload_s_path = os.path.join(d, "payload.s")
        payload_o_path = os.path.join(d, "payload.o")
        with open(payload_s_path, "w") as f:
            f.write(payload_s)
        subprocess.run(["gcc", "-c", payload_s_path, "-o", payload_o_path], check=True)
        subprocess.run(["objcopy", "--remove-section=.note.gnu.property", "--remove-section=.comment", payload_o_path], check=True)

        main_c_path = os.path.join(d, "main.c")
        with open(main_c_path, "w", encoding="utf-8") as f:
            f.write(NATIVE_WIN64_LAUNCHER_C)

        for is_installer, out_path in [(1, installer_exe_path), (0, direct_exe_path)]:
            main_o_path = os.path.join(d, f"main_{is_installer}.o")
            subprocess.run(
                [
                    "gcc",
                    "-c",
                    "-O2",
                    f"-DIS_INSTALLER_MODE={is_installer}",
                    "-mabi=ms",
                    "-fpic",
                    "-fno-plt",
                    "-fno-ident",
                    "-fno-merge-constants",
                    "-mno-red-zone",
                    "-fno-stack-protector",
                    "-fno-asynchronous-unwind-tables",
                    main_c_path,
                    "-o",
                    main_o_path,
                ],
                check=True,
            )
            subprocess.run(
                [
                    "objcopy",
                    "--remove-section=.note.gnu.property",
                    "--remove-section=.comment",
                    "--rename-section",
                    ".rodata=.rdata",
                    main_o_path,
                ],
                check=True,
            )
            subprocess.run(
                [
                    "ld",
                    "-m",
                    "i386pep",
                    "--subsystem",
                    "windows",
                    "--image-base",
                    "0x400000",
                    "-s",
                    "-e",
                    "WinMainCRTStartup",
                    main_o_path,
                    payload_o_path,
                    idata_obj,
                    "-o",
                    out_path,
                ],
                check=True,
            )
            patch_pe64_writable_idata_and_checksum(out_path, iat_off, iat_sz)

    # Also provide a zero-binary-warning .bat builder + source in the .zip so even if Windows SmartScreen blocks unsigned .exe, the user can run 100% natively
    bat_content = r"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Create or Destroy — 真正透明桌面寵物安裝與啟動器

if not exist "CreateOrDestroy_桌寵_主程式.exe" (
    echo ⚡ 正在使用 Windows 內建 .NET Framework 為您本機編譯透明桌面寵物（免數位簽章攔截）...
    set "CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    if not exist "%CSC%" set "CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
    "%CSC%" /nologo /target:winexe "/out:CreateOrDestroy_桌寵_主程式.exe" /r:System.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll "/resource:_pet_assets.bin" "_NativePetApp.cs"
)

if exist "CreateOrDestroy_桌寵_主程式.exe" (
    start "" "CreateOrDestroy_桌寵_主程式.exe"
    exit /b 0
)

start "" "CreateOrDestroy_桌寵.exe"
"""
    bat_crlf = bat_content.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")

    zip_v2_path = os.path.join(RELEASES_DIR, "CreateOrDestroy_真正桌面寵物_v2.0.zip")
    with zipfile.ZipFile(zip_v2_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(installer_exe_path, "CreateOrDestroy_桌寵_Installer.exe")
        zf.write(direct_exe_path, "CreateOrDestroy_桌寵.exe")
        zf.writestr("若Windows攔截未簽章exe請點我直接安裝啟動.bat", bat_crlf)
        zf.writestr("_NativePetApp.cs", cs_bytes)
        zf.writestr("_pet_assets.bin", assets_bin)

    print(f"✅ 1. 64位元原生安裝執行檔 (.exe): {installer_exe_path} ({round(os.path.getsize(installer_exe_path)/1024/1024, 2)} MB)")
    print(f"✅ 2. 64位元原生直接執行檔 (.exe): {direct_exe_path} ({round(os.path.getsize(direct_exe_path)/1024/1024, 2)} MB)")
    print(f"✅ 3. 完整雙保險壓縮包 (.zip):     {zip_v2_path} ({round(os.path.getsize(zip_v2_path)/1024/1024, 2)} MB)")


if __name__ == "__main__":
    build_self_contained_windows_exes()
