import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { open, ask } from '@tauri-apps/plugin-dialog';
import { getCurrentWindow } from '@tauri-apps/api/window';

const state = {
  config: null,
  files: [],
  status: 'idle',
  processed: 0,
  total: 0,
  found: 0,
  notFound: 0,
  rateLimitErrors: 0,
  logs: [],
  elapsed: 0,
  startTime: null,
  isProcessing: false
};

const $ = (id) => document.getElementById(id);

function fmt(n) { return n.toLocaleString('es-MX'); }
function fmtTime(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
}

function renderMetrics() {
  const totalRfcs = state.files.reduce((s, f) => s + f.row_count, 0);
  $('mRfcs').textContent = fmt(totalRfcs);
  $('mRfcsSub').textContent = totalRfcs > 0 ? 'registros totales' : '—';
  $('mFound').textContent = fmt(state.found);
  $('mFoundSub').textContent = state.found > 0 ? `${Math.round(state.found / Math.max(state.processed,1) * 100)}% de procesados` : '—';
  $('mNotFound').textContent = fmt(state.notFound);
  $('mNotFoundSub').textContent = state.notFound > 0 ? `${Math.round(state.notFound / Math.max(state.processed,1) * 100)}% de procesados` : '—';
  $('m429').textContent = fmt(state.rateLimitErrors);
  $('m429Sub').textContent = state.rateLimitErrors > 0 ? 'rate limit excedido' : 'rate limit';
}

function renderFileList() {
  const el = $('fileList');
  el.innerHTML = '';
  if (state.files.length === 0) return;
  for (const f of state.files) {
    const div = document.createElement('div');
    div.className = 'file-item';
    div.innerHTML = `
      <div class="file-item-left">
        <svg class="file-item-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        <span class="file-item-name">${f.filename}</span>
      </div>
      <div style="display:flex;align-items:center;gap:12px">
        <span class="file-item-count">${fmt(f.row_count)} filas</span>
        <button class="file-item-del" data-filename="${f.filename}" title="Eliminar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
        </button>
      </div>`;
    el.appendChild(div);
  }
  el.querySelectorAll('.file-item-del').forEach(btn => {
    btn.addEventListener('click', () => removeFile(btn.dataset.filename));
  });
}

function renderProcessing() {
  const dot = $('procDot');
  dot.className = 'proc-status-dot ' + state.status;
  const labels = { idle: 'Inactivo', running: 'Procesando…', done: 'Completado', stopped: 'Detenido', error: 'Error' };
  const badges = { idle: 'LISTO', running: 'EN PROCESO', done: 'COMPLETADO', stopped: 'DETENIDO', error: 'ERROR' };
  $('procStatusText').textContent = labels[state.status] || 'Inactivo';
  $('procBadge').textContent = badges[state.status] || '—';

  const pct = state.total > 0 ? (state.processed / state.total * 100) : 0;
  const bar = $('procBar');
  bar.style.width = pct + '%';
  bar.className = 'proc-bar' + (state.status === 'done' ? ' done' : state.status === 'stopped' ? ' stopped' : state.status === 'error' ? ' error' : '');

  $('procProcessed').textContent = fmt(state.processed);
  $('procTotal').textContent = fmt(state.total);
  $('procElapsed').textContent = fmtTime(state.elapsed);

  const btn = $('btnStart');
  if (state.status === 'running') {
    btn.className = 'btn btn-primary danger';
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> Detener';
  } else {
    btn.className = 'btn btn-primary';
    btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21"/></svg> Iniciar Procesamiento';
  }

  $('btnOpenResults').style.display = 'inline-flex';
}

function renderLog() {
  const el = $('logBody');
  el.innerHTML = '';
  for (const l of state.logs) {
    const div = document.createElement('div');
    div.className = 'log-line';
    div.innerHTML = `<span class="log-ts">${l.ts}</span><span class="log-level ${l.level}">${l.level.toUpperCase()}</span><span class="log-msg">${l.msg}</span>`;
    el.appendChild(div);
  }
  el.scrollTop = el.scrollHeight;
}



