// ==========================================================================
// Create or Destroy — Frontend Controller (雪靈 Xueling & 凌風 Ling Feng)
// ==========================================================================

let APP_STATE = null;
let ASSET_MANIFEST = null;
let CURRENT_SHOP_FILTER = "all";
let POMO_TIMER_ID = null;
let POMO_TOTAL_SEC = 1800;
let POMO_REMAINING_SEC = 1800;

const EXPR_CONFIG = {
  xueling: [
    { key: "expr_1_normal", label: "😐 普通", particle: "❄️" },
    { key: "expr_2_happy", label: "✨ 超開心閃耀", particle: "✨" },
    { key: "expr_3_angry", label: "💢 暴怒爆青筋", particle: "💢" },
    { key: "expr_4_surprised", label: "⚡ 大震驚雷擊", particle: "⚡" },
    { key: "expr_5_shy", label: "💕 害羞冒愛心", particle: "💕" },
    { key: "expr_6_focused", label: "💡 番茄鐘專注", particle: "💡" },
    { key: "expr_7_sick", label: "🤒 重感冒/腸胃炎", particle: "🤒" },
  ],
  lingfeng: [
    { key: "expr_1_normal", label: "😐 普通", particle: "🏎️" },
    { key: "expr_2_smile", label: "✨ 超開心閃耀", particle: "✨" },
    { key: "expr_3_angry", label: "💢 暴怒爆青筋", particle: "💢" },
    { key: "expr_4_surprised", label: "⚡ 大震驚雷擊", particle: "⚡" },
    { key: "expr_5_shy", label: "💕 害羞冒愛心", particle: "💕" },
    { key: "expr_6_focused", label: "💡 番茄鐘專注", particle: "💡" },
    { key: "expr_7_sick", label: "🤒 重感冒/腸胃炎", particle: "🤒" },
  ],
};

const VIEW_CONFIG = {
  xueling: [
    { key: "main_fullbody", label: "🌟 主立繪" },
    { key: "turn_1_front", label: "正面 FRONT" },
    { key: "turn_2_left45", label: "左前 45°" },
    { key: "turn_3_side", label: "側面 SIDE" },
    { key: "turn_4_right45", label: "右後 45°" },
    { key: "turn_5_back", label: "背面 BACK" },
    { key: "head_1_front", label: "頭部特寫" },
    { key: "costume_jacket_front", label: "🧥 LEGEND X 外套" },
    { key: "prop_sunglasses", label: "🕶️ 藍色墨鏡" },
    { key: "costume_shoes", label: "👟 電競運動鞋" },
  ],
  lingfeng: [
    { key: "main_fullbody", label: "🌟 主立繪" },
    { key: "turn_1_front", label: "正面 FRONT" },
    { key: "turn_2_side", label: "側面 SIDE" },
    { key: "turn_4_three_quarter", label: "斜側 3/4" },
    { key: "turn_3_back", label: "背面 BACK" },
    { key: "turn_5_top", label: "俯視 TOP" },
    { key: "racing_scene", label: "🏎️ BMW 跑車駕駛特寫" },
    { key: "prop_carkey", label: "🔑 BMW 跑車鑰匙" },
    { key: "prop_gaming_chair", label: "💺 專屬電競椅" },
    { key: "prop_headphones", label: "🎧 電競耳機" },
  ],
};

window.addEventListener("DOMContentLoaded", async () => {
  await loadManifest();
  await fetchState();
  appendChatBubble(
    "bot",
    "嗨！歡迎來到 Create or Destroy 雙角色 AI 桌寵系統 ✨ 您可以隨時切換「雪靈」與「凌風」、啟動 30 分鐘番茄鐘累積智慧經驗值、在 Discord 骰骰子賺取經驗兌換島民商店金幣！"
  );
});

async function loadManifest() {
  try {
    const res = await fetch("/assets/asset_manifest.json");
    ASSET_MANIFEST = await res.json();
  } catch (e) {
    console.error("Failed to load asset manifest:", e);
  }
}

async function apiPost(url, body = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return await res.json();
}

async function fetchState() {
  const res = await fetch("/api/state");
  const data = await res.json();
  if (data.ok) {
    renderState(data.state);
  }
}

