export function fmtClock(sec) {
  sec = Math.max(0, Math.floor(sec));
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function fmtLap(sec) {
  if (sec == null) return "–";
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(3);
  return m > 0 ? `${m}:${s.padStart(6, "0")}` : `${(+s).toFixed(3)}`;
}

export function fmtGap(v, isLeader) {
  if (v == null) return "–";
  if (isLeader) return "—";
  if (v === 0) return "+0.000";
  return "+" + v.toFixed(3);
}
