// Экран «Новости»: лента из GET /api/news.
// Сбор, разбор RSS, дедуп и выбор источников — на бэкенде; здесь только показ
// и фильтр по уже полученным материалам.
import { api } from "./api.js";

const body = document.getElementById("news-body");
let loaded = false;
let feed = { items: [], sources: [], failed_sources: [] };
let enabled = new Set();

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function timeAgo(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(+d)) return "";
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return "только что";
  const m = s / 60; if (m < 60) return `${Math.floor(m)} мин назад`;
  const h = m / 60; if (h < 24) return `${Math.floor(h)} ч назад`;
  const dd = h / 24; if (dd < 7) return `${Math.floor(dd)} дн назад`;
  return d.toLocaleDateString("ru", { day: "numeric", month: "long" });
}

export async function loadNews(force = false) {
  body.innerHTML = `<div class="state">Загружаю новости…</div>`;
  try {
    feed = await api.news(force);
    // При первой загрузке показываем все пришедшие источники.
    if (!enabled.size) {
      enabled = new Set(feed.sources.filter((s) => s.enabled).map((s) => s.id));
    }
    loaded = true;
    render();
  } catch (e) {
    renderError(String(e));
  }
}

export function ensureNews() { if (!loaded) loadNews(); }

function renderError(msg) {
  body.innerHTML = `
    <div class="state">
      <b>Не удалось загрузить новости</b>
      Источники RSS не ответили. Попробуйте ещё раз.
      <small>${esc(msg)}</small>
      <button class="retry" id="news-retry">Повторить</button>
    </div>`;
  document.getElementById("news-retry").onclick = () => loadNews(true);
}

function render() {
  if (!feed.items.length) return renderError(feed.error || "Пустая лента");

  const chips = feed.sources.map((s) => {
    const on = enabled.has(s.id);
    return `<button class="chip${on ? " on" : ""}" data-src="${esc(s.id)}"
      style="border-left-color:#${esc(s.colour)}">${esc(s.name)}</button>`;
  }).join("");

  const items = feed.items.filter((a) => enabled.has(a.source_id));
  const colourOf = (a) =>
    "#" + (feed.sources.find((s) => s.id === a.source_id)?.colour || "8A9099");

  const cards = items.map((a) => {
    const col = colourOf(a);
    const thumb = a.image_url
      ? `<div class="thumb" style="background-image:url('${esc(a.image_url).replace(/'/g, "%27")}')"></div>` : "";
    return `<a class="ncard" href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">
      ${thumb}
      <div class="nbody">
        <div class="ntop">
          <span class="nsrc" style="color:${col};background:${col}22">${esc(a.source)}</span>
          <span class="ntime">${timeAgo(a.published_at)}</span>
        </div>
        <div class="ntitle">${esc(a.title)}</div>
        ${a.excerpt ? `<div class="nexcerpt">${esc(a.excerpt)}</div>` : ""}
      </div></a>`;
  }).join("") || `<div class="state">Нет новостей по выбранным источникам</div>`;

  // Не делаем вид, что это всё: неответившие ленты называем явно.
  const warn = feed.failed_sources?.length
    ? `<div class="warnbar">Не ответили: ${esc(feed.failed_sources.join(", "))} — показаны материалы остальных источников.</div>`
    : "";

  body.innerHTML = `
    <div class="page-head">
      <div>
        <h1>Новости Формулы-1</h1>
        <div class="sub">Агрегируется на сервере из RSS-источников · ${feed.items.length} материалов
          ${feed.fetched_at ? `· обновлено ${timeAgo(feed.fetched_at)}` : ""}</div>
      </div>
      <button class="retry" id="news-refresh">↻ обновить</button>
    </div>
    ${warn}
    <div class="nfilters">${chips}</div>
    <div class="newsgrid">${cards}</div>`;

  document.getElementById("news-refresh").onclick = () => loadNews(true);
  body.querySelectorAll(".chip[data-src]").forEach((c) => {
    c.onclick = () => {
      const id = c.dataset.src;
      enabled.has(id) ? enabled.delete(id) : enabled.add(id);
      render();
    };
  });
}
