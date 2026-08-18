// Tyre strategy timeline (FR-30..32).
import { S, acr, teamColor } from "./state.js";

const wrap = document.getElementById("tyres");
const COMP_COLOR = {
  SOFT: "#ff3b3b", MEDIUM: "#ffd23f", HARD: "#e8e8e8",
  INTERMEDIATE: "#43d675", WET: "#3aa0ff", UNKNOWN: "#55607a",
};

export function renderTyres() {
  const total = S.totalLaps || Math.max(
    1, ...S.tyres.flatMap((d) => d.stints.map((s) => s.lap_end || 0)));
  const curLap = currentLap();
  // order by current position if we have timing
  const order = S.latestTiming.length
    ? S.latestTiming.map((r) => r.driver_number)
    : S.tyres.map((d) => d.driver_number);

  wrap.innerHTML = "";
  for (const num of order) {
    const d = S.tyres.find((x) => x.driver_number === num);
    if (!d) continue;
    const row = document.createElement("div");
    row.className = "tyre-row";
    const bars = d.stints.map((s) => {
      const start = (s.lap_start || 1) - 1, end = s.lap_end || total;
      const width = ((end - start) / total) * 100;
      return `<span class="stint" title="${s.compound} • круги ${s.lap_start}–${s.lap_end}"
        style="width:${width}%;background:${COMP_COLOR[s.compound] || COMP_COLOR.UNKNOWN}"></span>`;
    }).join("");
    const markLeft = (Math.min(curLap, total) / total) * 100;
    row.innerHTML = `
      <span class="who"><span class="team-bar" style="background:${teamColor(num)}"></span>${acr(num)}</span>
      <span class="stints">${bars}<span class="now-marker" style="left:${markLeft}%"></span></span>`;
    wrap.appendChild(row);
  }
}

function currentLap() {
  const laps = S.latestTiming.map((r) => r.lap_number).filter((x) => x != null);
  return laps.length ? Math.max(...laps) : 0;
}
