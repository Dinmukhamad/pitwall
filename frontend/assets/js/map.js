// MapView — one independent track map: own filter, own zoom/pan (FR-10..15).
import { S, teamColor, acr } from "./state.js";

let _id = 0;

export class MapView {
  constructor(container, { onSelect, onRemove, removable }) {
    this.id = ++_id;
    this.onSelect = onSelect;
    this.onRemove = onRemove;
    this.filter = new Set(Object.keys(S.driversByNum).map(Number)); // all on
    this.userScale = 1;
    this.panX = 0;
    this.panY = 0;
    this._drag = null;

    this.el = document.createElement("div");
    this.el.className = "mapcard";
    this.el.innerHTML = `
      <div class="mapcard-head">
        <span class="title">Карта ${this.id}</span>
        <button class="mini-btn" data-act="filter">Пилоты</button>
        <button class="mini-btn" data-act="all">Все</button>
        <button class="mini-btn" data-act="none">Никого</button>
        <button class="mini-btn" data-act="reset">Сброс</button>
        <span class="zoom-ind">×${this.userScale.toFixed(1)}</span>
        <button class="mini-btn" data-act="remove" title="Удалить карту">✕</button>
      </div>
      <canvas class="map-canvas" height="260"></canvas>
      <div class="filter-pop hidden"></div>`;
    container.appendChild(this.el);

    this.canvas = this.el.querySelector("canvas");
    this.ctx = this.canvas.getContext("2d");
    this.zoomInd = this.el.querySelector(".zoom-ind");
    this.pop = this.el.querySelector(".filter-pop");
    this.removeBtn = this.el.querySelector('[data-act="remove"]');
    if (!removable) this.removeBtn.style.display = "none";

    this._wire();
    this._buildFilterChips();
    this._resize();
    this._ro = new ResizeObserver(() => this._resize());
    this._ro.observe(this.canvas);
  }

