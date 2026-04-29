import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { open } from '@tauri-apps/plugin-dialog';

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
  btnAuto: document.getElementById('btn-auto'),
  btnStart: document.getElementById('btn-start'),
  logText: document.getElementById('log-text'),
  progressBar: document.getElementById('progress-bar'),
  statusLabel: document.getElementById('status-label'),
  settingsForm: document.getElementById('settings-form'),
  btnSaveConfig: document.getElementById('btn-save-config'),
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
  if (files.length === 0) {
    els.seedList.innerHTML = '<div class="empty-state">Aún no hay archivos de origen.<br>Agrega archivos .xlsx para comenzar.</div>';
    return;
  }
  els.seedList.innerHTML = files.map(f => `
    <div class="seed-item">
      <span class="seed-item-name" title="${f.filename}">${f.filename}</span>
      <span class="seed-item-count">${f.row_count} filas</span>
      <button class="seed-item-delete" data-file="${f.filename}">×</button>
    </div>
  `).join('');
  
  els.seedList.querySelectorAll('.seed-item-delete').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const filename = e.target.dataset.file;
      try {
        await invoke('remove_seed_file', { filename });
        await loadSeedFiles();
        appendLog(`Eliminado ${filename}.`, 'info');
      } catch (err) {
        appendLog(`Error eliminando ${filename}: ${err}`, 'error');
      }
    });
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

async function autoConfig() {
  try {
    const rec = await invoke('get_recommended_settings');
    els.sliderBatch.value = rec.batch_size;
    els.batchValue.textContent = rec.batch_size;
    els.sliderWorker.value = rec.max_workers;
    els.workerValue.textContent = rec.max_workers;
    appendLog(`Auto-configurado: batch_size=${rec.batch_size}, max_workers=${rec.max_workers}`, 'info');
  } catch (e) {
    appendLog(`Error en auto-configuración: ${e}`, 'error');
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
  els.btnStart.textContent = 'Ejecutando...';
  els.btnStart.disabled = true;
  els.btnAuto.disabled = true;
  els.sliderBatch.disabled = true;
  els.sliderWorker.disabled = true;
  els.btnAddFile.disabled = true;
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

function onProcessingComplete() {
  isProcessing = false;
  els.btnStart.textContent = 'Iniciar Procesamiento';
  els.btnStart.disabled = false;
  els.btnAuto.disabled = false;
  els.sliderBatch.disabled = false;
  els.sliderWorker.disabled = false;
  els.btnAddFile.disabled = false;
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
    if (message === 'Procesamiento completado.') {
      onProcessingComplete();
    }
  });
}

function setupEventListeners() {
  els.btnAddFile.addEventListener('click', addFile);
  els.btnAuto.addEventListener('click', autoConfig);
  els.btnStart.addEventListener('click', startProcessing);
  
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
  
  els.settingsForm.innerHTML = sections.map(section => `
    <div class="settings-section">
      <div class="settings-section-title">${section.title}</div>
      ${section.fields.map(field => `
        <div class="setting-row">
          <span class="setting-label">${field.label}</span>
          <input class="setting-input" type="text" data-key="${field.key}" value="${field.value}">
        </div>
      `).join('')}
    </div>
  `).join('');
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
