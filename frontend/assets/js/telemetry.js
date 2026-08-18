// Панель телеметрии (FR-20..23) — разметка по макету прототипа:
// крупный спидометр, педали газ/тормоз, плитки и график скорости.
import { S, teamColor, acr } from "./state.js";

const panel = document.getElementById("telemetry");
const nameEl = document.getElementById("active-driver");

const COMP_LETTER = { SOFT: "S", MEDIUM: "M", HARD: "H", INTERMEDIATE: "I", WET: "W", UNKNOWN: "–" };
const COMP_COLOR = {
  SOFT: "#FF3B3B", MEDIUM: "#FFD23F", HARD: "#E8E8E8",
  INTERMEDIATE: "#43D675", WET: "#3AA0FF", UNKNOWN: "#5C6673",
};

let built = false;   // разметку строим один раз, дальше только обновляем значения
let el = {};

export function renderTelemetry(tm) {
  if (S.activeDriver == null || !tm) {
    built = false;
    nameEl.textContent = "—";
    panel.innerHTML = `<div class="state">Выберите пилота в таблице или на карте</div>`;
    return;
  }

  const num = tm.driver_number;
  const drv = S.driversByNum[num] || {};
  nameEl.textContent = acr(num);

  if (!built || el.num !== num) build(num, drv);

  const c = tm.current || {};
  el.speed.textContent = c.speed ?? "–";
  el.thrNum.textContent = `${Math.round(c.throttle ?? 0)}%`;
  el.brkNum.textContent = `${Math.round(c.brake ?? 0)}%`;
  el.thrFill.style.width = `${c.throttle ?? 0}%`;
  el.brkFill.style.width = `${c.brake ?? 0}%`;
  el.gear.textContent = c.n_gear ?? "–";
  el.rpm.textContent = c.rpm != null ? c.rpm.toLocaleString("ru") : "–";
  el.drs.textContent = c.drs ? "открыт" : "закр";
  el.drs.className = "v " + (c.drs ? "on" : "off");
  el.tyre.innerHTML = `<span style="color:${COMP_COLOR[tm.compound]}">${COMP_LETTER[tm.compound] ?? "–"}</span>` +
    `<span style="font-size:11px;color:var(--muted);font-weight:600"> ·${tm.tyre_age ?? "–"}кр</span>`;

  drawGraph(tm.samples || []);
}

function build(num, drv) {
  panel.innerHTML = `
    <div class="drvhead">
      <div class="bar" style="background:${teamColor(num)}"></div>
      <div>
        <div class="big">${acr(num)}</div>
        <div class="team">${drv.team_name ?? ""}</div>
      </div>
    </div>

    <div class="speedbig"><span class="n" id="tm-speed">–</span><span class="u">км/ч</span></div>

    <div class="pedals">
      <div class="pedal">
        <div class="plabel"><span>Газ</span><span class="num" id="tm-thr-num">0%</span></div>
        <div class="track2"><div class="f thr" id="tm-thr"></div></div>
      </div>
      <div class="pedal">
        <div class="plabel"><span>Тормоз</span><span class="num" id="tm-brk-num">0%</span></div>
        <div class="track2"><div class="f brk" id="tm-brk"></div></div>
      </div>
    </div>

    <div class="grid2">
      <div class="stat"><div class="k">Передача</div><div class="v" id="tm-gear">–</div></div>
      <div class="stat"><div class="k">Обороты</div><div class="v" id="tm-rpm">–</div></div>
      <div class="stat"><div class="k">DRS</div><div class="v off" id="tm-drs">–</div></div>
      <div class="stat"><div class="k">Шина</div><div class="v" id="tm-tyre">–</div></div>
    </div>

    <div class="trace">
      <h3>Скорость · последние секунды</h3>
      <canvas id="spd"></canvas>
    </div>`;

  el = {
    num,
    speed: document.getElementById("tm-speed"),
    thrNum: document.getElementById("tm-thr-num"),
    brkNum: document.getElementById("tm-brk-num"),
    thrFill: document.getElementById("tm-thr"),
    brkFill: document.getElementById("tm-brk"),
    gear: document.getElementById("tm-gear"),
    rpm: document.getElementById("tm-rpm"),
    drs: document.getElementById("tm-drs"),
    tyre: document.getElementById("tm-tyre"),
    canvas: document.getElementById("spd"),
  };
  built = true;
}

function drawGraph(samples) {
  const cv = el.canvas;
  if (!cv) return;
  const ctx = cv.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth || 300, h = cv.clientHeight || 70;
  cv.width = w * dpr; cv.height = h * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  if (samples.length < 2) return;

  const max = Math.max(340, ...samples.map((s) => s.speed ?? 0));
  const pad = 5;
  const X = (i) => pad + (i / (samples.length - 1)) * (w - pad * 2);
  const Y = (v) => h - pad - (v / max) * (h - pad * 2);

  ctx.beginPath();
  samples.forEach((s, i) => {
    const x = X(i), y = Y(s.speed ?? 0);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.lineTo(X(samples.length - 1), h - pad);
  ctx.lineTo(X(0), h - pad);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, "rgba(47,212,122,.28)");
  grad.addColorStop(1, "rgba(47,212,122,0)");
  ctx.fillStyle = grad; ctx.fill();

  ctx.beginPath();
  samples.forEach((s, i) => {
    const x = X(i), y = Y(s.speed ?? 0);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.strokeStyle = "#2FD47A"; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.stroke();
}
