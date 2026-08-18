// Shared, mutable app state. Kept tiny and explicit.
export const S = {
  sessionKey: null,
  duration: 0,          // seconds (session length)
  offset: 0,            // playback position in seconds from start
  syncOffset: 0,        // manual second-screen offset (FR-42)
  playing: false,
  speed: 2,
  gapMode: "interval",  // "interval" | "leader"
  activeDriver: null,   // driver_number

  driversByNum: {},     // number -> Driver
  track: null,          // TrackGeometry
  tyres: [],            // DriverStints[]
  totalLaps: null,
  latestTiming: [],     // last frame's timing rows
  latestPositions: [],  // last frame's car positions

  // Темп опроса задаёт сервер (лимиты OpenF1 на живых данных).
  pollIntervalMs: 300,
  // Сглаживание движения машин: между редкими ответами сервера точки
  // доезжают к новым координатам, а не прыгают.
  renderPos: {},        // number -> {x, y}
};

export function teamColor(num) {
  const d = S.driversByNum[num];
  const c = d?.team_colour || "888888";
  return "#" + c.replace(/^#/, "");
}
export function acr(num) {
  return S.driversByNum[num]?.name_acronym || String(num);
}
