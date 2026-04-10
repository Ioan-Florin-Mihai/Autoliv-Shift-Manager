/**
 * tv.js — Autoliv Shift Manager Web TV
 *
 * Responsibilities:
 *   • Fetch /api/tv-data every 5 s (no full page reload)
 *   • Rotate departments every 10 s
 *   • Render industrial shift grid
 *   • Drive clock display
 */

'use strict';

// ── Configuration ────────────────────────────────────────────────────────────
const DATA_URL   = '/api/tv-data';
const REFRESH_MS = 5_000;    // data reload interval
const ROTATE_MS  = 10_000;   // department rotation interval
const FADE_MS    = 180;      // fade transition

const SHIFT_LABELS  = { Sch1: 'Sch. 1', Sch2: 'Sch. 2', Sch3: 'Sch. 3' };
const WEEKEND_DAYS  = new Set(['Sambata', 'Duminica']);
const MODE_NAMES    = ['Magazie', 'Bucle'];

// ── State ────────────────────────────────────────────────────────────────────
let _data    = null;   // last successful API response
let _modeIdx = 0;      // current mode index (Magazie / Bucle)
let _deptIdx = 0;      // current department index within mode

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Create an element with optional class and text content. */
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls)              e.className   = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** Current mode name, cycling through available modes. */
function currentMode() {
  if (!_data) return MODE_NAMES[0];
  const modes = Object.keys(_data.departments || {});
  if (!modes.length) return MODE_NAMES[0];
  return modes[_modeIdx % modes.length];
}

/** Department list for the current mode. */
function currentDepts() {
  if (!_data) return [];
  return (_data.departments[currentMode()] || []);
}


// ── Clock ────────────────────────────────────────────────────────────────────

function tickClock() {
  const now  = new Date();
  const pad  = n => String(n).padStart(2, '0');
  const time = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  const d    = `${pad(now.getDate())}/${pad(now.getMonth() + 1)}/${now.getFullYear()}`;
  document.getElementById('topbar-clock').textContent = `${time}   ${d}`;
  // Schedule next tick aligned to the next full second
  setTimeout(tickClock, 1000 - (Date.now() % 1000));
}


// ── Data fetch ───────────────────────────────────────────────────────────────

async function fetchData() {
  try {
    const res = await fetch(DATA_URL, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    if (json && !json.error) {
      _data = json;
    }
  } catch (_e) {
    // Keep displaying last good data; server may be temporarily unreachable
  }
}


// ── Grid builder ─────────────────────────────────────────────────────────────

/**
 * Build and return a .grid-table element for the given department.
 * Pure DOM construction — no side effects outside the returned element.
 */
function buildGrid(deptName) {
  const displayDays  = _data.display_days  || [];
  const dayDates     = _data.day_dates     || {};
  const dayDatesIso  = _data.day_dates_iso || {};
  const todayIso     = _data.today_iso     || '';
  const mode         = currentMode();
  const deptSchedule = ((_data.schedule[mode] || {})[deptName] || {});

  const table = el('div', 'grid-table');

  // ── Column header row ──────────────────────────────────────────────────────
  const hdrRow = el('div', 'col-hdr-row');
  hdrRow.appendChild(el('div', 'col-hdr-spacer'));

  displayDays.forEach(day => {
    const isToday   = dayDatesIso[day] === todayIso && todayIso !== '';
    const isWeekend = WEEKEND_DAYS.has(day);

    let cls = 'col-hdr-cell';
    if (isToday)        cls += ' today';
    else if (isWeekend) cls += ' wknd';

    const cell = el('div', cls);
    cell.appendChild(el('span', 'day-name', day.toUpperCase()));
    cell.appendChild(el('span', 'day-date', dayDates[day] || ''));
    hdrRow.appendChild(cell);
  });
  table.appendChild(hdrRow);

  // ── Shift rows ─────────────────────────────────────────────────────────────
  ['Sch1', 'Sch2', 'Sch3'].forEach((shift, shiftIdx) => {
    const rowParity = shiftIdx % 2 === 0 ? 'even' : 'odd';
    const row       = el('div', `shift-row ${rowParity}`);

    row.appendChild(el('div', 'shift-lbl', SHIFT_LABELS[shift] || shift));

    displayDays.forEach(day => {
      const isToday   = dayDatesIso[day] === todayIso && todayIso !== '';
      const isWeekend = WEEKEND_DAYS.has(day);

      let cellCls = 'day-cell';
      if (isToday)        cellCls += ' today';
      else if (isWeekend) cellCls += ' wknd';

      const cell = el('div', cellCls);
      const emps = ((deptSchedule[day] || {})[shift] || []);

      if (emps.length > 0) {
        emps.forEach(emp => {
          const span = el('span', 'emp' + (emp.hours12 ? ' h12' : ''), emp.name);
          cell.appendChild(span);
        });
      } else {
        cell.appendChild(el('span', 'emp-empty', '—'));
      }

      row.appendChild(cell);
    });

    table.appendChild(row);
  });

  return table;
}


// ── Render ───────────────────────────────────────────────────────────────────

function render() {
  if (!_data) return;

  const depts     = currentDepts();
  const deptCount = depts.length;
  if (deptCount === 0) return;

  // Make sure index is in-bounds (dept list may change between fetches)
  if (_deptIdx >= deptCount) _deptIdx = 0;

  const deptName = depts[_deptIdx];
  const mode     = currentMode();

  // ── Top bar ────────────────────────────────────────────────────────────────
  document.getElementById('topbar-dept').textContent = deptName || '—';

  const weekText = [
    _data.week_label  || '',
    _data.week_range ? `(${_data.week_range})` : '',
  ].filter(Boolean).join('  ');
  document.getElementById('topbar-week').textContent = weekText;

  document.getElementById('footer-mode').textContent = mode.toUpperCase();

  // ── Dept progress dots ─────────────────────────────────────────────────────
  const dotsEl = document.getElementById('dept-dots');
  dotsEl.innerHTML = '';
  depts.forEach((_, i) => {
    const dot = el('span', 'pdot' + (i === _deptIdx ? ' active' : ''));
    dotsEl.appendChild(dot);
  });

  // ── Grid (fade swap) ───────────────────────────────────────────────────────
  const wrap = document.getElementById('grid-wrap');
  wrap.classList.add('fading');

  setTimeout(() => {
    wrap.innerHTML = '';
    wrap.appendChild(buildGrid(deptName));
    wrap.classList.remove('fading');
  }, FADE_MS);
}


// ── Rotation ─────────────────────────────────────────────────────────────────

function rotateDept() {
  const depts = currentDepts();
  if (depts.length === 0) return;
  _deptIdx = (_deptIdx + 1) % depts.length;
  render();
}


// ── Refresh loop ─────────────────────────────────────────────────────────────

async function refresh() {
  await fetchData();
  render();
}


// ── Init ─────────────────────────────────────────────────────────────────────

async function init() {
  tickClock();

  // Initial load
  await fetchData();
  render();

  // Periodic data refresh (no page reload — just fetch + re-render)
  setInterval(refresh, REFRESH_MS);

  // Department rotation
  setInterval(rotateDept, ROTATE_MS);
}

document.addEventListener('DOMContentLoaded', init);
