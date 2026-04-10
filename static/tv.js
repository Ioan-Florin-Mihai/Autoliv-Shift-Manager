/**
 * tv.js — Autoliv Shift Manager Web TV
 *
 * Responsabilitati:
 *   • Citeste /api/tv-data la fiecare 5 s (fara reload complet de pagina)
 *   • Rotește departamentele la fiecare 10 s
 *   • Randeaza grila industriala de schimburi
 *   • Actualizeaza ceasul din interfata
 */

'use strict';

// ── Configurare ─────────────────────────────────────────────────────────────
const DATA_URL   = '/api/tv-data';
const REFRESH_MS = 5_000;    // interval de baza pentru reincarcarea datelor
const MAX_BACKOFF_MS = 30_000;
const DISCONNECT_WARN_MS = 10_000;
const FADE_MS    = 180;      // tranzitie de estompare

const SHIFT_LABELS  = { Sch1: 'Sch. 1', Sch2: 'Sch. 2', Sch3: 'Sch. 3' };
const WEEKEND_DAYS  = new Set(['Sambata', 'Duminica']);
const MODE_NAMES    = ['Magazie', 'Bucle'];

// ── Stare ────────────────────────────────────────────────────────────────────
let _data    = null;   // ultimul raspuns API valid
let _modeIdx = 0;      // indexul modului curent (Magazie / Bucle)
let _deptIdx = 0;      // indexul departamentului curent in modul activ
let _lastSuccessMs = 0;
let _lastFailureSinceMs = 0;
let _lastPublishTime = null;
let _refreshDelayMs = REFRESH_MS;
let _refreshBaseMs = REFRESH_MS;
let _disconnectWarnMs = DISCONNECT_WARN_MS;
let _refreshTimer = null;
let _syncTimer = null;

// ── Utilitare ────────────────────────────────────────────────────────────────

/** Creeaza un element cu clasa si text optionale. */
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls)              e.className   = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** Numele modului curent, cu rotire prin modurile disponibile. */
function currentMode() {
  if (!_data) return MODE_NAMES[0];
  const modes = Object.keys(_data.departments || {});
  if (!modes.length) return MODE_NAMES[0];
  return modes[_modeIdx % modes.length];
}

/** Lista departamentelor pentru modul curent. */
function currentDepts() {
  if (!_data) return [];
  return (_data.departments[currentMode()] || []);
}

