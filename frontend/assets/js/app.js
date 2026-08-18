// Bootstrap + orchestration: session load, playback clock, control wiring.
import { api } from "./api.js";
import { S } from "./state.js";
import { fmtClock } from "./format.js";
import { renderTower } from "./timing.js";
import { renderTelemetry } from "./telemetry.js";
import { renderTyres } from "./tyres.js";
import { MapView } from "./map.js";

const maps = [];
const mapsWrap = document.getElementById("maps-wrap");
const TELE_WINDOW = 30;
let busy = false;

// ---------- Header ----------
const H = {
  flagChip: document.getElementById("flag-chip"),
  flagLabel: document.getElementById("flag-label"),
  lapCur: document.getElementById("lap-current"),
  lapTot: document.getElementById("lap-total"),
  air: document.getElementById("w-air"), track: document.getElementById("w-track"),
  hum: document.getElementById("w-hum"), wind: document.getElementById("w-wind"),
  conn: document.getElementById("conn-status"), connLabel: document.getElementById("conn-label"),
  clock: document.getElementById("clock"),
};
const FLAG_LABEL = {
  GREEN: "Зелёный", YELLOW: "Жёлтый", DOUBLE_YELLOW: "2×Жёлтый",
  SC: "Safety Car", VSC: "Вирт. SC", RED: "Красный", CHEQUERED: "Финиш", UNKNOWN: "—",
};

function setConn(state, label) {
  H.conn.className = "conn " + state;
  H.connLabel.textContent = label;
}

// ---------- Session lifecycle ----------
async function loadSessions() {
  const sessions = await api.sessions();
  const sel = document.getElementById("session-select");
  sel.innerHTML = "";
  for (const s of sessions) {
    const opt = document.createElement("option");
    opt.value = s.session_key;
    opt.textContent = `${s.year ?? ""} · ${s.country ?? s.circuit ?? "Race"} · ${s.session_name ?? ""}`.trim();
    sel.appendChild(opt);
  }
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
  document.getElementById("maps-count").textContent = `${maps.length} / 3`;
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

    // header
    H.flagChip.dataset.flag = frame.flag;
    H.flagLabel.textContent = FLAG_LABEL[frame.flag] || frame.flag;
    H.lapCur.textContent = frame.lap ?? "–";
    if (frame.total_laps) H.lapTot.textContent = frame.total_laps;
    const w = frame.weather || {};
    H.air.textContent = w.air_temperature ?? "–";
    H.track.textContent = w.track_temperature ?? "–";
    H.hum.textContent = w.humidity ?? "–";
    H.wind.textContent = w.wind_speed ?? "–";

    renderTower(selectDriver);
    renderTyres();
    maps.forEach((m) => m.redraw());

    if (S.activeDriver != null) {
      const tm = await api.telemetry(S.sessionKey, S.activeDriver, off.toFixed(2), TELE_WINDOW);
      renderTelemetry(tm);
    }

    setConn(S.latestPositions.length ? "ok" : "stale",
      S.latestPositions.length ? "данные ок" : "данные задерживаются");
  } catch (e) {
    console.error(e);
    setConn("err", "нет связи");
  } finally {
    busy = false;
    updateClock();
  }
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
function play() {
  if (S.playing) return;
  S.playing = true;
  document.getElementById("play-btn").textContent = "⏸";
  const TICK = 250;
  timer = setInterval(() => {
    S.offset += (TICK / 1000) * S.speed;
    if (S.offset >= S.duration) { S.offset = S.duration; stop(); }
    syncScrubber();
    refresh();
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

  const gapBtn = document.getElementById("gap-toggle");
  gapBtn.onclick = () => {
    S.gapMode = S.gapMode === "interval" ? "leader" : "interval";
    document.getElementById("gap-mode").textContent =
      S.gapMode === "interval" ? "интервал" : "от лидера";
    document.getElementById("gap-col-label").textContent =
      S.gapMode === "interval" ? "Инт." : "Лидер";
    renderTower(selectDriver);
  };

  // mode switch (Live requires openf1 source — informational for now)
  document.getElementById("mode-replay").onclick = () => setMode("replay");
  document.getElementById("mode-live").onclick = () => setMode("live");
}

function setMode(mode) {
  document.getElementById("mode-replay").classList.toggle("active", mode === "replay");
  document.getElementById("mode-live").classList.toggle("active", mode === "live");
  if (mode === "live") {
    // Live continuously advances toward "now"; here we just keep polling head.
    setConn("stale", "Live: нужен источник openf1");
  }
}

// ---------- Init ----------
async function init() {
  wireControls();
  try {
    const h = await api.health();
    setConn("ok", `${h.data_source} · ${h.cache_backend}`);
  } catch { setConn("err", "backend недоступен"); }
  await loadSessions();
  updateClock();
}
init();