function showToast(msg, isError = false) {
  const box = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = "toast-msg" + (isError ? " error" : "");
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

function spawnParticles(symbol = "✨", count = 6) {
  const layer = document.getElementById("particle-layer");
  for (let i = 0; i < count; i++) {
    const p = document.createElement("div");
    p.className = "floating-particle";
    p.textContent = symbol;
    p.style.left = `${28 + Math.random() * 52}%`;
    p.style.top = `${35 + Math.random() * 40}%`;
    p.style.animationDelay = `${i * 0.08}s`;
    layer.appendChild(p);
    setTimeout(() => p.remove(), 1450);
  }
}

function triggerSpriteAnimation(animClass = "bounce") {
  const box = document.getElementById("pet-sprite-container");
  box.classList.remove("bounce", "shake");
  void box.offsetWidth;
  box.classList.add(animClass);
  setTimeout(() => box.classList.remove(animClass), 650);
}

function renderState(state) {
  APP_STATE = state;
  const prof = state.profile;
  const charId = prof.active_character || "xueling";
  const char = state.characters[charId];

  // Version
  if (state.version_info && state.version_info.version) {
    document.getElementById("version-badge").textContent = `v${state.version_info.version}`;
  }

  // Top Bar Character Switcher
  document.getElementById("btn-char-xueling").classList.toggle("active", charId === "xueling");
  document.getElementById("btn-char-lingfeng").classList.toggle("active", charId === "lingfeng");

  // Economy Bar
  document.getElementById("stat-total-exp").textContent = Number(prof.total_exp).toFixed(1);
  document.getElementById("stat-avail-exp").textContent = Number(prof.available_exp).toFixed(1);
  document.getElementById("stat-coins").textContent = prof.coins;
  document.getElementById("shop-coins-val").textContent = prof.coins;
  document.getElementById("stat-streak").textContent =
    `${prof.streak_days} 天` + (prof.sickness_unlocked ? " (已解鎖生病)" : "");

  // Minigame Mode Toggle Button
  const mgBtn = document.getElementById("btn-minigame-toggle");
  if (prof.mini_game_enabled) {
    mgBtn.className = "action-pill-btn minigame-on";
    mgBtn.textContent = "🎮 小遊戲互動模式：開啟";
  } else {
    mgBtn.className = "action-pill-btn";
    mgBtn.textContent = "🎮 小遊戲互動模式：關閉";
  }

  // Stage Header & Health Badge
  document.getElementById("stage-char-name").textContent = char.name;
  document.getElementById("chat-char-title").textContent = char.name;
  document.getElementById("speech-speaker").textContent =
    (charId === "xueling" ? "❄️ " : "🏎️ ") + char.name + "：";
  document.getElementById("stage-char-level").textContent = `Lv.${char.computed_level}`;

  const hBadge = document.getElementById("stage-health-badge");
  const hDetail = document.getElementById("txt-health-detail");
  const gastroAlert = document.getElementById("badge-gastro-alert");
  const btnAdvGastro = document.getElementById("btn-advance-gastro");

  if (char.health_status === "cold") {
    hBadge.className = "health-badge cold";
    hBadge.textContent = "🤒 感冒發燒中";
    hDetail.textContent = "🤒 感冒發燒中（請服用【感冒藥 +25】）";
    gastroAlert.classList.add("hidden");
    btnAdvGastro.classList.add("hidden");
  } else if (char.health_status === "gastroenteritis") {
    hBadge.className = "health-badge gastroenteritis";
    const rem = char.gastro_days_remaining;
    const activeCourse = char.gastro_course_active === 1;
    hBadge.textContent = activeCourse ? `🤢 腸胃炎（療程剩 ${rem} 天）` : "🤢 嚴重腸胃炎（未服藥）";
    hDetail.textContent = activeCourse
      ? `🏥 已服腸胃藥三天份，還需 ${rem} 天完全康復`
      : "🤢 誤喝謎之飲料觸發腸胃炎！請購買【腸胃藥三天份】";
    gastroAlert.classList.remove("hidden");
    btnAdvGastro.classList.remove("hidden");
  } else {
    hBadge.className = "health-badge healthy";
    hBadge.textContent = "✨ 健康良好";
    hDetail.textContent = "✨ 健康良好";
    gastroAlert.classList.add("hidden");
    btnAdvGastro.classList.add("hidden");
  }

  // Dirty Alert Badge
  const dirtyAlert = document.getElementById("badge-dirty-alert");
  if (char.dirtiness >= 45) {
    dirtyAlert.classList.remove("hidden");
  } else {
    dirtyAlert.classList.add("hidden");
  }

  // Special Prop Button Text
  const propBtn = document.getElementById("btn-special-prop");
  if (charId === "lingfeng") {
    propBtn.innerHTML = "🏎️ BMW 跑車特寫 <small>賽道模式</small>";
  } else {
    propBtn.innerHTML = "🧥 外套/墨鏡拆解 <small>設定集</small>";
  }

  // Update Main Sprite & Expression Sprite
  updateCharacterSprites(charId, char.current_view, char.current_expr);
  renderSelectorChips(charId, char.current_view, char.current_expr);

  // Update Status Bars
  document.getElementById("val-affection").textContent = char.affection;
  document.getElementById("val-recovery").textContent = char.recovery_exp;
  document.getElementById("val-wisdom").textContent = char.wisdom_exp;

  const msStamina = document.getElementById("mini-val-stamina");
  if (msStamina) {
    msStamina.textContent = char.stamina;
    document.getElementById("mini-val-wisdom").textContent = char.wisdom_exp;
    document.getElementById("mini-val-hunger").textContent = `${char.hunger}%`;
    document.getElementById("mini-val-dirt").textContent = `${char.dirtiness}%`;
    document.getElementById("mini-val-affection").textContent = char.affection;
  }

  document.getElementById("bar-txt-stamina").textContent = `${char.stamina} / 100`;
  document.getElementById("bar-fill-stamina").style.width = `${Math.min(100, char.stamina)}%`;

  const wisdomPct = Math.min(100, Math.round((char.wisdom_exp / 150) * 100));
  document.getElementById("bar-txt-wisdom").textContent = `${char.wisdom_exp} 點 (完成 ${char.pomodoro_count} 次番茄鐘)`;
  document.getElementById("bar-fill-wisdom").style.width = `${wisdomPct}%`;

  document.getElementById("bar-txt-hunger").textContent = `${char.hunger}%`;
  document.getElementById("bar-fill-hunger").style.width = `${char.hunger}%`;

  document.getElementById("bar-txt-dirtiness").textContent =
    `${char.dirtiness}%` + (char.dirtiness >= 50 ? " (待洗澡!)" : "");
  document.getElementById("bar-fill-dirtiness").style.width = `${char.dirtiness}%`;

  document.getElementById("bar-txt-fatigue").textContent = `${char.fatigue}%`;
  document.getElementById("bar-fill-fatigue").style.width = `${char.fatigue}%`;

  // Render Achievements, Shop, Logs, Settings
  renderAchievements(state);
  renderShop(state);
  renderLogs(state.logs || []);

  document.getElementById("set-discord-webhook").value = prof.discord_webhook || "";
  document.getElementById("set-ai-provider").value = prof.ai_provider || "offline";
  document.getElementById("set-ai-key").value = prof.ai_api_key || "";
}

function updateCharacterSprites(charId, viewKey, exprKey) {
  const cManifest = ASSET_MANIFEST && ASSET_MANIFEST[charId] ? ASSET_MANIFEST[charId] : null;
  const mainImg = document.getElementById("pet-main-img");
  const exprImg = document.getElementById("pet-expr-img");
  const exprLabel = document.getElementById("pet-expr-label");

  if (cManifest && cManifest[viewKey]) {
    mainImg.src = "/" + cManifest[viewKey].path;
  } else {
    mainImg.src = `/assets/${charId}/turnaround/main_fullbody.png`;
  }

  // Fallback for expression key difference between xueling (expr_2_happy) and lingfeng (expr_2_smile)
  if (charId === "lingfeng" && exprKey === "expr_2_happy") exprKey = "expr_2_smile";
  if (charId === "xueling" && exprKey === "expr_2_smile") exprKey = "expr_2_happy";

  if (cManifest && cManifest[exprKey]) {
    exprImg.src = "/" + cManifest[exprKey].path;
    exprLabel.textContent = cManifest[exprKey].label.replace(/^.*?- /, "");
  } else {
    exprImg.src = `/assets/${charId}/expressions/expr_1_normal.png`;
    exprLabel.textContent = "普通 (Normal)";
  }
}

function renderSelectorChips(charId, activeView, activeExpr) {
  const exprRow = document.getElementById("expr-buttons-row");
  exprRow.innerHTML = "";
  (EXPR_CONFIG[charId] || []).forEach((item) => {
    const btn = document.createElement("button");
    btn.className = "pose-chip" + (activeExpr === item.key ? " active" : "");
    btn.textContent = item.label;
    btn.onclick = () => changePose(charId, null, item.key, item.particle);
    exprRow.appendChild(btn);
  });

  const viewRow = document.getElementById("view-buttons-row");
  viewRow.innerHTML = "";
  (VIEW_CONFIG[charId] || []).forEach((item) => {
    const btn = document.createElement("button");
    btn.className = "pose-chip" + (activeView === item.key ? " active" : "");
    btn.textContent = item.label;
    btn.onclick = () => changePose(charId, item.key, null, "🔄");
    viewRow.appendChild(btn);
  });
}

async function switchCharacter(charId) {
  const data = await apiPost("/api/switch_char", { char_id: charId });
  if (data.ok) {
    renderState(data.state);
    const cname = charId === "xueling" ? "雪靈 (Xueling)" : "凌風 (Ling Feng)";
    setSpeech(
      charId === "xueling"
        ? "雪靈報到 ✨ 今天要一起開啟 30 分鐘番茄鐘，還是去島民商店吃點心呢？"
        : "凌風就位 🏎️ 不管是專注學習還是 Discord 多人骰子對決，隨時可以開始。"
    );
    spawnParticles(charId === "xueling" ? "❄️" : "🏎️", 6);
    triggerSpriteAnimation("bounce");
    showToast(`已切換桌寵角色為：${cname}`);
  }
}

async function changePose(charId, view, expr, particleSymbol = "✨") {
  const data = await apiPost("/api/pose", { char_id: charId, view, expr });
  if (data.ok) {
    renderState(data.state);
    spawnParticles(particleSymbol, 5);
    triggerSpriteAnimation(expr === "expr_3_angry" ? "shake" : "bounce");
  }
}

async function toggleMinigameMode() {
  const data = await apiPost("/api/minigame", {});
  if (data.ok) {
    renderState(data.state);
    showToast(`養成小遊戲互動模式：${data.mini_game_enabled ? "已開啟 🎮" : "已關閉"}`);
  }
}

function toggleLayoutMode() {
  document.body.classList.toggle("pet-product-mode");
  const isCompact = document.body.classList.contains("pet-product-mode");
  const btn = document.getElementById("btn-layout-mode");
  if (btn) {
    btn.textContent = isCompact ? "🖥️ 展開雙欄面板" : "🗔 精簡桌寵視窗";
  }
  showToast(isCompact ? "已切換為【精簡桌寵主視窗模式】" : "已展開為【雙欄完整控制模式】");
}

function toggleDevMode() {
  document.querySelectorAll(".dev-only").forEach((el) => {
    el.classList.toggle("hidden");
  });
  showToast("🔧 已切換顯示/隱藏【快速測試按鈕（5秒番茄鐘/測試生病）】");
}

function togglePoseDrawer() {
  const dr = document.getElementById("pose-drawer");
  if (dr) dr.classList.toggle("hidden");
}

function openFeatureDrawer(tabId) {
  const panel = document.getElementById("control-panel-card");
  if (panel) panel.classList.add("drawer-open");
  switchTab(tabId);
  document.querySelectorAll(".dock-btn").forEach((b) => {
    b.classList.toggle("active", b.getAttribute("data-tab") === tabId);
  });
  if (document.body.classList.contains("pet-product-mode") && panel) {
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function closeFeatureDrawer() {
  const panel = document.getElementById("control-panel-card");
  if (panel) panel.classList.remove("drawer-open");
}

function setSpeech(text) {
  if (!text) return;
  document.getElementById("speech-text").textContent = text;
}

async function interactPet(action) {
  const charId = APP_STATE ? APP_STATE.profile.active_character : "xueling";
  const data = await apiPost("/api/interact", { char_id: charId, action });
  if (data.ok) {
    renderState(data.state);
    if (data.reply) setSpeech(data.reply);

    const particleMap = {
      pat: "💕",
      poke: "💢",
      bath: "🛁",
      rest: "💤",
      racing_drive: "🏎️",
      trigger_cold_test: "🤒",
    };
    spawnParticles(particleMap[action] || "✨", 7);
    triggerSpriteAnimation(action === "poke" || action === "trigger_cold_test" ? "shake" : "bounce");
  }
}

function triggerSpecialProp() {
  const charId = APP_STATE ? APP_STATE.profile.active_character : "xueling";
  if (charId === "lingfeng") {
    interactPet("racing_drive");
  } else {
    const curView = APP_STATE.characters.xueling.current_view;
    const nextView = curView === "costume_jacket_front" ? "main_fullbody" : "costume_jacket_front";
    changePose("xueling", nextView, "expr_2_happy", "🧥");
    setSpeech("這是我的 LEGEND X 專屬電競外套與墨鏡設定細節喔！✨");
  }
}

// ==========================================================================
// 30-MINUTE POMODORO STUDY SYSTEM (+15 WISDOM EXP, -20 STAMINA)
// ==========================================================================
async function startPomodoro(durationSeconds = 1800) {
  if (POMO_TIMER_ID) return;
  const charId = APP_STATE.profile.active_character;
  const res = await apiPost("/api/pomodoro", { char_id: charId, event_type: "start" });
  if (!res.ok) {
    showToast(res.error || "無法啟動番茄鐘", true);
    setSpeech(res.error);
    return;
  }

  renderState(res.state);
  if (res.reply) setSpeech(res.reply);
  spawnParticles("💡", 7);

  POMO_TOTAL_SEC = durationSeconds;
  POMO_REMAINING_SEC = durationSeconds;

  document.getElementById("btn-pomo-start").disabled = true;
  document.getElementById("btn-pomo-quick").disabled = true;
  document.getElementById("btn-pomo-stop").disabled = false;
  document.getElementById("stage-pomo-hud").classList.remove("hidden");

  updatePomoDisplay();
  POMO_TIMER_ID = setInterval(async () => {
    POMO_REMAINING_SEC--;
    updatePomoDisplay();
    if (POMO_REMAINING_SEC <= 0) {
      clearInterval(POMO_TIMER_ID);
      POMO_TIMER_ID = null;
      await finishPomodoro();
    }
  }, 1000);
}

function updatePomoDisplay() {
  const mins = String(Math.floor(POMO_REMAINING_SEC / 60)).padStart(2, "0");
  const secs = String(POMO_REMAINING_SEC % 60).padStart(2, "0");
  const txt = `${mins}:${secs}`;
  document.getElementById("pomo-timer-display").textContent = txt;
  document.getElementById("stage-pomo-timer").textContent = txt;

  const pct = Math.min(100, Math.round(((POMO_TOTAL_SEC - POMO_REMAINING_SEC) / POMO_TOTAL_SEC) * 100));
  document.getElementById("pomo-progress-fill").style.width = `${pct}%`;
}

async function stopPomodoro() {
  if (!POMO_TIMER_ID) return;
  clearInterval(POMO_TIMER_ID);
  POMO_TIMER_ID = null;

  document.getElementById("btn-pomo-start").disabled = false;
  document.getElementById("btn-pomo-quick").disabled = false;
  document.getElementById("btn-pomo-stop").disabled = true;
  document.getElementById("stage-pomo-hud").classList.add("hidden");
  document.getElementById("pomo-timer-display").textContent = "30:00";
  document.getElementById("pomo-progress-fill").style.width = "0%";

  const charId = APP_STATE.profile.active_character;
  const res = await apiPost("/api/pomodoro", { char_id: charId, event_type: "abort" });
  if (res.ok) {
    renderState(res.state);
    setSpeech(res.reply);
    showToast("已中途停止番茄鐘（未滿全程不計入 +15 智慧經驗值）", true);
  }
}

async function finishPomodoro() {
  document.getElementById("btn-pomo-start").disabled = false;
  document.getElementById("btn-pomo-quick").disabled = false;
  document.getElementById("btn-pomo-stop").disabled = true;
  document.getElementById("stage-pomo-hud").classList.add("hidden");
  document.getElementById("pomo-timer-display").textContent = "30:00";
  document.getElementById("pomo-progress-fill").style.width = "100%";

  const charId = APP_STATE.profile.active_character;
  const res = await apiPost("/api/pomodoro", { char_id: charId, event_type: "complete" });
  if (res.ok) {
    renderState(res.state);
    setSpeech(res.reply);
    spawnParticles("🎓", 10);
    triggerSpriteAnimation("bounce");
    showToast("🎓 完成 30 分鐘番茄鐘！角色智慧經驗值 +15 點、人物體力值 -20 點！");
    if (res.unlocked_achievements && res.unlocked_achievements.length > 0) {
      res.unlocked_achievements.forEach((m) => showToast(m));
    }
  }
}

function renderAchievements(state) {
  const grid = document.getElementById("achievements-grid");
  grid.innerHTML = "";
  const unlocked = state.unlocked_achievements || {};
  const cat = state.achievements_catalog || {};
  const allAchs = [...(cat.wisdom_achievements || []), ...(cat.care_achievements || [])];

  allAchs.forEach((ach) => {
    const isUn = Boolean(unlocked[ach.id]);
    const card = document.createElement("div");
    card.className = "ach-card" + (isUn ? " unlocked" : "");
    card.innerHTML = `
      <div class="ach-icon">${ach.icon || "🏆"}</div>
      <div>
        <div class="ach-title">${ach.title} ${isUn ? "✅" : "🔒"}</div>
        <div class="ach-desc">${ach.description}</div>
      </div>
    `;
    grid.appendChild(card);
  });
}

// ==========================================================================
// CREATE OR DESTROY ISLAND SHOP (23 ITEMS) & GASTROENTERITIS 3-DAY COURSE
// ==========================================================================
function filterShop(category, btnEl) {
  CURRENT_SHOP_FILTER = category;
  document.querySelectorAll(".filter-chip").forEach((b) => b.classList.remove("active"));
  if (btnEl) btnEl.classList.add("active");
  if (APP_STATE) renderShop(APP_STATE);
}

function renderShop(state) {
  const grid = document.getElementById("shop-items-grid");
  grid.innerHTML = "";
  const items = (state.shop_catalog && state.shop_catalog.items) || [];
  const inv = state.inventory || {};

  items
    .filter((it) => CURRENT_SHOP_FILTER === "all" || it.category === CURRENT_SHOP_FILTER)
    .forEach((it) => {
      const count = inv[it.id] || 0;
      const isNeg = it.recovery < 0;
      const effectBadge = it.effect_label || `${it.recovery >= 0 ? "+" : ""}${it.recovery} 恢復值`;
      const iconSrc = it.icon ? "/" + it.icon.replace(/^\//, "") : `/assets/shop_items/${it.id}.svg`;
      const descText = it.description || it.desc || "";

      const card = document.createElement("div");
      card.className = "shop-item-card" + (isNeg ? " negative-item" : "");
      card.innerHTML = `
        <div>
          <div class="shop-item-top">
            <img class="shop-item-svg" src="${iconSrc}" alt="${it.name}" />
            <div>
              <div class="shop-item-name">${it.emoji} ${it.name}</div>
              <div class="shop-item-effect">${effectBadge}</div>
            </div>
          </div>
          <div class="shop-item-desc" style="margin-top:6px;">${descText}</div>
        </div>
        <div class="shop-item-footer">
          <div>
            <span class="shop-price-tag">🪙 ${it.price}</span>
            <span class="inv-count-badge">背包: ${count}</span>
          </div>
          <div class="shop-btn-group">
            <button class="shop-act-btn" onclick="buyShopItem('${it.id}', false)">購買</button>
            <button class="shop-act-btn feed" onclick="buyShopItem('${it.id}', true)">購買並餵食</button>
            ${
              count > 0
                ? `<button class="shop-act-btn use-bag" onclick="useBagItem('${it.id}')">餵食</button>`
                : ""
            }
          </div>
        </div>
      `;
      grid.appendChild(card);
    });
}

async function buyShopItem(itemId, autoUse = false) {
  const charId = APP_STATE.profile.active_character;
  const res = await apiPost("/api/shop/buy", {
    item_id: itemId,
    quantity: 1,
    auto_use_char_id: autoUse ? charId : null,
  });
  if (!res.ok) {
    showToast(res.error, true);
    return;
  }
  renderState(res.state);
  if (res.reply) setSpeech(res.reply);
  showToast(res.message);
  spawnParticles(autoUse ? "🍽️" : "🛒", 6);
  triggerSpriteAnimation("bounce");
}

async function useBagItem(itemId) {
  const charId = APP_STATE.profile.active_character;
  const res = await apiPost("/api/shop/use", { char_id: charId, item_id: itemId });
  if (!res.ok) {
    showToast(res.error, true);
    return;
  }
  renderState(res.state);
  if (res.reply) setSpeech(res.reply);
  showToast(res.message);
  spawnParticles(itemId === "bad_mystery_drink" ? "🤢" : "✨", 7);
  triggerSpriteAnimation(itemId === "bad_mystery_drink" ? "shake" : "bounce");
}

async function quickUseMedicine(itemId) {
  const inv = (APP_STATE && APP_STATE.inventory) || {};
  if ((inv[itemId] || 0) > 0) {
    await useBagItem(itemId);
  } else {
    await buyShopItem(itemId, true);
  }
}

async function advanceGastroDay() {
  const charId = APP_STATE.profile.active_character;
  const res = await apiPost("/api/gastro/advance", { char_id: charId });
  if (!res.ok) {
    showToast(res.error, true);
    return;
  }
  renderState(res.state);
  if (res.reply) setSpeech(res.reply);
  showToast(res.message);
  spawnParticles("💊", 7);
}

// ==========================================================================
// DISCORD COMMANDS, SOLO/MULTIPLAYER DICE & COIN EXCHANGE
// ==========================================================================
async function runDiscordCommand(cmdText) {
  const res = await apiPost("/api/discord/command", { command: cmdText, username: "島民玩家" });
  if (!res.ok) {
    showToast(res.error, true);
    return;
  }
  renderState(res.state);
  showToast(res.message);
  spawnParticles("💎", 6);
}

async function quickExchangeCoins() {
  await runDiscordCommand("/exchange 1");
}

async function rollDiscordDice(mode = "solo") {
  const cmd = mode === "multi" ? "/roll multi" : "/roll solo";
  const res = await apiPost("/api/discord/command", { command: cmd, username: "島民玩家" });
  if (!res.ok) {
    showToast(res.error, true);
    return;
  }
  renderState(res.state);
  showToast(res.message);
  spawnParticles("🎲", 8);

  const arena = document.getElementById("dice-arena-box");
  arena.classList.remove("hidden");
  const rollsHtml = (res.rolls || [])
    .map(
      (r) => `
      <div class="dice-player-chip ${r.is_winner ? "winner" : ""}">
        🎲 ${r.name}：<strong>${r.roll} 點</strong> ${r.is_winner ? "👑最高點" : ""}
      </div>
    `
    )
    .join("");
  arena.innerHTML = `
    <div style="font-size:13px;font-weight:800;color:#fff;">${res.message}</div>
    <div class="dice-rolls-row">${rollsHtml}</div>
  `;
}

async function submitDiscordInput() {
  const input = document.getElementById("discord-cmd-input");
  const val = input.value.trim();
  if (!val) return;
  input.value = "";
  await runDiscordCommand(val);
}

// ==========================================================================
// AI PERSONA CHAT & LOGS
// ==========================================================================
function appendChatBubble(role, text) {
  const box = document.getElementById("chat-history-box");
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

async function sendQuickChat(text) {
  document.getElementById("chat-user-input").value = text;
  await sendChatMessage();
}

async function sendChatMessage() {
  const input = document.getElementById("chat-user-input");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";

  const charId = APP_STATE ? APP_STATE.profile.active_character : "xueling";
  appendChatBubble("user", msg);

  const res = await apiPost("/api/chat", { char_id: charId, message: msg });
  if (res.ok) {
    renderState(res.state);
    appendChatBubble("bot", `${res.char_name}：${res.reply}`);
    setSpeech(res.reply);
    spawnParticles("💬", 5);
    triggerSpriteAnimation("bounce");
  }
}

function renderLogs(logs) {
  const box = document.getElementById("activity-logs-box");
  box.innerHTML = logs
    .map(
      (l) => `
      <div class="log-item">
        <span class="log-time">[${l.created_at}]</span>
        <span class="log-src">【${l.source}】</span>
        <span>${l.message}</span>
      </div>
    `
    )
    .join("");
}

// ==========================================================================
// TABS, MODALS & HOT-UPDATE PATCHER
// ==========================================================================
function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("active", b.getAttribute("data-tab") === tabId);
  });
  document.querySelectorAll(".tab-content").forEach((c) => {
    c.classList.toggle("active", c.id === tabId);
  });
}

function openModal(id) {
  document.getElementById(id).classList.remove("hidden");
}

function closeModal(id) {
  document.getElementById(id).classList.add("hidden");
}

async function saveSettings() {
  const payload = {
    discord_webhook: document.getElementById("set-discord-webhook").value.trim(),
    ai_provider: document.getElementById("set-ai-provider").value,
    ai_api_key: document.getElementById("set-ai-key").value.trim(),
  };
  const res = await apiPost("/api/settings", payload);
  if (res.ok) {
    renderState(res.state);
    showToast("✅ 已成功儲存 Discord 連動與 AI 引擎設定！");
    closeModal("modal-settings");
  }
}

async function generateSamplePatch() {
  const ver = document.getElementById("new-patch-ver").value.trim() || "1.0.1";
  const notes = document.getElementById("new-patch-notes").value.trim() || "熱更新包測試";
  const res = await apiPost("/api/updater/create", { new_version: ver, patch_notes: notes });
  if (res.ok) {
    renderState(res.state);
    const box = document.getElementById("patch-result-box");
    box.classList.remove("hidden");
    box.textContent = res.message;
    showToast(res.message);
  }
}

async function uploadHotUpdatePatch() {
  const fileInput = document.getElementById("patch-file-input");
  if (!fileInput.files || fileInput.files.length === 0) {
    showToast("請先選擇一個 .zip 熱更新包檔案！", true);
    return;
  }
  const file = fileInput.files[0];
  const arrayBuffer = await file.arrayBuffer();
  const res = await fetch(`/api/updater/apply?filename=${encodeURIComponent(file.name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: arrayBuffer,
  });
  const data = await res.json();
  if (data.ok) {
    renderState(data.state);
    showToast(data.message);
    const box = document.getElementById("patch-result-box");
    box.classList.remove("hidden");
    box.textContent = data.message;
  } else {
    showToast(data.error || "更新包套用失敗", true);
  }
}

// ==========================================================================
// AUTONOMOUS DESKTOP PET AI ROAMING, WALKING, JUMPING & DRAG PHYSICS ENGINE
// ==========================================================================
const PET_AI = {
  autoWalk: true,
  state: "walk", // "idle" | "walk" | "jump" | "drag" | "fall"
  x: 0,          // horizontal offset in px from center (-120..+120)
  y: 0,          // vertical offset in px (<= 0 means up in air)
  vx: 1.35,
  vy: 0,
  dir: 1,        // 1 = right, -1 = left
  stepPhase: 0,
  stateTimer: 120,
  dragging: false,
  dragStartX: 0,
  dragStartY: 0,
  origX: 0,
  origY: 0,
};

function initAutonomousPetEngine() {
  const wrap = document.getElementById("pet-sprite-container");
  const img = document.getElementById("pet-main-img");
  if (!wrap || !img) return;
  wrap.classList.remove("breathing");

  // Disable native image drag so custom mouse drag physics works smoothly
  img.setAttribute("draggable", "false");

  wrap.addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    PET_AI.dragging = true;
    PET_AI.state = "drag";
    PET_AI.dragStartX = e.clientX;
    PET_AI.dragStartY = e.clientY;
    PET_AI.origX = PET_AI.x;
    PET_AI.origY = PET_AI.y;
    PET_AI.vy = 0;
  });

  window.addEventListener("mousemove", (e) => {
    if (!PET_AI.dragging) return;
    const dx = e.clientX - PET_AI.dragStartX;
    const dy = e.clientY - PET_AI.dragStartY;
    if (Math.hypot(dx, dy) > 8) {
      PET_AI.x = Math.max(-135, Math.min(135, PET_AI.origX + dx));
      PET_AI.y = Math.max(-150, Math.min(20, PET_AI.origY + dy));
      if (Math.random() < 0.08) {
        spawnParticles("⚡", 1);
      }
    }
  });

  window.addEventListener("mouseup", (e) => {
    if (!PET_AI.dragging) return;
    const moved = Math.hypot(e.clientX - PET_AI.dragStartX, e.clientY - PET_AI.dragStartY);
    PET_AI.dragging = false;
    if (moved > 10) {
      PET_AI.state = "fall";
      PET_AI.vy = 1.5;
      setSpeech("哇啊啊！從半空中掉下來啦～✨");
      spawnParticles("✨", 4);
    } else {
      PET_AI.state = "idle";
      PET_AI.stateTimer = 80;
    }
  });

  // 30 FPS autonomous physics & walking loop
  setInterval(() => {
    if (!wrap) return;
    PET_AI.stepPhase += 0.26;

    if (PET_AI.state === "drag") {
      const swing = Math.sin(PET_AI.stepPhase * 1.6) * 6;
      wrap.style.transform = `translate(${PET_AI.x.toFixed(1)}px, ${PET_AI.y.toFixed(1)}px) rotate(${swing.toFixed(1)}deg) scale(1.04)`;
      return;
    }

    if (PET_AI.state === "fall") {
      PET_AI.vy += 1.4;
      PET_AI.y += PET_AI.vy;
      if (PET_AI.y >= 0) {
        PET_AI.y = 0;
        if (Math.abs(PET_AI.vy) > 4.5) {
          PET_AI.vy = -PET_AI.vy * 0.45;
        } else {
          PET_AI.vy = 0;
          PET_AI.state = "walk";
          PET_AI.stateTimer = 110;
        }
      }
      wrap.style.transform = `translate(${PET_AI.x.toFixed(1)}px, ${PET_AI.y.toFixed(1)}px)`;
      return;
    }

    if (!PET_AI.autoWalk) {
      const breathY = Math.sin(PET_AI.stepPhase * 0.45) * 3.5;
      wrap.style.transform = `translate(0px, ${breathY.toFixed(1)}px)`;
      return;
    }

    PET_AI.stateTimer -= 1;
    if (PET_AI.stateTimer <= 0) {
      const roll = Math.random();
      if (roll < 0.58) {
        PET_AI.state = "walk";
        PET_AI.dir = Math.random() < 0.5 ? -1 : 1;
        PET_AI.stateTimer = 75 + Math.floor(Math.random() * 90);
      } else if (roll < 0.78) {
        PET_AI.state = "jump";
        PET_AI.vy = -9.5;
        PET_AI.stateTimer = 45;
        spawnParticles("✨", 3);
      } else {
        PET_AI.state = "idle";
        PET_AI.stateTimer = 50 + Math.floor(Math.random() * 60);
      }

      // Autonomous spontaneous expression & line every few transitions
      if (Math.random() < 0.35 && APP_STATE && !POMODORO.running) {
        const charId = APP_STATE.profile.active_character;
        const c = APP_STATE.characters[charId];
        if (c && c.health_status === "healthy") {
          const exprPool = charId === "xueling"
            ? ["expr_1_normal", "expr_2_happy", "expr_5_shy", "expr_4_surprised"]
            : ["expr_1_normal", "expr_2_smile", "expr_5_shy", "expr_4_surprised"];
          const pickExpr = exprPool[Math.floor(Math.random() * exprPool.length)];
          changePose(charId, null, pickExpr);
          const autoLines = charId === "xueling"
            ? [
                "達達達～在桌面上散步真開心 ✨ 點擊我可以摸摸頭喔！",
                "主人工作累了嗎？要不要開個 30 分鐘番茄鐘一起衝刺 💡",
                "嘿嘿，我會自己走來走去陪著你，也可以用滑鼠拎起我拖曳喔！",
                "肚子有點餓了呢～要不要去島民商店買杯珍珠奶茶 🧋？"
              ]
            : [
                "在桌面上巡邏中 🏎️ 需要專注衝刺時隨時叫我！",
                "你可以用滑鼠左鍵按住我拖曳位置，或點下方功能列互動喔 ✨",
                "今天在 Discord 打卡跟骰骰子了嗎？最高點有 +5 EXP 喔 🎲"
              ];
          setSpeech(autoLines[Math.floor(Math.random() * autoLines.length)]);
        }
      }
    }

    if (PET_AI.state === "walk") {
      PET_AI.x += PET_AI.dir * PET_AI.vx;
      if (PET_AI.x > 115) {
        PET_AI.x = 115;
        PET_AI.dir = -1;
      } else if (PET_AI.x < -115) {
        PET_AI.x = -115;
        PET_AI.dir = 1;
      }
      const stepBob = -Math.abs(Math.sin(PET_AI.stepPhase)) * 9.5;
      const stepTilt = Math.sin(PET_AI.stepPhase) * 3.2;
      const flipX = PET_AI.dir < 0 ? 1 : -1;
      wrap.style.transform = `translate(${PET_AI.x.toFixed(1)}px, ${stepBob.toFixed(1)}px) rotate(${stepTilt.toFixed(1)}deg)`;
      img.style.transform = `scaleX(${flipX})`;
    } else if (PET_AI.state === "jump") {
      PET_AI.vy += 0.95;
      PET_AI.y += PET_AI.vy;
      if (PET_AI.y >= 0) {
        PET_AI.y = 0;
        PET_AI.vy = -5.5;
      }
      wrap.style.transform = `translate(${PET_AI.x.toFixed(1)}px, ${PET_AI.y.toFixed(1)}px)`;
    } else {
      const breathY = Math.sin(PET_AI.stepPhase * 0.45) * 4.0;
      wrap.style.transform = `translate(${PET_AI.x.toFixed(1)}px, ${breathY.toFixed(1)}px)`;
    }
  }, 33);
}

window.addEventListener("DOMContentLoaded", () => {
  setTimeout(initAutonomousPetEngine, 200);
});