function formatPublishTime(value) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  const pad = n => String(n).padStart(2, '0');
  return `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
}

function updateStaleWarning(nowMs = Date.now()) {
  const statusEl = document.getElementById('footer-status');
  const lastEl = document.getElementById('footer-last-update');
  if (lastEl) {
    lastEl.textContent = `Ultima actualizare: ${formatPublishTime(_lastPublishTime)}`;
  }
  if (!statusEl) return;
  if (_lastSuccessMs && (nowMs - _lastSuccessMs) <= _disconnectWarnMs) {
    statusEl.textContent = '✔ Conectat';
    statusEl.classList.remove('warn');
    return;
  }
  if (_lastFailureSinceMs && (nowMs - _lastFailureSinceMs) >= _disconnectWarnMs) {
    statusEl.textContent = '⚠ Deconectat';
    statusEl.classList.add('warn');
    return;
  }
  statusEl.textContent = '… Conectare';
  statusEl.classList.add('warn');
}

function computeSyncedDeptIndex(nowMs, deptCount) {
  if (!_data || deptCount <= 0) return 0;
  const serverTimeMs = Number(_data.server_time || nowMs);
  const rotationStepMs = Number(_data.rotation_step_ms || 10_000);
  const offsetMs = Math.max(0, nowMs - _lastSuccessMs);
  const syncedNow = serverTimeMs + offsetMs;
  return Math.floor(syncedNow / rotationStepMs) % deptCount;
}


// ── Ceas ─────────────────────────────────────────────────────────────────────

function tickClock() {
  const now  = new Date();
  const pad  = n => String(n).padStart(2, '0');
  const time = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  const d    = `${pad(now.getDate())}/${pad(now.getMonth() + 1)}/${now.getFullYear()}`;
  document.getElementById('topbar-clock').textContent = `${time}   ${d}`;
  // Programeaza urmatorul tick aliniat la secunda intreaga
  setTimeout(tickClock, 1000 - (Date.now() % 1000));
}


// ── Citire date ──────────────────────────────────────────────────────────────

async function fetchData() {
  try {
    const res = await fetch(DATA_URL, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    if (json && !json.error && json.data) {
      _data = json.data;
      _lastSuccessMs = Date.now();
      _lastFailureSinceMs = 0;
      _lastPublishTime = json.last_publish_time || _lastPublishTime;
      _data.server_time = Number(json.server_time || _lastSuccessMs);
      _refreshBaseMs = Number(_data.refresh_interval_ms || REFRESH_MS);
      _disconnectWarnMs = DISCONNECT_WARN_MS;
      _refreshDelayMs = _refreshBaseMs;
      updateStaleWarning(_lastSuccessMs);
      return true;
    }
  } catch (_e) {
    // Pastreaza afisarea ultimelor date valide; serverul poate fi temporar indisponibil.
  }
  if (!_lastFailureSinceMs) {
    _lastFailureSinceMs = Date.now();
  }
  _refreshDelayMs = Math.min(MAX_BACKOFF_MS, Math.round(_refreshDelayMs * 1.8));
  updateStaleWarning(Date.now());
  return false;
}


// ── Constructor grila ────────────────────────────────────────────────────────

/**
 * Construieste si returneaza un element .grid-table pentru departamentul dat.
 * Constructie DOM pura — fara efecte secundare in afara elementului returnat.
 */
function buildGrid(deptName) {
  const displayDays  = _data.display_days  || [];
  const dayDates     = _data.day_dates     || {};
  const dayDatesIso  = _data.day_dates_iso || {};
  const todayIso     = _data.today_iso     || '';
  const mode         = currentMode();
  const deptSchedule = ((_data.schedule[mode] || {})[deptName] || {});

  const table = el('div', 'grid-table');

  // ── Rand antet coloane ─────────────────────────────────────────────────────
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

  // ── Randuri schimburi ──────────────────────────────────────────────────────
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


// ── Randare ──────────────────────────────────────────────────────────────────

function render() {
  if (!_data) return;

  const depts     = currentDepts();
  const deptCount = depts.length;
  if (deptCount === 0) return;

  _deptIdx = computeSyncedDeptIndex(Date.now(), deptCount);

  const deptName = depts[_deptIdx];
  const mode     = currentMode();

  // ── Bara superioara ────────────────────────────────────────────────────────
  document.getElementById('topbar-dept').textContent = deptName || '—';

  const weekText = [
    _data.week_label  || '',
    _data.week_range ? `(${_data.week_range})` : '',
  ].filter(Boolean).join('  ');
  document.getElementById('topbar-week').textContent = weekText;

  document.getElementById('footer-mode').textContent = mode.toUpperCase();

  // ── Indicatori progres departamente ───────────────────────────────────────
  const dotsEl = document.getElementById('dept-dots');
  dotsEl.innerHTML = '';
  depts.forEach((_, i) => {
    const dot = el('span', 'pdot' + (i === _deptIdx ? ' active' : ''));
    dotsEl.appendChild(dot);
  });

  // ── Grila (schimb cu estompare) ────────────────────────────────────────────
  const wrap = document.getElementById('grid-wrap');
  wrap.classList.add('fading');

  setTimeout(() => {
    wrap.innerHTML = '';
    wrap.appendChild(buildGrid(deptName));
    wrap.classList.remove('fading');
  }, FADE_MS);
}


// ── Bucle de rulare ──────────────────────────────────────────────────────────

async function refreshLoop() {
  await fetchData();
  render();
  if (_refreshTimer) clearTimeout(_refreshTimer);
  _refreshTimer = setTimeout(refreshLoop, _refreshDelayMs);
}

function syncLoop() {
  updateStaleWarning(Date.now());
  render();
  if (_syncTimer) clearTimeout(_syncTimer);
  _syncTimer = setTimeout(syncLoop, 1000);
}


// ── Initializare ─────────────────────────────────────────────────────────────

async function init() {
  tickClock();

  // Incarcare initiala
  await fetchData();
  render();

  // Refresh periodic cu backoff la retry + re-randare la nivel de secunda pentru aliniere perfecta.
  refreshLoop();
  syncLoop();
}

document.addEventListener('DOMContentLoaded', init);
