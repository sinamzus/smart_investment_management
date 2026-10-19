/* همتا — موتور نمودار مشترک (ChartKit): همهٔ نمودارهای سری زمانی از اینجا رسم می‌شوند.
   قابلیت‌ها: زوم با چرخ موس (حول نشانگر)، کشیدن برای انتخاب بازه، Shift+کشیدن/Shift+چرخ برای جابه‌جایی، دابل‌کلیک = بازنشانی،
   دکمه‌های + − ◀ ▶ ⟲ روی نمودار، کلیدهای ← → (ردگیری نقطه‌به‌نقطه؛ Shift = ۱۰ نقطه) و + − Esc با فوکوس روی نمودار.
   هوور: خط‌چین عمودی و افقی، نقطهٔ روی هر سری، برچسب تاریخ (میلادی · شمسی) روی محور افقی، برچسب مقدار نشانگر روی محور راست،
   برچسب مقدار هر سری روی لبهٔ چپ، و جعبهٔ شناور با همهٔ مقدارها.
   واسط:  ChartKit.paneChart(svg, dates, panes, st)   ·   ChartKit.attach(svg, st, redraw, opts)   ·   ChartKit.bars(el, labels, values, f, mark)
   st = { i, y, v0, v1 } (وضعیت هر نمودار؛ i = اندیس هوور در دادهٔ کامل). pane = { frac, log?, zero?, fmt?, series:[{v, color, w?, dash?, name?, fmt?}] }.
   opts.onZoom(lo, hi) اگر باشد زوم را به‌جای تغییر v0/v1 به فراخوان می‌سپارد (نمای صندوق‌ها بازه را از نو محاسبه می‌کند)؛ opts.onReset. */
