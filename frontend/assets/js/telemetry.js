// Telemetry panel + rolling speed graph (FR-20..23).
import { S, acr } from "./state.js";

const el = {
  active: document.getElementById("active-driver"),
  speed: document.getElementById("tm-speed"),
  gear: document.getElementById("tm-gear"),
  rpm: document.getElementById("tm-rpm"),
  drs: document.getElementById("tm-drs"),
  throttle: document.getElementById("tm-throttle"),
  brake: document.getElementById("tm-brake"),
  tyre: document.getElementById("tyre-now"),
  canvas: document.getElementById("speed-graph"),
};
const ctx = el.canvas.getContext("2d");

export function renderTelemetry(tm) {
  if (!tm || S.activeDriver == null) {
    el.active.textContent = "— выберите пилота";
    return;
  }
  el.active.textContent = acr(S.activeDriver);
  const c = tm.current || {};
  el.speed.textContent = c.speed ?? "–";
  el.gear.textContent = c.n_gear ?? "–";
  el.rpm.textContent = c.rpm ?? "–";
  el.drs.textContent = c.drs ? "OPEN" : "—";
  el.drs.style.color = c.drs ? "var(--green)" : "var(--muted)";
  el.throttle.style.width = (c.throttle ?? 0) + "%";
  el.brake.style.width = (c.brake ?? 0) + "%";
  el.tyre.innerHTML = `Шина: <b>${tm.compound}</b> · возраст <b>${tm.tyre_age ?? "–"}</b> кр.`;
  drawGraph(tm.samples || []);
}

function drawGraph(samples) {
  const dpr = window.devicePixelRatio || 1;
  const w = el.canvas.clientWidth, h = 120;
  el.canvas.width = w * dpr; el.canvas.height = h * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  if (samples.length < 2) return;

  const speeds = samples.map((s) => s.speed ?? 0);
  const max = Math.max(340, ...speeds), min = 0;
  const pad = 6;
  const X = (i) => pad + (i / (samples.length - 1)) * (w - pad * 2);
  const Y = (v) => h - pad - ((v - min) / (max - min)) * (h - pad * 2);

  // gridlines
  ctx.strokeStyle = "#222b3a"; ctx.lineWidth = 1;
  [100, 200, 300].forEach((g) => {
    ctx.beginPath(); ctx.moveTo(pad, Y(g)); ctx.lineTo(w - pad, Y(g)); ctx.stroke();
    ctx.fillStyle = "#4a556b"; ctx.font = "9px sans-serif";
    ctx.fillText(String(g), 2, Y(g) - 2);
  });

  // area + line
  ctx.beginPath();
  samples.forEach((s, i) => { const x = X(i), y = Y(s.speed ?? 0); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
  ctx.lineTo(X(samples.length - 1), h - pad); ctx.lineTo(X(0), h - pad); ctx.closePath();
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, "rgba(55,224,200,0.35)");
  grad.addColorStop(1, "rgba(55,224,200,0)");
  ctx.fillStyle = grad; ctx.fill();

  ctx.beginPath();
  samples.forEach((s, i) => { const x = X(i), y = Y(s.speed ?? 0); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
  ctx.strokeStyle = "#37e0c8"; ctx.lineWidth = 2; ctx.stroke();
}
