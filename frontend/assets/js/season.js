// Экран «Сезон»: календарь и зачёты (данные — GET /api/season).
// Считать и нормализовать всё уже нечего: бэкенд отдаёт готовую модель.
import { api } from "./api.js";

const body = document.getElementById("season-body");
let loaded = false;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 > 20)) return few;
  return many;
};

export async function loadSeason(force = false) {
  body.innerHTML = `<div class="state">Загружаю данные сезона…</div>`;
  try {
    const data = await api.season(force);
    if (data.error) return renderError(data.error);
    render(data);
    loaded = true;
  } catch (e) {
    renderError(String(e));
  }
}

export function ensureSeason() { if (!loaded) loadSeason(); }

function renderError(msg) {
  body.innerHTML = `
    <div class="state">
      <b>Не удалось загрузить данные сезона</b>
      Источник Jolpica-F1 не ответил. Проверьте подключение и попробуйте ещё раз.
      <small>${esc(msg)}</small>
      <button class="retry" id="season-retry">Повторить</button>
    </div>`;
  document.getElementById("season-retry").onclick = () => loadSeason(true);
}

function ring(pct, big, sub) {
  const r = 42, c = 2 * Math.PI * r, off = c * (1 - pct);
  return `<svg viewBox="0 0 100 100" class="ring">
    <circle cx="50" cy="50" r="${r}" fill="none" stroke="#263042" stroke-width="8"/>
    <circle cx="50" cy="50" r="${r}" fill="none" stroke="#37e0c8" stroke-width="8" stroke-linecap="round"
      stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}" transform="rotate(-90 50 50)"/>
    <text x="50" y="48" text-anchor="middle" class="ringbig">${esc(big)}</text>
    <text x="50" y="64" text-anchor="middle" class="ringsub">${esc(sub)}</text></svg>`;
}

function donut(segs) {
  const total = segs.reduce((a, s) => a + s.value, 0) || 1;
  const r = 40, c = 2 * Math.PI * r;
  let acc = 0, arcs = "";
  for (const s of segs) {
    const len = c * (s.value / total);
    arcs += `<circle cx="50" cy="50" r="${r}" fill="none" stroke="${s.color}" stroke-width="13"
      stroke-dasharray="${len.toFixed(1)} ${(c - len).toFixed(1)}"
      stroke-dashoffset="${(-acc).toFixed(1)}" transform="rotate(-90 50 50)"/>`;
    acc += len;
  }
  return `<svg viewBox="0 0 100 100" class="donut">
    <circle cx="50" cy="50" r="${r}" fill="none" stroke="#1b2231" stroke-width="13"/>${arcs}</svg>`;
}

function bars(rows, label) {
  if (!rows.length) return `<div class="state">Нет данных</div>`;
  const max = Math.max(...rows.map((r) => r.points), 1);
  return `<div class="bars">` + rows.map((r) => `
    <div class="barrow">
      <div class="bpos">${r.position}</div>
      <div class="bname"><b>${esc(label(r).main)}</b><span>${esc(label(r).sub)}</span></div>
      <div class="btrack"><div class="bfill" style="width:${Math.max(1, (r.points / max) * 100)}%;
        background:#${esc(r.team_colour)}"></div></div>
      <div class="bval">${r.points}</div>
    </div>`).join("") + `</div>`;
}

