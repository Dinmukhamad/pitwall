// MapView — независимая карта трассы: свой фильтр пилотов, свой зум и панорама
// (FR-10..15). Разметка по макету прототипа.
import { S, teamColor, acr } from "./state.js";

let _id = 0;

export class MapView {
  constructor(container, { onSelect, onRemove, removable }) {
    this.id = ++_id;
    this.onSelect = onSelect;
    this.onRemove = onRemove;
    this.filter = new Set(Object.keys(S.driversByNum).map(Number));
    this.userScale = 1;
    this.panX = 0;
    this.panY = 0;
    this._drag = null;
    this._moved = false;

    this.el = document.createElement("div");
    this.el.className = "mapcard";
    this.el.innerHTML = `
      <div class="maphead">
        <span class="mtitle">Карта ${this.id}</span>
        <div class="mtools">
          <button class="mbtn" data-act="filter">пилоты · <b>0</b></button>
          <button class="mbtn" data-act="reset" title="Сбросить масштаб">⤢</button>
          <button class="mbtn" data-act="remove" title="Убрать карту">✕</button>
        </div>
      </div>
      <div class="filterpop hidden">
        <div class="frow">
          <button data-act="all">Все</button>
          <button data-act="none">Никого</button>
        </div>
        <div class="chips"></div>
      </div>
      <div class="cwrap">
        <canvas></canvas>
        <div class="drslegend hidden"><i></i>зона DRS</div>
        <div class="zoombadge">100%</div>
      </div>`;
    container.appendChild(this.el);

    this.canvas = this.el.querySelector("canvas");
    this.ctx = this.canvas.getContext("2d");
    this.cwrap = this.el.querySelector(".cwrap");
    this.zoomBadge = this.el.querySelector(".zoombadge");
    this.drsLegend = this.el.querySelector(".drslegend");
    this.pop = this.el.querySelector(".filterpop");
    this.chips = this.el.querySelector(".chips");
    this.countEl = this.el.querySelector('[data-act="filter"] b');
    this.removeBtn = this.el.querySelector('[data-act="remove"]');
    if (!removable) this.removeBtn.style.display = "none";

    this._wire();
    this.buildFilterChips();
    this._resize();
    this._ro = new ResizeObserver(() => this._resize());
    this._ro.observe(this.cwrap);
  }

