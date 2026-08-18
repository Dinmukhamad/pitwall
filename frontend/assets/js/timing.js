// Timing Tower (FR-01..06) — разметка по макету прототипа.
import { S, teamColor, acr } from "./state.js";
import { fmtLap, fmtGap } from "./format.js";

const tower = document.getElementById("tower");
const COMP_LETTER = { SOFT: "S", MEDIUM: "M", HARD: "H", INTERMEDIATE: "I", WET: "W", UNKNOWN: "–" };
const COMP_COLOR = {
  SOFT: "#FF3B3B", MEDIUM: "#FFD23F", HARD: "#E8E8E8",
  INTERMEDIATE: "#43D675", WET: "#3AA0FF", UNKNOWN: "#5C6673",
};

export function renderTower(onSelect) {
  tower.innerHTML = "";
  for (const r of S.latestTiming) {
    const isLeader = r.position === 1;
    const gapVal = S.gapMode === "leader" ? r.gap_to_leader : r.interval;
    const comp = r.compound || "UNKNOWN";

    // Класс подсветки круга: фиолетовый — быстрейший круг гонки (FR-04),
    // зелёный — личный лучший.
    const lapCls = r.is_fastest_lap ? "fl" : r.is_personal_best ? "pb" : "";

    const row = document.createElement("div");
    row.className = "row" + (r.driver_number === S.activeDriver ? " sel" : "");
    row.dataset.num = r.driver_number;
    row.innerHTML = `
      <div class="pos">${r.position ?? "–"}</div>
      <div class="teambar" style="background:${teamColor(r.driver_number)}"></div>
      <div class="code">${acr(r.driver_number)}</div>
      <div class="midcol">
        <span class="lastlap ${lapCls}">${fmtLap(r.last_lap)}</span>
      </div>
      <div class="gap${isLeader ? " leader" : ""}">${isLeader ? "LEADER" : fmtGap(gapVal, false)}</div>
      <div class="tyre" style="color:${COMP_COLOR[comp]}">${COMP_LETTER[comp] ?? "–"}</div>
      ${r.in_pit
        ? `<div class="tag pit">PIT</div>`
        : `<div class="tag ${r.drs ? "drs" : "off"}">DRS</div>`}`;
    row.onclick = () => onSelect(r.driver_number);
    tower.appendChild(row);
  }
}