function render(d) {
  const pct = d.races_total ? d.races_done / d.races_total : 0;
  const dLead = d.drivers[0], dSec = d.drivers[1];
  const cLead = d.constructors[0], cSec = d.constructors[1];

  const nextTile = d.next_race
    ? `<div class="kpi"><div>
         <div class="kl">следующая гонка · этап ${d.next_race.round}</div>
         <div class="kv accent">${d.days_to_next ?? "—"}
           <span style="font-size:13px;font-weight:600">${plural(d.days_to_next ?? 0, "день", "дня", "дней")}</span></div>
         <div class="ks">${esc(d.next_race.name)}<br>${esc(d.next_race.locality ?? "")}, ${esc(d.next_race.country ?? "")}</div>
       </div></div>`
    : `<div class="kpi"><div><div class="kl">сезон</div>
         <div class="kv accent">Финиш</div><div class="ks">Все этапы проведены</div></div></div>`;

  const drvTile = dLead ? `<div class="kpi"><div>
      <div class="kl">лидер · личный зачёт</div>
      <div class="kv">${esc(dLead.code)}</div>
      <div class="ks"><b style="color:var(--text)">${dLead.points}</b> очк.${
        dSec ? ` · отрыв +${(dLead.points - dSec.points).toFixed(0)} от ${esc(dSec.code)}` : ""}</div>
    </div></div>` : "";

  const conTile = cLead ? `<div class="kpi"><div>
      <div class="kl">лидер · конструкторы</div>
      <div class="kv" style="font-size:19px">${esc(cLead.name)}</div>
      <div class="ks"><b style="color:var(--text)">${cLead.points}</b> очк.${
        cSec ? ` · отрыв +${(cLead.points - cSec.points).toFixed(0)}` : ""}</div>
    </div></div>` : "";

  const segs = d.constructors.map((c) => ({ value: c.points, color: "#" + c.team_colour, name: c.name }));
  const segTotal = segs.reduce((a, s) => a + s.value, 0) || 1;
  const legend = segs.map((s) => `<div class="lg"><i style="background:${s.color}"></i>${esc(s.name)}
      <span class="v">${Math.round((s.value / segTotal) * 100)}%</span></div>`).join("");

  const marks = d.calendar.map((r) => {
    const x = d.calendar.length > 1 ? ((r.round - 1) / (d.calendar.length - 1)) * 100 : 0;
    const col = r.is_next ? "#37e0c8" : r.is_past ? "#2ee06a" : "#4a556b";
    return `<div class="tlmark" style="left:${x}%;background:${col}"></div>`;
  }).join("");

  const chips = d.calendar.map((r) => {
    const cls = r.is_next ? "next" : r.is_past ? "done" : "up";
    const date = r.date
      ? new Date(r.date).toLocaleDateString("ru", { day: "numeric", month: "short" }) : "";
    return `<div class="rchip ${cls}">
      <b>${r.round}. ${esc((r.name || "").replace(/ Grand Prix/i, ""))}</b>
      <div class="c">${esc(r.country ?? "")}</div><div class="d">${date}</div></div>`;
  }).join("");

  body.innerHTML = `
    <div class="page-head">
      <div>
        <h1>Сезон Формулы-1 · ${esc(d.season)}</h1>
        <div class="sub">Прошло этапов: ${d.races_done} из ${d.races_total} · осталось ${d.races_total - d.races_done}</div>
      </div>
      <button class="retry" id="season-refresh">↻ обновить</button>
    </div>

    <div class="kpis">
      <div class="kpi">${ring(pct, `${d.races_done}/${d.races_total}`, "этапов")}
        <div><div class="kl">прогресс сезона</div><div class="kv">${Math.round(pct * 100)}%</div>
        <div class="ks">осталось ${d.races_total - d.races_done}</div></div></div>
      ${drvTile}${conTile}${nextTile}
    </div>

    <div class="card"><h2>Личный зачёт · очки</h2>
      ${bars(d.drivers, (r) => ({ main: r.code, sub: r.team_name ?? "" }))}</div>

    <div class="two-col">
      <div class="card"><h2>Кубок конструкторов · очки</h2>
        ${bars(d.constructors, (r) => ({ main: r.name, sub: "" }))}</div>
      <div class="card"><h2>Доля очков по командам</h2>
        <div class="donutwrap">${donut(segs)}<div class="legend">${legend}</div></div></div>
    </div>

    <div class="card"><h2>Календарь ${esc(d.season)} · ${d.races_total} этапов</h2>
      <div class="tl"><div class="tlbar"><div class="tlfill" style="width:${pct * 100}%"></div>${marks}</div></div>
      <div class="cal">${chips}</div></div>`;

  document.getElementById("season-refresh").onclick = () => loadSeason(true);
}
