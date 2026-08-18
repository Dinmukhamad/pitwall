// Стратегия шин (FR-30..32) — полоса во всю ширину с осью кругов и маркером
// текущего круга, как в макете прототипа.
import { S, acr } from "./state.js";

const wrap = document.getElementById("tyres");
const ticksEl = document.getElementById("ticks");

const COMP_COLOR = {
  SOFT: "#FF3B3B", MEDIUM: "#FFD23F", HARD: "#E8E8E8",
  INTERMEDIATE: "#43D675", WET: "#3AA0FF", UNKNOWN: "#5C6673",
};
const COMP_LETTER = { SOFT: "S", MEDIUM: "M", HARD: "H", INTERMEDIATE: "I", WET: "W", UNKNOWN: "" };

let lastTicks = null;

export function renderTyres() {
  const total = S.totalLaps || Math.max(
    1, ...S.tyres.flatMap((d) => d.stints.map((s) => s.lap_end || 0)));
  const curLap = Math.max(0, ...S.latestTiming.map((r) => r.lap_number ?? 0));

  renderTicks(total);

  // Порядок — по текущей позиции в гонке, иначе таблица и полоса расходятся.
  const order = S.latestTiming.length
    ? S.latestTiming.map((r) => r.driver_number)
    : S.tyres.map((d) => d.driver_number);

  const rows = [];
  for (const num of order) {
    const d = S.tyres.find((x) => x.driver_number === num);
    if (!d) continue;
    const stints = d.stints.map((s) => {
      const from = ((s.lap_start || 1) - 1) / total * 100;
      const width = ((s.lap_end || total) - (s.lap_start || 1) + 1) / total * 100;
      const col = COMP_COLOR[s.compound] || COMP_COLOR.UNKNOWN;
      return `<div class="stint" title="${s.compound} · круги ${s.lap_start}–${s.lap_end}"
        style="left:${from}%;width:${width}%;background:${col}">${
          width > 4 ? (COMP_LETTER[s.compound] ?? "") : ""}</div>`;
    }).join("");
    const nowLeft = Math.min(curLap, total) / total * 100;
    rows.push(`<div class="srow">
      <div class="sc">${acr(num)}</div>
      <div class="stintbar">${stints}<div class="nowline" style="left:${nowLeft}%"></div></div>
    </div>`);
  }
  wrap.innerHTML = rows.join("") || `<div class="state">Нет данных по шинам</div>`;
}

function renderTicks(total) {
  if (lastTicks === total) return;      // ось перерисовываем только при смене гонки
  lastTicks = total;
  const step = total <= 12 ? 2 : total <= 30 ? 5 : 10;
  const marks = [];
  for (let lap = 0; lap <= total; lap += step) marks.push(lap);
  if (marks[marks.length - 1] !== total) marks.push(total);
  ticksEl.innerHTML = marks.map((m) => `<span>${m}</span>`).join("");
}
