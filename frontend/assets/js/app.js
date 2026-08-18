// Bootstrap + orchestration: session load, playback clock, control wiring.
import { api } from "./api.js";
import { S } from "./state.js";
import { fmtClock } from "./format.js";
import { renderTower } from "./timing.js";
import { renderTelemetry } from "./telemetry.js";
import { renderTyres } from "./tyres.js";
import { MapView } from "./map.js";
import { ensureSeason } from "./season.js";
import { ensureNews } from "./news.js";

const maps = [];
const mapsWrap = document.getElementById("maps-wrap");
const TELE_WINDOW = 30;
let busy = false;

// ---------- Шапка ----------
const H = {
  flag: document.getElementById("flag"),
  lapCur: document.getElementById("lap-current"),
  lapTot: document.getElementById("lap-total"),
  weather: document.getElementById("weather"),
  conn: document.getElementById("conn-status"),
  connLabel: document.getElementById("conn-label"),
  clock: document.getElementById("clock"),
  mapsCount: document.getElementById("maps-count"),
};
// Флаг показываем короткой меткой, как в макете: GREEN / SC / RED …
const FLAG = {
  GREEN: ["GREEN", ""], YELLOW: ["YELLOW", "yellow"], DOUBLE_YELLOW: ["2× YELLOW", "yellow"],
  SC: ["SAFETY CAR", "sc"], VSC: ["VSC", "vsc"], RED: ["RED", "red"],
  CHEQUERED: ["FINISH", "chequered"], UNKNOWN: ["—", ""],
};

function setConn(state, label) {
  H.conn.className = "demo-badge" + (state === "ok" ? "" : state === "err" ? " err" : "");
  H.connLabel.textContent = label;
}

// ---------- Session lifecycle ----------
async function loadSessions() {
  const sessions = await api.sessions();
  const sel = document.getElementById("session-select");
  sel.innerHTML = "";
  // Подпись: номер этапа, страна и трасса — так список читается как календарь.
  // Этапы уже отсортированы по дате, поэтому номер = порядковый индекс.
  sessions.forEach((s, i) => {
    const opt = document.createElement("option");
    opt.value = s.session_key;
    const where = [s.country, s.circuit].filter(Boolean).join(" · ");
    opt.textContent = `${i + 1}. ${where || s.session_name || "Race"}`;
    sel.appendChild(opt);
  });
  sel.onchange = () => loadSession(+sel.value);
  if (sessions.length) await loadSession(sessions[0].session_key);
}

async function loadSession(sk) {
  stop();
  S.sessionKey = sk;
  S.offset = 0; S.activeDriver = null; S.latestTiming = []; S.latestPositions = [];

  const [info, drivers, bounds, track, tyres] = await Promise.all([
    api.session(sk), api.drivers(sk), api.bounds(sk), api.track(sk), api.tyres(sk),
  ]);
  S.driversByNum = Object.fromEntries(drivers.map((d) => [d.driver_number, d]));
  S.totalLaps = info.total_laps;
  S.track = track;
  S.tyres = tyres;
  S.duration = (new Date(bounds.end) - new Date(bounds.start)) / 1000;

  H.lapTot.textContent = info.total_laps ?? "–";

  // rebuild maps (start with one)
  maps.forEach((m) => m.destroy()); maps.length = 0;
  addMap(false);
  renderTyres();
  updateMapsCount();
  await refresh();
}

// ---------- Maps ----------
function addMap(removable = true) {
  if (maps.length >= 3) return;
  const m = new MapView(mapsWrap, {
    onSelect: selectDriver,
    onRemove: removeMap,
    removable: removable || maps.length > 0,
  });
  maps.push(m);
  updateMapsCount();
}
function removeMap(m) {
  if (maps.length <= 1) return;         // FR-14: at least one stays
  m.destroy();
  maps.splice(maps.indexOf(m), 1);
  updateMapsCount();
}
function updateMapsCount() {
  H.mapsCount.textContent = `${maps.length} / 3`;
  document.getElementById("add-map").disabled = maps.length >= 3;
}

// ---------- Data refresh ----------
function effOffset() {
  return Math.max(0, Math.min(S.duration, S.offset + S.syncOffset));
}

async function refresh() {
  if (busy || S.sessionKey == null) return;
  busy = true;
  try {
    const off = effOffset();
    const frame = await api.frame(S.sessionKey, off.toFixed(2));
    S.latestTiming = frame.timing || [];
    S.latestPositions = frame.positions || [];

    // Шапка: флаг, круг, погода (FR-50, FR-51)
    const [flagText, flagCls] = FLAG[frame.flag] || FLAG.UNKNOWN;
    H.flag.textContent = flagText;
    H.flag.className = "flag race-only " + flagCls;
    H.lapCur.textContent = frame.lap ?? "–";
    if (frame.total_laps) H.lapTot.textContent = frame.total_laps;

    const w = frame.weather || {};
    H.weather.textContent = w.air_temperature != null
      ? `возд ${w.air_temperature}° · трасса ${w.track_temperature ?? "–"}° · ` +
        `влажн ${w.humidity ?? "–"}% · ветер ${w.wind_speed ?? "–"} м/с`
      : "";

    renderTower(selectDriver);
    renderTyres();
    seedRenderPositions();
    maps.forEach((m) => m.redraw());

    if (S.activeDriver != null) {
      const tm = await api.telemetry(S.sessionKey, S.activeDriver, off.toFixed(2), TELE_WINDOW);
      renderTelemetry(tm);
    }

    if (!S.latestPositions.length) setConn("stale", "данные задерживаются");
  } catch (e) {
    console.error(e);
    setConn("err", "нет связи");
  } finally {
    busy = false;
    updateClock();
  }
}

