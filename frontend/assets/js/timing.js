// Timing Tower renderer (FR-01..06).
import { S, teamColor, acr } from "./state.js";
import { fmtLap, fmtGap } from "./format.js";

const tower = document.getElementById("tower");

export function renderTower(onSelect) {
  const rows = S.latestTiming;
  tower.innerHTML = "";
  for (const r of rows) {
    const li = document.createElement("li");
    li.dataset.num = r.driver_number;
    if (r.driver_number === S.activeDriver) li.classList.add("active");
    if (r.is_fastest_lap) li.classList.add("fastest");
    else if (r.is_personal_best) li.classList.add("pb");

    const isLeader = r.position === 1;
    const gapVal = S.gapMode === "leader" ? r.gap_to_leader : r.interval;
    const comp = r.compound || "UNKNOWN";

    li.innerHTML = `
      <span class="c-pos">${r.position ?? "–"}</span>
      <span class="c-drv">
        <span class="team-bar" style="background:${teamColor(r.driver_number)}"></span>
        <span class="acr">${acr(r.driver_number)}</span>
        <span class="tyre-badge tyre-${comp}">${comp[0] || "?"}</span>
      </span>
      <span class="c-gap ${isLeader ? "lead" : ""}">${fmtGap(gapVal, isLeader)}</span>
      <span class="c-lap">${fmtLap(r.last_lap)}</span>
      <span class="c-ind">
        <span class="ind drs ${r.drs ? "on" : ""}">DRS</span>
        ${r.in_pit ? '<span class="ind pit">PIT</span>' : ""}
      </span>`;
    li.onclick = () => onSelect(r.driver_number);
    tower.appendChild(li);
  }
}
