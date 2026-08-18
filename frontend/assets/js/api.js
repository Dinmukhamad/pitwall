// Thin API client — one place that knows the backend contract.
const BASE = "";

async function j(url) {
  const r = await fetch(BASE + url, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

export const api = {
  health: () => j(`/api/health`),
  sessions: () => j(`/api/sessions`),
  session: (sk) => j(`/api/sessions/${sk}`),
  drivers: (sk) => j(`/api/sessions/${sk}/drivers`),
  bounds: (sk) => j(`/api/sessions/${sk}/bounds`),
  track: (sk) => j(`/api/sessions/${sk}/track`),
  tyres: (sk) => j(`/api/sessions/${sk}/tyres`),
  frame: (sk, offset) => j(`/api/sessions/${sk}/frame?offset=${offset}`),
  telemetry: (sk, driver, offset, win) =>
    j(`/api/sessions/${sk}/telemetry?driver=${driver}&offset=${offset}&window=${win}`),

  season: (refresh = false) => j(`/api/season${refresh ? "?refresh=true" : ""}`),
  news: (refresh = false) => j(`/api/news${refresh ? "?refresh=true" : ""}`),
};