function renderConfig() {
  if (!state.config) return;
  $('cfgApiUrl').value = state.config.api.base_url || '';
  $('cfgCollectionId').value = state.config.api.default_coll_name || '';
  $('cfgYears').value = (state.config.filters.years_to_check || []).join(', ');
  $('cfgDeclType').value = state.config.filters.common_filters.tipoDeclaracion || '';
  $('cfgInstitution').value = state.config.filters.common_filters.institucionReceptora || '';
  $('cfgWorkers').value = state.config.rate_limit.max_concurrent || 10;
  $('cfgWorkersVal').textContent = state.config.rate_limit.max_concurrent || 10;
  $('cfgBatch').value = state.config.processing.batch_size || 100;
  $('cfgBatchVal').textContent = state.config.processing.batch_size || 100;
  $('cfgRetries').value = state.config.api.max_retries || 5;
  $('cfgRetryBaseDelay').value = state.config.api.retry_base_delay || 2.0;
  $('cfgMinInterval').value = state.config.rate_limit.min_interval || 0.15;
  $('cfgInterBatchDelay').value = state.config.rate_limit.inter_batch_delay || 1.5;
  $('cfgCooldownBase').value = state.config.rate_limit.cooldown_base || 5.0;
  $('cfgCooldownMax').value = state.config.rate_limit.cooldown_max || 60.0;
  $('cfgTimeout').value = state.config.api.timeout || 60;
}

function updateSystemDot() {
  const dot = $('sysStatusDot');
  if (state.status === 'running' || state.status === 'done') {
    dot.className = 'hdr-stat-dot active';
  } else {
    dot.className = 'hdr-stat-dot';
  }
}

function addLog(level, msg) {
  const now = new Date();
  const ts = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
  state.logs.push({ ts, level, msg });
  renderLog();
}

async function addFile(path) {
  try {
    await invoke('add_seed_file', { sourcePath: path });
    await refreshFiles();
    addLog('info', `Archivo agregado: ${path.split(/[\\/]/).pop()}`);
  } catch (e) {
    addLog('error', `Error al agregar archivo: ${e}`);
  }
}

async function removeFile(filename) {
  if (state.isProcessing) return;
  try {
    await invoke('remove_seed_file', { filename });
    await refreshFiles();
    addLog('info', `Archivo eliminado: ${filename}`);
  } catch (e) {
    addLog('error', `Error al eliminar archivo: ${e}`);
  }
}

async function refreshFiles() {
  try {
    state.files = await invoke('get_seed_files');
    renderFileList();
    renderMetrics();
  } catch(e) {
    console.error('Failed to load seed files:', e);
  }
}

async function toggleProcessing() {
  if (state.isProcessing) {
    try {
      await invoke('stop_processing');
      addLog('warn', 'Solicitud de detención enviada…');
      $('btnStart').disabled = true;
    } catch (e) {
      addLog('error', `Error al detener: ${e}`);
    }
  } else {
    state.config.processing.batch_size = parseInt($('cfgBatch').value);
    state.config.processing.max_workers = parseInt($('cfgWorkers').value);
    state.config.rate_limit.max_concurrent = parseInt($('cfgWorkers').value);

    try {
      await invoke('save_config', { newConfig: state.config });
    } catch (e) {
      addLog('error', `Error guardando config: ${e}`);
      return;
    }

    state.startTime = Date.now();
    state.processed = 0;
    state.found = 0;
    state.notFound = 0;
    state.rateLimitErrors = 0;
    state.elapsed = 0;
    state.isProcessing = true;
    state.status = 'running';
    $('btnStart').disabled = false;

    disableFileActions(true);

    try {
      await invoke('start_processing');
      addLog('info', 'Procesamiento iniciado.');
    } catch (e) {
      addLog('error', `Error iniciando procesamiento: ${e}`);
      state.isProcessing = false;
      state.status = 'error';
    }

    renderProcessing();
    renderMetrics();
    updateSystemDot();
  }
}

function onProcessingComplete() {
  state.isProcessing = false;
  disableFileActions(false);
}

function disableFileActions(disabled) {
  const dz = $('dropzone');
  dz.style.pointerEvents = disabled ? 'none' : 'auto';
  dz.style.opacity = disabled ? '0.5' : '1';
  document.querySelectorAll('.file-item-del').forEach(btn => {
    btn.disabled = disabled;
  });
}

async function openResults() {
  try {
    await invoke('open_output_dir');
  } catch(e) {
    addLog('error', `Error al abrir carpeta de resultados: ${e}`);
  }
}