  _wire() {
    this.el.querySelector('[data-act="filter"]').onclick = () => this.pop.classList.toggle("hidden");
    this.el.querySelector('[data-act="all"]').onclick = () => this._setAll(true);
    this.el.querySelector('[data-act="none"]').onclick = () => this._setAll(false);
    this.el.querySelector('[data-act="reset"]').onclick = () => {
      this.userScale = 1; this.panX = 0; this.panY = 0; this._draw();
    };
    this.removeBtn.onclick = () => this.onRemove?.(this);

    // Зум колесом — к точке под курсором (FR-12)
    this.canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const rect = this.canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const ns = Math.min(8, Math.max(1, this.userScale * (e.deltaY < 0 ? 1.1 : 1 / 1.1)));
      const k = ns / this.userScale;
      const cx = this._cssW / 2, cy = this._cssH / 2;
      this.panX = mx - k * (mx - (cx + this.panX)) - cx;
      this.panY = my - k * (my - (cy + this.panY)) - cy;
      this.userScale = ns;
      this._draw();
    }, { passive: false });

    // Панорама перетаскиванием
    this.canvas.addEventListener("pointerdown", (e) => {
      this.canvas.setPointerCapture(e.pointerId);
      this._drag = { x: e.clientX, y: e.clientY, px: this.panX, py: this.panY };
      this._moved = false;
      this.cwrap.classList.add("drag");
    });
    this.canvas.addEventListener("pointermove", (e) => {
      if (!this._drag) return;
      const dx = e.clientX - this._drag.x, dy = e.clientY - this._drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) this._moved = true;
      this.panX = this._drag.px + dx;
      this.panY = this._drag.py + dy;
      this._draw();
    });
    const up = () => { this._drag = null; this.cwrap.classList.remove("drag"); };
    this.canvas.addEventListener("pointerup", up);
    this.canvas.addEventListener("pointercancel", up);

    // Клик по машине выбирает пилота (FR-15); после перетаскивания — не считается
    this.canvas.addEventListener("click", (e) => {
      if (this._moved) return;
      const rect = this.canvas.getBoundingClientRect();
      const hit = this._hitTest(e.clientX - rect.left, e.clientY - rect.top);
      if (hit != null) this.onSelect?.(hit);
    });
  }

  buildFilterChips() {
    const nums = Object.keys(S.driversByNum).map(Number);
    this.filter = new Set(nums);
    this.chips.innerHTML = "";
    for (const num of nums) {
      const chip = document.createElement("button");
      chip.className = "chip on";
      chip.textContent = acr(num);
      chip.style.borderLeftColor = teamColor(num);
      chip.onclick = () => {
        this.filter.has(num) ? this.filter.delete(num) : this.filter.add(num);
        chip.classList.toggle("on", this.filter.has(num));
        this._updateCount(); this._draw();
      };
      this.chips.appendChild(chip);
    }
    this._updateCount();
  }

  _setAll(on) {
    const nums = Object.keys(S.driversByNum).map(Number);
    this.filter = new Set(on ? nums : []);
    this.chips.querySelectorAll(".chip").forEach((c, i) =>
      c.classList.toggle("on", this.filter.has(nums[i])));
    this._updateCount(); this._draw();
  }

  _updateCount() { this.countEl.textContent = String(this.filter.size); }

  _resize() {
    const r = this.cwrap.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this._cssW = r.width || 400;
    this._cssH = r.height || 220;
    this.canvas.width = this._cssW * dpr;
    this.canvas.height = this._cssH * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this._draw();
  }

  // координаты трассы -> экран
  _project(x, y) {
    const t = S.track;
    if (!t) return [0, 0];
    const b = t.bounds;
    const spanX = (b.maxx - b.minx) || 1, spanY = (b.maxy - b.miny) || 1;
    const cx = (b.minx + b.maxx) / 2, cy = (b.miny + b.maxy) / 2;
    const s = Math.min(this._cssW / spanX, this._cssH / spanY) * 0.86 * this.userScale;
    return [(x - cx) * s + this._cssW / 2 + this.panX,
            (cy - y) * s + this._cssH / 2 + this.panY];   // Y инвертирован
  }

  _hitTest(mx, my) {
    let best = null, bd = 16 * 16;
    for (const p of S.latestPositions) {
      if (!this.filter.has(p.driver_number)) continue;
      const rp = S.renderPos[p.driver_number] || p;
      const [sx, sy] = this._project(rp.x, rp.y);
      const d = (sx - mx) ** 2 + (sy - my) ** 2;
      if (d < bd) { bd = d; best = p.driver_number; }
    }
    return best;
  }

  _draw() {
    const ctx = this.ctx, t = S.track;
    this.zoomBadge.textContent = Math.round(this.userScale * 100) + "%";
    // Легенду показываем только если зоны DRS действительно есть и нарисованы —
    // иначе подпись обещает то, чего на карте нет.
    const zones = t?.drs_zones ?? [];
    this.drsLegend.classList.toggle("hidden", zones.length === 0);
    ctx.clearRect(0, 0, this._cssW, this._cssH);
    if (!t || !t.points?.length) {
      ctx.fillStyle = "#5C6673"; ctx.font = "12px Inter, sans-serif";
      ctx.fillText("нет геометрии трассы", 14, 24);
      return;
    }

    // Полотно трассы: широкая тёмная линия с более светлой окантовкой
    ctx.lineJoin = ctx.lineCap = "round";
    ctx.beginPath();
    t.points.forEach((p, i) => {
      const [sx, sy] = this._project(p.x, p.y);
      i ? ctx.lineTo(sx, sy) : ctx.moveTo(sx, sy);
    });
    ctx.closePath();
    ctx.strokeStyle = "#39414F"; ctx.lineWidth = 11; ctx.stroke();
    ctx.strokeStyle = "#1A2029"; ctx.lineWidth = 7.5; ctx.stroke();

    // Линия старт/финиш
    if (t.start_finish) {
      const [sx, sy] = this._project(t.start_finish.x, t.start_finish.y);
      ctx.save();
      ctx.fillStyle = "#EDF0F4";
      ctx.fillRect(sx - 6, sy - 2.5, 12, 5);
      ctx.fillStyle = "#0B0E13";
      ctx.fillRect(sx - 6, sy - 2.5, 4, 2.5);
      ctx.fillRect(sx + 2, sy, 4, 2.5);
      ctx.restore();
    }

    // Машины
    const leader = S.latestTiming.find((r) => r.position === 1)?.driver_number;
    for (const pos of S.latestPositions) {
      if (!this.filter.has(pos.driver_number)) continue;
      const rp = S.renderPos[pos.driver_number] || pos;
      const [sx, sy] = this._project(rp.x, rp.y);
      const active = pos.driver_number === S.activeDriver;
      ctx.beginPath();
      ctx.arc(sx, sy, active ? 7 : 5, 0, Math.PI * 2);
      ctx.fillStyle = teamColor(pos.driver_number);
      ctx.fill();
      if (active) { ctx.lineWidth = 2; ctx.strokeStyle = "#EDF0F4"; ctx.stroke(); }
      // Подписи только лидеру и выбранному — иначе на 20 машинах каша
      if (active || pos.driver_number === leader) {
        ctx.font = "700 11px Inter, sans-serif";
        ctx.fillStyle = "#EDF0F4";
        ctx.fillText(acr(pos.driver_number), sx + 10, sy + 4);
      }
    }
  }

  redraw() { this._draw(); }
  destroy() { this._ro.disconnect(); this.el.remove(); }
}