(function () {
  const JM = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
  const fa = new Intl.DateTimeFormat('fa-IR-u-ca-persian-nu-latn', { year: 'numeric', month: 'numeric', day: 'numeric' });
  const jc = new Map();
  const jp = d => { let v = jc.get(d); if (!v) { const p = fa.formatToParts(new Date(d + 'T00:00:00Z')); const g = t => +p.find(x => x.type === t).value; v = [g('year'), g('month'), g('day')]; jc.set(d, v); } return v; };
  const jstr = d => { const [y, m, dd] = jp(d); return y + '/' + String(m).padStart(2, '0') + '/' + String(dd).padStart(2, '0'); };
  const nf = (x, d = 2) => Number(x).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  const MINSPAN = 8;

  function xticks(dates, v0, v1, x, minX, maxX) {
    const days = (Date.parse(dates[v1]) - Date.parse(dates[v0])) / 864e5, out = [];
    let key = null, prev = null;
    const mode = days > 3 * 365 ? 'y' : days > 420 ? 'q' : days > 150 ? 'm' : days > 50 ? 'h' : 'd';   // سال / فصل / ماه / نیم‌ماه / روز
    const stepD = Math.max(1, Math.round((v1 - v0) / 8));
    for (let i = v0; i <= v1; i++) {
      const [y, m, d] = jp(dates[i]);
      let k, lab;
      if (mode === 'y') { k = y; lab = String(y); }
      else if (mode === 'q') { k = y * 4 + Math.floor((m - 1) / 3); lab = JM[(Math.floor((m - 1) / 3)) * 3] + (m <= 3 ? ' ' + y : ''); }
      else if (mode === 'm') { k = y * 12 + m; lab = JM[m - 1] + (m === 1 ? ' ' + y : ''); }
      else if (mode === 'h') { k = y * 24 + (m - 1) * 2 + (d > 15 ? 1 : 0); lab = (d > 15 ? 16 : 1) + ' ' + JM[m - 1]; }
      else { if ((i - v0) % stepD !== 0) continue; k = i; lab = d + ' ' + JM[m - 1]; }
      if (k !== key) { key = k; const xx = x(i); if (xx > minX && xx < maxX && (prev == null || xx - prev >= 52)) { out.push([xx, lab]); prev = xx; } }
    }
    return out;
  }

  function path(vals, v0, v1, x, y, plotW) {
    const n = v1 - v0 + 1, dense = n > plotW * 1.6;
    let d = '', pen = false;
    if (!dense) {
      for (let i = v0; i <= v1; i++) { const v = vals[i]; if (v == null || !isFinite(v)) { pen = false; continue; } d += (pen ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1); pen = true; }
      return d;
    }
    // کاهش نقطه: برای هر پیکسل اولین، کمینه، بیشینه و آخرین مقدار (قلهٔ واقعی حفظ می‌شود)
    let bx = null, first, last, mn, mx, imn, imx;
    const flush = () => {
      if (bx == null) return;
      const pts = [[first[0], first[1]], [imn, mn], [imx, mx], [last[0], last[1]]].sort((a, b) => a[0] - b[0]);
      pts.forEach((p, k) => { if (k && p[0] === pts[k - 1][0] && p[1] === pts[k - 1][1]) return; d += (pen ? 'L' : 'M') + x(p[0]).toFixed(1) + ' ' + y(p[1]).toFixed(1); pen = true; });
    };
    for (let i = v0; i <= v1; i++) {
      const v = vals[i];
      if (v == null || !isFinite(v)) { flush(); bx = null; pen = false; continue; }
      const px = Math.round(x(i));
      if (px !== bx) { flush(); bx = px; first = [i, v]; mn = mx = v; imn = imx = i; }
      if (v < mn) { mn = v; imn = i; } if (v > mx) { mx = v; imx = i; }
      last = [i, v];
    }
    flush();
    return d;
  }

  function tagRect(cx, cy, text, anchor, cls, stroke) {
    const w = text.length * 5.9 + 10, x0 = anchor === 'middle' ? cx - w / 2 : anchor === 'start' ? cx : cx - w;
    return `<g class="ctag ${cls || ''}"><rect x="${x0.toFixed(1)}" y="${(cy - 8).toFixed(1)}" width="${w.toFixed(1)}" height="16" rx="2" ${stroke ? `stroke="${stroke}"` : ''}/><text x="${(x0 + w / 2).toFixed(1)}" y="${(cy + 3.5).toFixed(1)}" text-anchor="middle">${text}</text></g>`;
  }

  function paneChart(svg, dates, panes, st) {
    st = st || {};
    const N = dates.length, W = svg.clientWidth || 800, H = svg.clientHeight || 300, m = { l: 8, r: 58, t: 30, b: 22 }, gap = 18;
    const key = N + '|' + dates[0] + '|' + dates[N - 1];
    if (st._key !== key) { st._key = key; st.v0 = 0; st.v1 = N - 1; st.i = null; st.sel = null; }
    if (st.v0 == null || st.v1 == null) { st.v0 = 0; st.v1 = N - 1; }
    const v0 = Math.max(0, Math.min(N - 2, st.v0)), v1 = Math.max(v0 + 1, Math.min(N - 1, st.v1)), span = v1 - v0;
    const plotW = W - m.l - m.r, avail = H - m.t - m.b - gap * (panes.length - 1);
    const x = i => m.l + plotW * (i - v0) / span;
    let out = '', top = m.t;
    const geo = [], uid = (svg.id || 'ck') + '-cp';
    panes.forEach(p => {
      const h = Math.max(avail * p.frac, 12);   // نمای کوچک (یا پنهان) ارتفاع منفی نسازد
      const vals = []; p.series.forEach(s => { for (let i = v0; i <= v1; i++) { const v = s.v[i]; if (v != null && isFinite(v) && (!p.log || v > 0)) vals.push(v); } });
      let lo = vals.length ? Math.min(...vals) : 0, hi = vals.length ? Math.max(...vals) : 1;
      if (p.zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
      if (hi === lo) { hi = lo + (Math.abs(lo) || 1) * .01; }
      const T = p.log ? Math.log : (v => v), a = T(lo), b = T(hi), pad = (b - a) * .06 || 1, y0 = top;
      const y = v => y0 + h * (1 - (T(v) - (a - pad)) / ((b - a) + 2 * pad));
      const inv = py => { const t = 1 - (py - y0) / h, tv = (a - pad) + t * ((b - a) + 2 * pad); return p.log ? Math.exp(tv) : tv; };
      let tv = [];
      if (p.log) { for (let e = Math.floor(Math.log10(lo)) - 1; e <= Math.ceil(Math.log10(hi)) + 1; e++) [1, 2, 5].forEach(mu => { const v = mu * 10 ** e; if (v >= lo * 0.97 && v <= hi * 1.03) tv.push(v); }); if (tv.length > 7) tv = tv.filter(v => Math.abs(Math.log10(v) - Math.round(Math.log10(v))) < 1e-9); if (tv.length < 2) tv = [lo, hi]; }
      else { const raw = (hi - lo) / 4 || 1, p10 = 10 ** Math.floor(Math.log10(raw)), step = [1, 2, 2.5, 5, 10].map(q => q * p10).find(q => q >= raw); for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) tv.push(Math.abs(v) < 1e-9 ? 0 : v); }
      tv.forEach(v => { const yy = y(v); out += `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${yy}" y2="${yy}"/><text x="${W - m.r + 6}" y="${yy + 3}">${p.fmt ? p.fmt(v) : nf(v, 1)}</text>`; });
      if (p.zero) { const z = y(0); out += `<line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${z}" y2="${z}"/>`; }
      out += `<clipPath id="${uid}${geo.length}"><rect x="${m.l}" y="${y0}" width="${plotW}" height="${h}"/></clipPath><g clip-path="url(#${uid}${geo.length})">`;
      p.series.forEach(s => { out += `<path d="${path(s.v, v0, v1, x, y, plotW)}" fill="none" stroke="${s.color}" stroke-width="${s.w || 1.4}" ${s.dash ? 'stroke-dasharray="3 2"' : ''}/>`; });
      out += '</g>';
      geo.push({ top: y0, h, y, inv, p });
      top += h + gap;
    });
    // محور افقی
    xticks(dates, v0, v1, x, m.l + 14, W - m.r - 14).forEach(([xx, lab]) => { out += `<line class="axis" x1="${xx}" x2="${xx}" y1="${H - m.b}" y2="${H - m.b + 4}"/><text x="${xx}" y="${H - 6}" text-anchor="middle">${lab}</text>`; });
    // انتخاب بازه (کشیدن)
    if (st.sel) { const xa = x(Math.max(v0, Math.min(st.sel.i0, st.sel.i1))), xb = x(Math.min(v1, Math.max(st.sel.i0, st.sel.i1))); out += `<rect class="csel" x="${xa}" y="${m.t}" width="${Math.max(1, xb - xa)}" height="${H - m.t - m.b}"/>`; }
    // هوور
    let tipHtml = null;
    if (st.i != null && st.i >= v0 && st.i <= v1 && !st.sel) {
      const i = st.i, xi = x(i);
      out += `<line class="axis cross" x1="${xi}" x2="${xi}" y1="${m.t}" y2="${H - m.b}"/>`;
      const rows = [];
      geo.forEach((gp, gi) => {
        const left = [];
        gp.p.series.forEach(s => {
          const v = s.v[i]; if (v == null || !isFinite(v) || (gp.p.log && v <= 0)) return;
          const yy = gp.y(v), f = s.fmt || gp.p.fmt || (q => nf(q, 2));
          out += `<circle class="cpt" cx="${xi}" cy="${yy}" r="3.2" stroke="${s.color}"/>`;
          left.push([yy, f(v), s.color]);
          rows.push([s.name || '', f(v), s.color]);
        });
        left.sort((a, b) => a[0] - b[0]);
        for (let k = 1; k < left.length; k++) if (left[k][0] - left[k - 1][0] < 15) left[k][0] = left[k - 1][0] + 15;      // جلوگیری از هم‌پوشانی برچسب‌ها
        left.forEach(([yy, t, c]) => { out += tagRect(m.l + 2, yy, t, 'start', 'sv', c); });
        if (st.y != null && st.y >= gp.top && st.y <= gp.top + gp.h) {
          const val = gp.inv(st.y), f = gp.p.fmt || (q => nf(q, 2));
          out += `<line class="axis cross" x1="${m.l}" x2="${W - m.r}" y1="${st.y}" y2="${st.y}"/>` + tagRect(W - m.r + 1, st.y, f(val), 'start', 'yv');
        }
      });
      const dI = dates[i];
      out += tagRect(xi < m.l + 70 ? m.l + 70 : xi > W - m.r - 70 ? W - m.r - 70 : xi, H - m.b + 9, dI + ' · ' + jstr(dI), 'middle', 'dv');
      tipHtml = `<div class="d">${dI} · ${jstr(dI)}</div>` + rows.map(([n, v, c]) => `<div><i style="background:${c}"></i>${n ? n + ' ' : ''}<b>${v}</b></div>`).join('');
    }
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.innerHTML = out;
    svg._geom = { m, W, H, N, v0, v1, geo, x };
    svg._geom.N = N;
    const tip = svg._tip;
    if (tip) {
      if (tipHtml && st.cx != null) {
        tip.innerHTML = tipHtml; tip.hidden = false;
        const pw = svg.parentElement.clientWidth, tw = tip.offsetWidth, th = tip.offsetHeight;
        let lx = st.cx + 16, ly = st.cy + 12;
        if (lx + tw > pw - 4) lx = st.cx - tw - 16;
        if (ly + th > svg.parentElement.clientHeight - 4) ly = st.cy - th - 12;
        tip.style.left = Math.max(2, lx) + 'px'; tip.style.top = Math.max(2, ly) + 'px';
      } else tip.hidden = true;
    }
    if (svg._label) svg._label(dates[v0], dates[v1], v1 - v0 + 1, N);
  }

  function attach(svg, st, redraw, opts) {
    opts = opts || {};
    if (svg._ck) { svg._ck.redraw = redraw; svg._ck.opts = opts; return; }
    const ck = svg._ck = { redraw, opts };
    const par = svg.parentElement;
    if (getComputedStyle(par).position === 'static') par.style.position = 'relative';
    svg.tabIndex = 0; svg.style.touchAction = 'none'; svg.classList.add('zoomable');
    const tip = document.createElement('div'); tip.className = 'ctip'; tip.hidden = true; par.appendChild(tip); svg._tip = tip;
    const bar = document.createElement('div'); bar.className = 'cbar';
    bar.innerHTML = '<span class="clab"></span>' +
      [['in', '＋', 'زوم به داخل (چرخ موس هم همین کار را می‌کند)'], ['out', '−', 'زوم به بیرون'], ['l', '◀', 'جابه‌جایی به گذشته (Shift+چرخ موس)'], ['r', '▶', 'جابه‌جایی به جلو'], ['rs', '⟲', 'بازنشانی زوم (دابل‌کلیک روی نمودار)']]
        .map(([k, t, tp]) => `<button class="tool" data-k="${k}" data-tip="${tp}" type="button">${t}</button>`).join('');
    par.appendChild(bar);
    svg._label = (a, b, n, N) => { bar.firstChild.textContent = n < N ? jstr(a) + ' ← ' + jstr(b) + ' · ' + n + ' نقطه' : ''; };
    const re = () => ck.redraw && ck.redraw();
    const G = () => svg._geom;
    const rect = () => svg.getBoundingClientRect();
    const px = e => { const g = G(), r = rect(); return (e.clientX - r.left) * (g.W / r.width); };
    const py = e => { const g = G(), r = rect(); return (e.clientY - r.top) * (g.H / r.height); };
    const idxOf = p => { const g = G(); return Math.max(g.v0, Math.min(g.v1, Math.round(g.v0 + (p - g.m.l) / (g.W - g.m.l - g.m.r) * (g.v1 - g.v0)))); };
    const setView = (lo, hi) => {
      const g = G(); lo = Math.round(lo); hi = Math.round(hi);
      if (ck.opts.onZoom) return ck.opts.onZoom(lo, hi);
      const N = g.N; let span = Math.max(MINSPAN, hi - lo);
      if (span >= N - 1) { st.v0 = 0; st.v1 = N - 1; return re(); }
      lo = Math.max(0, Math.min(N - 1 - span, lo)); st.v0 = lo; st.v1 = lo + span; re();
    };
    const zoom = (f, anchor) => { const g = G(), a = anchor == null ? (g.v0 + g.v1) / 2 : anchor, lo = a - (a - g.v0) * f, hi = a + (g.v1 - a) * f; if (f < 1 && hi - lo < MINSPAN) return; setView(lo, hi); };
    const pan = f => { const g = G(), d = (g.v1 - g.v0) * f; setView(g.v0 + d, g.v1 + d); };
    const reset = () => { if (ck.opts.onReset) return ck.opts.onReset(); const g = G(); st.v0 = 0; st.v1 = g.N - 1; re(); };
    bar.addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      ({ in: () => zoom(.6), out: () => zoom(1 / .6), l: () => pan(-.35), r: () => pan(.35), rs: reset })[b.dataset.k]();
    });
    let drag = null;
    svg.addEventListener('pointermove', e => {
      const g = G(); if (!g) return;
      const p = px(e), q = py(e), r = rect();
      st.cx = e.clientX - r.left; st.cy = e.clientY - r.top; st.y = q;
      if (drag) {
        if (drag.pan) { const d = (p - drag.p0) / (g.W - g.m.l - g.m.r) * (drag.v1 - drag.v0); setView(drag.v0 - d, drag.v1 - d); }
        else { drag.moved = Math.abs(p - drag.p0) > 6; st.sel = { i0: drag.i0, i1: idxOf(p) }; st.i = null; re(); }
        return;
      }
      st.i = idxOf(p); re();
    });
    svg.addEventListener('pointerleave', () => { if (drag) return; st.i = null; st.y = null; re(); });
    svg.addEventListener('pointerdown', e => {
      if (e.button !== 0 || !G()) return; svg.focus({ preventScroll: true });
      const g = G(), p = px(e);
      drag = { p0: p, i0: idxOf(p), pan: e.shiftKey, v0: g.v0, v1: g.v1, moved: false };
      try { svg.setPointerCapture(e.pointerId); } catch (x) { /* بی‌اهمیت */ }
      e.preventDefault();
    });
    let lastUp = null;
    const up = e => {
      if (!drag) return; const d = drag; drag = null; try { svg.releasePointerCapture(e.pointerId); } catch (x) { /* بی‌اهمیت */ }
      // دابل‌کلیک دستی: preventDefault روی pointerdown رویداد dblclick مرورگر را حذف می‌کند
      const now = e.timeStamp, cx = e.clientX, cy = e.clientY;
      if (!d.moved && lastUp && now - lastUp.t < 380 && Math.abs(cx - lastUp.x) < 8 && Math.abs(cy - lastUp.y) < 8) { lastUp = null; st.sel = null; return reset(); }
      lastUp = d.moved ? null : { t: now, x: cx, y: cy };
      if (!d.pan && d.moved && st.sel) { const lo = Math.min(st.sel.i0, st.sel.i1), hi = Math.max(st.sel.i0, st.sel.i1); st.sel = null; if (hi - lo >= 2) return setView(lo, hi); }
      st.sel = null; re();
    };
    svg.addEventListener('pointerup', up); svg.addEventListener('pointercancel', up);
    svg.addEventListener('wheel', e => {
      const g = G(); if (!g) return; e.preventDefault();
      if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return pan((e.deltaX || e.deltaY) > 0 ? .15 : -.15);
      zoom(e.deltaY < 0 ? .78 : 1 / .78, idxOf(px(e)));
    }, { passive: false });
    svg.addEventListener('keydown', e => {
      const g = G(); if (!g) return; const k = e.key;
      if (k === 'ArrowLeft' || k === 'ArrowRight') { const s = (k === 'ArrowLeft' ? -1 : 1) * (e.shiftKey ? 10 : 1); st.i = Math.max(g.v0, Math.min(g.v1, (st.i == null ? Math.round((g.v0 + g.v1) / 2) : st.i) + s)); st.y = null; st.cx = g.x(st.i) * (svg.clientWidth / g.W); st.cy = 40; re(); e.preventDefault(); }
      else if (k === '+' || k === '=') { zoom(.7, st.i); e.preventDefault(); }
      else if (k === '-') { zoom(1 / .7, st.i); e.preventDefault(); }
      else if (k === 'Escape') { reset(); }
    });
  }

  function bars(el, labels, values, f, mark) {
    const mx = Math.max(...values.map(v => Math.abs(v || 0)), 1e-9);
    el.innerHTML = values.map((v, i) => `<div class="b" title="${labels[i]}: ${f(v)}" style="height:${Math.max(1, Math.abs(v || 0) / mx * 78)}%;${mark && mark(i, v) ? 'background:var(--lg-c)' : ''}"><em>${f(v)}</em><span>${labels[i]}</span></div>`).join('');
  }

  window.ChartKit = { paneChart, attach, bars, jstr, jp };
})();