async function saveConfig() {
  if (!state.config) return;

  state.config.api.base_url = $('cfgApiUrl').value;
  state.config.api.default_coll_name = $('cfgCollectionId').value;
  state.config.filters.years_to_check = $('cfgYears').value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
  state.config.filters.common_filters.tipoDeclaracion = $('cfgDeclType').value;
  state.config.filters.common_filters.institucionReceptora = $('cfgInstitution').value;
  state.config.rate_limit.max_concurrent = parseInt($('cfgWorkers').value) || 10;
  state.config.processing.batch_size = parseInt($('cfgBatch').value) || 100;
  state.config.processing.max_workers = parseInt($('cfgWorkers').value) || 10;
  state.config.api.max_retries = parseInt($('cfgRetries').value) || 5;
  state.config.api.retry_base_delay = parseFloat($('cfgRetryBaseDelay').value) || 2.0;
  state.config.rate_limit.min_interval = parseFloat($('cfgMinInterval').value) || 0.15;
  state.config.rate_limit.inter_batch_delay = parseFloat($('cfgInterBatchDelay').value) || 1.5;
  state.config.rate_limit.cooldown_base = parseFloat($('cfgCooldownBase').value) || 5.0;
  state.config.rate_limit.cooldown_max = parseFloat($('cfgCooldownMax').value) || 60.0;
  state.config.api.timeout = parseInt($('cfgTimeout').value) || 60;

  try {
    await invoke('save_config', { newConfig: state.config });
    addLog('info', 'Configuración guardada exitosamente.');
  } catch (e) {
    addLog('error', `Error guardando configuración: ${e}`);
  }
}

function openDrawer() {
  $('drawer').classList.add('open');
  $('drawerOverlay').classList.add('open');
}
function closeDrawer() {
  $('drawer').classList.remove('open');
  $('drawerOverlay').classList.remove('open');
}

async function init() {
  try {
    state.config = await invoke('get_config');
    renderConfig();
  } catch(e) {
    console.warn('Config unavailable:', e);
  }

  try {
    state.files = await invoke('get_seed_files');
    renderFileList();
  } catch(e) {
    console.warn('Seed files unavailable:', e);
  }

  renderMetrics();
  renderProcessing();
  updateSystemDot();

  $('btnSettings').addEventListener('click', openDrawer);
  $('btnCloseDrawer').addEventListener('click', closeDrawer);
  $('drawerOverlay').addEventListener('click', closeDrawer);

  $('btnStart').addEventListener('click', () => toggleProcessing());
  $('btnOpenResults').addEventListener('click', () => openResults());

  $('dropzone').addEventListener('click', async () => {
    try {
      const selected = await open({
        multiple: true,
        filters: [{ name: 'Archivos Excel', extensions: ['xlsx'] }]
      });
      if (!selected) return;
      const files = Array.isArray(selected) ? selected : [selected];
      for (const path of files) {
        await addFile(path);
      }
    } catch(e) {
      addLog('error', `Error al seleccionar archivo: ${e}`);
    }
  });

  $('btnClearLog').addEventListener('click', () => {
    state.logs = [];
    renderLog();
  });

  $('btnSaveConfig').addEventListener('click', () => saveConfig());

  $('cfgWorkers').addEventListener('input', (e) => {
    $('cfgWorkersVal').textContent = e.target.value;
  });
  $('cfgBatch').addEventListener('input', (e) => {
    $('cfgBatchVal').textContent = e.target.value;
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDrawer();
  });

  listen('progress', (event) => {
    const { processed, total, found, not_found } = event.payload;
    state.processed = processed;
    state.total = total;
    if (found !== undefined) state.found = found;
    if (not_found !== undefined) state.notFound = not_found;
    state.elapsed = state.startTime ? (Date.now() - state.startTime) / 1000 : 0;
    renderProcessing();
    renderMetrics();
  });

  listen('log', (event) => {
    const { message, level } = event.payload;
    addLog(level || 'info', message);

    if (message && message.includes('429')) {
      state.rateLimitErrors++;
    }

    if (message === 'Procesamiento completado.') {
      state.status = 'done';
      state.isProcessing = false;
      disableFileActions(false);
      renderProcessing();
      renderMetrics();
      updateSystemDot();
    } else if (message === 'Procesamiento detenido por el usuario.') {
      state.status = 'stopped';
      state.isProcessing = false;
      disableFileActions(false);
      renderProcessing();
      renderMetrics();
      updateSystemDot();
    }
  });

  listen('confirm-close', async () => {
    const confirmed = await ask('El procesamiento está en curso. ¿Deseas detenerlo y cerrar la aplicación?', { title: 'Cerrar aplicación', kind: 'warning', yesLabel: 'Sí', noLabel: 'No' });
    if (confirmed) {
      try {
        await invoke('stop_processing');
      } catch (e) {}
      const win = getCurrentWindow();
      await win.destroy();
    }
  });

  setInterval(() => {
    if (state.status === 'running' && state.startTime) {
      state.elapsed = (Date.now() - state.startTime) / 1000;
      $('procElapsed').textContent = fmtTime(state.elapsed);
    }
  }, 1000);

  addLog('info', 'Auto Servidores iniciado');
  if (state.files.length > 0) {
    addLog('info', `${state.files.length} archivo${state.files.length > 1 ? 's' : ''} cargado${state.files.length > 1 ? 's' : ''} — ${fmt(state.files.reduce((s,f) => s + f.row_count, 0))} RFCs listos`);
  }
}

init();