// ---------- Плавное движение машин ----------
// Сервер отдаёт координаты редко (на живых данных — раз в ~1.5 с из-за лимитов
// OpenF1). Чтобы точки не прыгали, каждая машина «доезжает» к новой позиции.
function seedRenderPositions() {
  for (const p of S.latestPositions) {
    if (!S.renderPos[p.driver_number]) S.renderPos[p.driver_number] = { x: p.x, y: p.y };
  }
}

function animate() {
  let moved = false;
  for (const p of S.latestPositions) {
    const rp = S.renderPos[p.driver_number];
    if (!rp) continue;
    const dx = p.x - rp.x, dy = p.y - rp.y;
    const dist = Math.hypot(dx, dy);
    if (dist < 0.5) { rp.x = p.x; rp.y = p.y; continue; }
    // Экспоненциальное сближение; при большом скачке (новый круг) — телепорт.
    const k = dist > 400 ? 1 : 0.18;
    rp.x += dx * k; rp.y += dy * k;
    moved = true;
  }
  if (moved) maps.forEach((m) => m.redraw());
  requestAnimationFrame(animate);
}

function selectDriver(num) {
  S.activeDriver = num;
  renderTower(selectDriver);
  maps.forEach((m) => m.redraw());
  // immediate telemetry pull
  api.telemetry(S.sessionKey, num, effOffset().toFixed(2), TELE_WINDOW)
    .then(renderTelemetry).catch(() => {});
}

// ---------- Playback clock ----------
let timer = null;
let lastFetch = 0;
function play() {
  if (S.playing) return;
  S.playing = true;
  document.getElementById("play-btn").textContent = "⏸";
  const TICK = 100;
  lastFetch = 0;
  timer = setInterval(() => {
    // Часы идут плавно (100 мс), а к серверу обращаемся в темпе
    // pollIntervalMs — иначе на живых данных мы бы упёрлись в лимиты OpenF1.
    S.offset += (TICK / 1000) * S.speed;
    if (S.offset >= S.duration) { S.offset = S.duration; stop(); }
    syncScrubber();
    updateClock();
    const now = performance.now();
    if (now - lastFetch >= S.pollIntervalMs) {
      lastFetch = now;
      refresh();
    }
  }, TICK);
}
function stop() {
  S.playing = false;
  document.getElementById("play-btn").textContent = "▶";
  if (timer) { clearInterval(timer); timer = null; }
}
function togglePlay() { S.playing ? stop() : play(); }

function updateClock() {
  H.clock.textContent = `${fmtClock(effOffset())} / ${fmtClock(S.duration)}`;
}
function syncScrubber() {
  const sc = document.getElementById("scrubber");
  sc.value = S.duration ? (S.offset / S.duration) * 100 : 0;
}

// ---------- Controls ----------
function wireControls() {
  document.getElementById("play-btn").onclick = togglePlay;
  document.getElementById("add-map").onclick = () => addMap(true);

  document.querySelectorAll(".spd").forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll(".spd").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      S.speed = +b.dataset.spd;
    };
  });

  const sc = document.getElementById("scrubber");
  sc.oninput = () => { S.offset = (sc.value / 100) * S.duration; refresh(); };

  document.getElementById("offset").onchange = (e) => {
    S.syncOffset = +e.target.value || 0; refresh();
  };

  // Переключение режима разрыва (FR-03): активный режим выделен жирным
  const gapBtn = document.getElementById("gap-toggle");
  const paintGap = () => {
    gapBtn.innerHTML = S.gapMode === "interval"
      ? `<b style="color:var(--muted)">интервал</b> ▸ к лидеру`
      : `интервал ▸ <b style="color:var(--muted)">к лидеру</b>`;
  };
  paintGap();
  gapBtn.onclick = () => {
    S.gapMode = S.gapMode === "interval" ? "leader" : "interval";
    paintGap();
    renderTower(selectDriver);
  };

  wireViews();
}

// ---------- Переключение разделов ----------
// Данные вкладки грузятся при первом открытии, а не на старте: экран гонки
// не должен ждать сезон и новости.
const VIEWS = {
  race: { el: "view-race", btn: "v-race" },
  season: { el: "view-season", btn: "v-season", load: ensureSeason },
  news: { el: "view-news", btn: "v-news", load: ensureNews },
};

function showView(name) {
  for (const [key, v] of Object.entries(VIEWS)) {
    const on = key === name;
    document.getElementById(v.el).classList.toggle("hidden", !on);
    const btn = document.getElementById(v.btn);
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-selected", String(on));
  }
  document.body.classList.toggle("on-race", name === "race");
  // Плеер отсчитывает время только на видимом экране гонки.
  if (name !== "race" && S.playing) stop();
  VIEWS[name].load?.();
}

function wireViews() {
  for (const [key, v] of Object.entries(VIEWS)) {
    document.getElementById(v.btn).onclick = () => showView(key);
  }
  document.body.classList.add("on-race");
}

// ---------- Init ----------
async function init() {
  wireControls();
  try {
    const h = await api.health();
    S.pollIntervalMs = h.poll_interval_ms || 300;
    // Бейдж честно говорит, что на экране: имитация или живые данные.
    if (h.data_source === "openf1") {
      H.conn.className = "demo-badge live";
      H.connLabel.textContent = "openf1 · live";
    } else {
      setConn("ok", "demo · симуляция");
    }
  } catch { setConn("err", "нет связи с бэкендом"); }
  await loadSessions();
  updateClock();
  requestAnimationFrame(animate);
}
init();
