import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { open } from '@tauri-apps/plugin-dialog';
import { getCurrentWindow } from '@tauri-apps/api/window';

// State
let config = null;
let isProcessing = false;

// DOM Elements
const els = {
  cpuInfo: document.getElementById('cpu-info'),
  ramInfo: document.getElementById('ram-info'),
  btnAddFile: document.getElementById('btn-add-file'),
  seedList: document.getElementById('seed-list'),
  sliderBatch: document.getElementById('slider-batch'),
  sliderWorker: document.getElementById('slider-worker'),
  batchValue: document.getElementById('batch-value'),
  workerValue: document.getElementById('worker-value'),

  btnStart: document.getElementById('btn-start'),
  logText: document.getElementById('log-text'),
  progressBar: document.getElementById('progress-bar'),
  statusLabel: document.getElementById('status-label'),
  settingsForm: document.getElementById('settings-form'),
  btnSaveConfig: document.getElementById('btn-save-config'),
  btnOpenOutput: document.getElementById('btn-open-output'),
  tabBtns: document.querySelectorAll('.tab-btn'),
  tabPanels: document.querySelectorAll('.tab-panel'),
};

// Initialize
async function init() {
  await loadSystemInfo();
  await loadConfig();
  await loadSeedFiles();
  setupEventListeners();
  setupTauriEvents();
}

async function loadSystemInfo() {
  try {
    const info = await invoke('get_system_info');
    els.cpuInfo.textContent = `CPU: ${info.cpu_cores} núcleos`;
    els.ramInfo.textContent = `RAM: ${info.ram_gb} GB`;
  } catch (e) {
    console.error('Failed to load system info:', e);
  }
}

async function loadConfig() {
  try {
    config = await invoke('get_config');
    updateSlidersFromConfig();
    renderSettingsForm();
  } catch (e) {
    console.error('Failed to load config:', e);
  }
}

function updateSlidersFromConfig() {
  if (!config) return;
  els.sliderBatch.value = config.processing.batch_size;
  els.batchValue.textContent = config.processing.batch_size;
  els.sliderWorker.value = config.processing.max_workers;
  els.workerValue.textContent = config.processing.max_workers;
}

async function loadSeedFiles() {
  try {
    const files = await invoke('get_seed_files');
    renderSeedList(files);
  } catch (e) {
    console.error('Failed to load seed files:', e);
  }
}

function renderSeedList(files) {
  els.seedList.innerHTML = '';
  if (files.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'Aún no hay archivos de origen. Agrega archivos .xlsx para comenzar.';
    els.seedList.appendChild(empty);
    return;
  }
  files.forEach(f => {
    const item = document.createElement('div');
    item.className = 'seed-item';
    const name = document.createElement('span');
    name.className = 'seed-item-name';
    name.title = f.filename;
    name.textContent = f.filename;
    const count = document.createElement('span');
    count.className = 'seed-item-count';
    count.textContent = f.row_count + ' filas';
    const btn = document.createElement('button');
    btn.className = 'seed-item-delete';
    btn.dataset.file = f.filename;
    btn.textContent = '\u00d7';
    if (isProcessing) btn.disabled = true;
    btn.addEventListener('click', async () => {
      if (isProcessing) return;
      const filename = btn.dataset.file;
      try {
        await invoke('remove_seed_file', { filename });
        await loadSeedFiles();
        appendLog(`Eliminado ${filename}.`, 'info');
      } catch (err) {
        appendLog(`Error eliminando ${filename}: ${err}`, 'error');
      }
    });
    item.append(name, count, btn);
    els.seedList.appendChild(item);
  });
}

function updateSeedListState() {
  els.seedList.querySelectorAll('.seed-item-delete').forEach(btn => {
    btn.disabled = isProcessing;
  });
}