  _wire() {
    this.el.querySelector('[data-act="filter"]').onclick = () =>
      this.pop.classList.toggle("hidden");
    this.el.querySelector('[data-act="all"]').onclick = () => this._setAll(true);
    this.el.querySelector('[data-act="none"]').onclick = () => this._setAll(false);
    this.el.querySelector('[data-act="reset"]').onclick = () => {
      this.userScale = 1; this.panX = 0; this.panY = 0; this._draw();
    };
    this.removeBtn.onclick = () => this.onRemove?.(this);

    // wheel zoom to cursor
    this.canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const rect = this.canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
      const ns = Math.min(8, Math.max(1, this.userScale * factor));
      const k = ns / this.userScale;
      // keep point under cursor fixed
      const cx = this.canvas.width / 2, cy = this.canvas.height / 2;
      this.panX = mx - k * (mx - (cx + this.panX)) - cx;
      this.panY = my - k * (my - (cy + this.panY)) - cy;
      this.userScale = ns;
      this._draw();
    }, { passive: false });

    // drag pan
    const down = (x, y) => { this._drag = { x, y, px: this.panX, py: this.panY }; };
    const move = (x, y) => {
      if (!this._drag) return;
      this.panX = this._drag.px + (x - this._drag.x);
      this.panY = this._drag.py + (y - this._drag.y);
      this._draw();
    };
    const up = () => { this._drag = null; };
    this.canvas.addEventListener("pointerdown", (e) => { this.canvas.setPointerCapture(e.pointerId); down(e.clientX, e.clientY); });
    this.canvas.addEventListener("pointermove", (e) => move(e.clientX, e.clientY));
    this.canvas.addEventListener("pointerup", up);
    this.canvas.addEventListener("pointercancel", up);

    // click a car to select
    this.canvas.addEventListener("click", (e) => {
      if (this._moved) return;
      const rect = this.canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const hit = this._hitTest(mx, my);
      if (hit != null) this.onSelect?.(hit);
    });
  }

  _buildFilterChips() {
    this.pop.innerHTML = "";
    for (const num of Object.keys(S.driversByNum).map(Number)) {
      const chip = document.createElement("button");
      chip.className = "dchip on";
      chip.textContent = acr(num);
      chip.style.borderColor = teamColor(num);
      chip.style.color = teamColor(num);
      chip.onclick = () => {
        if (this.filter.has(num)) this.filter.delete(num); else this.filter.add(num);
        chip.classList.toggle("on", this.filter.has(num));
        this._updateCount(); this._draw();
      };
      this.pop.appendChild(chip);
    }
    this._updateCount();
  }
  _setAll(on) {
    const nums = Object.keys(S.driversByNum).map(Number);
    this.filter = new Set(on ? nums : []);
    this.pop.querySelectorAll(".dchip").forEach((c, i) =>
      c.classList.toggle("on", this.filter.has(nums[i])));
    this._updateCount(); this._draw();
  }
  _updateCount() {
    const t = this.el.querySelector(".title");
    t.textContent = `Карта ${this.id} · ${this.filter.size} пил.`;
  }

  _resize() {
    const w = this.canvas.clientWidth || 400;
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = w * dpr;
    this.canvas.height = 260 * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this._cssW = w; this._cssH = 260;
    this._draw();
  }

  // world (track coord) -> screen px
  _project(x, y) {
    const t = S.track;
    if (!t) return [0, 0];
    const b = t.bounds;
    const spanX = (b.maxx - b.minx) || 1, spanY = (b.maxy - b.miny) || 1;
    const cx = (b.minx + b.maxx) / 2, cy = (b.miny + b.maxy) / 2;
    const s0 = Math.min(this._cssW / spanX, this._cssH / spanY) * 0.86;
    const s = s0 * this.userScale;
    const sx = (x - cx) * s + this._cssW / 2 + this.panX;
    const sy = (cy - y) * s + this._cssH / 2 + this.panY; // flip Y
    return [sx, sy];
  }

  _hitTest(mx, my) {
    let best = null, bd = 14 * 14;
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
    this.zoomInd.textContent = "×" + this.userScale.toFixed(1);
    ctx.clearRect(0, 0, this._cssW, this._cssH);
    if (!t || !t.points?.length) {
      ctx.fillStyle = "#556"; ctx.font = "12px sans-serif";
      ctx.fillText("нет геометрии трассы", 12, 20);
      return;
    }
    // track ribbon
    ctx.lineJoin = "round"; ctx.lineCap = "round";
    ctx.strokeStyle = "#33405a";
    ctx.lineWidth = 9; ctx.beginPath();
    t.points.forEach((p, i) => {
      const [sx, sy] = this._project(p.x, p.y);
      i ? ctx.lineTo(sx, sy) : ctx.moveTo(sx, sy);
    });
    ctx.closePath(); ctx.stroke();
    ctx.strokeStyle = "#0c1119"; ctx.lineWidth = 6; ctx.stroke();

    // start/finish
    if (t.start_finish) {
      const [sx, sy] = this._project(t.start_finish.x, t.start_finish.y);
      ctx.fillStyle = "#fff";
      ctx.fillRect(sx - 5, sy - 5, 10, 10);
      ctx.fillStyle = "#000";
      ctx.fillRect(sx - 5, sy - 5, 5, 5);
      ctx.fillRect(sx, sy, 5, 5);
    }

    // cars — рисуем сглаженные позиции (см. S.renderPos)
    const activeNum = S.activeDriver;
    const p1 = S.latestTiming.find((r) => r.position === 1)?.driver_number;
    for (const pos of S.latestPositions) {
      if (!this.filter.has(pos.driver_number)) continue;
      const rp = S.renderPos[pos.driver_number] || pos;
      const [sx, sy] = this._project(rp.x, rp.y);
      const col = teamColor(pos.driver_number);
      const active = pos.driver_number === activeNum;
      ctx.beginPath();
      ctx.arc(sx, sy, active ? 7 : 5, 0, Math.PI * 2);
      ctx.fillStyle = col; ctx.fill();
      if (active) { ctx.lineWidth = 2; ctx.strokeStyle = "#fff"; ctx.stroke(); }
      if (active || pos.driver_number === p1) {
        ctx.fillStyle = "#fff"; ctx.font = "bold 11px sans-serif";
        ctx.fillText(acr(pos.driver_number), sx + 9, sy + 4);
      }
    }
  }

  redraw() { this._draw(); }
  destroy() { this._ro.disconnect(); this.el.remove(); }
}