async function addFile() {
  try {
    const selected = await open({
      multiple: true,
      filters: [{
        name: 'Archivos Excel',
        extensions: ['xlsx']
      }]
    });
    if (!selected) return;
    const files = Array.isArray(selected) ? selected : [selected];
    let copied = 0;
    for (const path of files) {
      await invoke('add_seed_file', { sourcePath: path });
      copied++;
    }
    await loadSeedFiles();
    appendLog(`Agregado(s) ${copied} archivo(s) a la carpeta de origen.`, 'info');
  } catch (e) {
    appendLog(`Error agregando archivo: ${e}`, 'error');
  }
}

async function startProcessing() {
  if (isProcessing) return;

  // Sync config from sliders
  config.processing.batch_size = parseInt(els.sliderBatch.value);
  config.processing.max_workers = parseInt(els.sliderWorker.value);

  try {
    await invoke('save_config', { newConfig: config });
  } catch (e) {
    appendLog(`Error guardando config: ${e}`, 'error');
    return;
  }

  isProcessing = true;
  els.btnStart.textContent = 'Detener';
  els.btnStart.classList.add('btn-stop');
  els.btnStart.disabled = false;

  els.sliderBatch.disabled = true;
  els.sliderWorker.disabled = true;
  els.btnAddFile.disabled = true;
  updateSeedListState();
  els.progressBar.value = 0;
  els.statusLabel.textContent = 'Iniciando...';
  els.logText.innerHTML = '';

  try {
    await invoke('start_processing');
    appendLog('Procesamiento iniciado.', 'info');
  } catch (e) {
    appendLog(`Error iniciando procesamiento: ${e}`, 'error');
    onProcessingComplete();
  }
}

async function stopProcessing() {
  if (!isProcessing) return;
  try {
    await invoke('stop_processing');
    appendLog('Solicitud de detención enviada...', 'info');
    els.btnStart.disabled = true;
    els.btnStart.textContent = 'Deteniendo...';
  } catch (e) {
    appendLog(`Error deteniendo procesamiento: ${e}`, 'error');
  }
}

function onProcessingComplete() {
  isProcessing = false;
  els.btnStart.textContent = 'Iniciar Procesamiento';
  els.btnStart.classList.remove('btn-stop');
  els.btnStart.disabled = false;

  els.sliderBatch.disabled = false;
  els.sliderWorker.disabled = false;
  els.btnAddFile.disabled = false;
  updateSeedListState();
  els.progressBar.value = 100;
  els.statusLabel.textContent = 'Listo';
}

function appendLog(message, level = 'info') {
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  const timestamp = new Date().toLocaleTimeString();
  entry.textContent = `[${timestamp}] [${level.toUpperCase()}] ${message}`;
  els.logText.appendChild(entry);
  els.logText.scrollTop = els.logText.scrollHeight;
}

function setupTauriEvents() {
  listen('progress', (event) => {
    const { processed, total } = event.payload;
    if (total > 0) {
      els.progressBar.value = (processed / total) * 100;
      els.statusLabel.textContent = `Procesados ${processed} / ${total}`;
    }
  });

  listen('log', (event) => {
    const { message, level } = event.payload;
    appendLog(message, level);
    if (message === 'Procesamiento completado.' || message === 'Procesamiento detenido por el usuario.') {
      onProcessingComplete();
    }
  });

  listen('confirm-close', async () => {
    const confirmed = confirm('El procesamiento está en curso. ¿Deseas detenerlo y cerrar la aplicación?');
    if (confirmed) {
      try {
        await invoke('stop_processing');
      } catch (e) {
        // ignore
      }
      const win = getCurrentWindow();
      await win.close();
    }
  });
}

function setupEventListeners() {
  els.btnAddFile.addEventListener('click', addFile);
  els.btnStart.addEventListener('click', () => {
    if (isProcessing) {
      stopProcessing();
    } else {
      startProcessing();
    }
  });
  
  els.sliderBatch.addEventListener('input', (e) => {
    els.batchValue.textContent = e.target.value;
  });
  
  els.sliderWorker.addEventListener('input', (e) => {
    els.workerValue.textContent = e.target.value;
  });
  
  els.tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      els.tabBtns.forEach(b => b.classList.remove('active'));
      els.tabPanels.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(`tab-${tab}`).classList.add('active');
    });
  });
  
  els.btnSaveConfig.addEventListener('click', saveSettings);
  els.btnOpenOutput.addEventListener('click', openOutputFolder);
}

function renderSettingsForm() {
  if (!config) return;

  const sections = [
    {
      title: 'Configuración API',
      fields: [
        { label: 'URL Base:', key: 'api.base_url', value: config.api.base_url },
        { label: 'ID de Colección:', key: 'api.default_coll_name', value: config.api.default_coll_name },
      ]
    },
    {
      title: 'Filtros',
      fields: [
        { label: 'Años:', key: 'filters.years_to_check', value: config.filters.years_to_check.join(', ') },
      ]
    },
    {
      title: 'Rate Limit',
      fields: [
        { label: 'Conexiones Máximas:', key: 'rate_limit.max_concurrent', value: config.rate_limit.max_concurrent },
        { label: 'Intervalo Mínimo (seg):', key: 'rate_limit.min_interval', value: config.rate_limit.min_interval },
        { label: 'Cooldown Base (seg):', key: 'rate_limit.cooldown_base', value: config.rate_limit.cooldown_base },
        { label: 'Cooldown Máx (seg):', key: 'rate_limit.cooldown_max', value: config.rate_limit.cooldown_max },
        { label: 'Pausa Entre Lotes (seg):', key: 'rate_limit.inter_batch_delay', value: config.rate_limit.inter_batch_delay },
      ]
    },
    {
      title: 'Reintentos',
      fields: [
        { label: 'Reintentos Máximos:', key: 'api.max_retries', value: config.api.max_retries },
        { label: 'Base Espera (seg):', key: 'api.retry_base_delay', value: config.api.retry_base_delay },
      ]
    }
  ];

  els.settingsForm.innerHTML = '';
  sections.forEach(section => {
    const sectionDiv = document.createElement('div');
    sectionDiv.className = 'settings-section';
    const titleDiv = document.createElement('div');
    titleDiv.className = 'settings-section-title';
    titleDiv.textContent = section.title;
    sectionDiv.appendChild(titleDiv);
    section.fields.forEach(field => {
      const row = document.createElement('div');
      row.className = 'setting-row';
      const label = document.createElement('span');
      label.className = 'setting-label';
      label.textContent = field.label;
      const input = document.createElement('input');
      input.className = 'setting-input';
      const isNumeric = typeof field.value === 'number';
      if (isNumeric) {
        input.type = 'number';
        input.step = Number.isInteger(field.value) ? '1' : '0.1';
        input.min = '0';
      } else {
        input.type = 'text';
      }
      input.dataset.key = field.key;
      input.value = field.value;
      row.append(label, input);
      sectionDiv.appendChild(row);
    });
    els.settingsForm.appendChild(sectionDiv);
  });
}

async function openOutputFolder() {
  try {
    await invoke('open_output_dir');
  } catch (e) {
    appendLog(`Error abriendo carpeta de resultados: ${e}`, 'error');
  }
}

async function saveSettings() {
  if (!config) return;
  
  const inputs = els.settingsForm.querySelectorAll('.setting-input');
  inputs.forEach(input => {
    const key = input.dataset.key;
    const value = input.value;
    const keys = key.split('.');
    let target = config;
    for (let i = 0; i < keys.length - 1; i++) {
      target = target[keys[i]];
    }
    const lastKey = keys[keys.length - 1];
    
    if (lastKey === 'years_to_check') {
      target[lastKey] = value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
    } else if (typeof target[lastKey] === 'number') {
      const num = parseFloat(value);
      target[lastKey] = isNaN(num) ? target[lastKey] : num;
    } else {
      target[lastKey] = value;
    }
  });
  
  try {
    await invoke('save_config', { newConfig: config });
    appendLog('Configuración guardada exitosamente.', 'info');
  } catch (e) {
    appendLog(`Error guardando configuración: ${e}`, 'error');
  }
}

// Start
init();
