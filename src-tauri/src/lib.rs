mod cache;
mod client;
mod compactor;
mod config;
mod models;
mod orchestrator;
mod rate_limit;
mod seed_index;
mod system_info;
mod worker;

use models::AppConfig;
use std::path::PathBuf;
use std::sync::{Arc, Mutex as StdMutex};
use tauri::{Emitter, Manager};

struct AppState {
    config: StdMutex<AppConfig>,
    config_dir: PathBuf,
    processing: Arc<StdMutex<bool>>,
}

fn get_app_dir(app: &tauri::AppHandle) -> PathBuf {
    app.path().app_data_dir().unwrap_or_else(|_| PathBuf::from("."))
}

fn resolve_config_path(app_dir: &std::path::Path) -> PathBuf {
    let config_path = app_dir.join("config.toml");
    if config_path.exists() {
        return config_path;
    }
    let bundled = app_dir.join("config.toml");
    if bundled.exists() && bundled != config_path {
        let _ = std::fs::copy(&bundled, &config_path);
    }
    config_path
}

#[tauri::command]
fn get_system_info() -> models::SystemInfo {
    system_info::get_system_info()
}

#[tauri::command]
fn get_config(state: tauri::State<'_, AppState>) -> Result<AppConfig, String> {
    let config = state.config.lock().map_err(|e| e.to_string())?;
    Ok(config.clone())
}

#[tauri::command]
fn save_config(
    new_config: AppConfig,
    state: tauri::State<'_, AppState>,
) -> Result<(), String> {
    let path = resolve_config_path(&state.config_dir);
    config::save_config(&new_config, &path)?;
    let mut cfg = state.config.lock().map_err(|e| e.to_string())?;
    *cfg = new_config;
    Ok(())
}

#[tauri::command]
fn get_recommended_settings() -> models::RecommendedSettings {
    system_info::recommend_settings()
}

#[tauri::command]
fn get_seed_files(state: tauri::State<'_, AppState>) -> Result<Vec<models::SeedFileInfo>, String> {
    let seed_dir = state.config_dir.join("seed");
    let index = seed_index::SeedIndex::new(&seed_dir)?;
    Ok(index.get_files().to_vec())
}

#[tauri::command]
fn add_seed_file(
    source_path: String,
    state: tauri::State<'_, AppState>,
) -> Result<String, String> {
    let seed_dir = state.config_dir.join("seed");
    std::fs::create_dir_all(&seed_dir)
        .map_err(|e| format!("Error creating seed directory: {}", e))?;
    let source = PathBuf::from(&source_path);
    let filename = source
        .file_name()
        .ok_or("Invalid source path")?
        .to_string_lossy()
        .to_string();
    let dest = seed_dir.join(&filename);
    let dest = if dest.exists() {
        let stem = source.file_stem().unwrap().to_string_lossy().to_string();
        let ext = source.extension().unwrap().to_string_lossy().to_string();
        let mut i = 1;
        loop {
            let candidate = seed_dir.join(format!("{}_{}.{}", stem, i, ext));
            if !candidate.exists() {
                break candidate;
            }
            i += 1;
        }
    } else {
        dest
    };
    std::fs::copy(&source, &dest)
        .map_err(|e| format!("Error copying file: {}", e))?;
    Ok(dest.to_string_lossy().to_string())
}

#[tauri::command]
fn remove_seed_file(
    filename: String,
    state: tauri::State<'_, AppState>,
) -> Result<(), String> {
    let path = state.config_dir.join("seed").join(&filename);
    if path.exists() {
        std::fs::remove_file(&path)
            .map_err(|e| format!("Error removing file: {}", e))?;
    }
    Ok(())
}

#[tauri::command]
async fn start_processing(
    app: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
) -> Result<String, String> {
    let is_processing = state.processing.lock().map_err(|e| e.to_string())?;
    if *is_processing {
        return Err("Processing already in progress".to_string());
    }
    drop(is_processing);
    *state.processing.lock().map_err(|e| e.to_string())? = true;

    let config = {
        let cfg = state.config.lock().map_err(|e| e.to_string())?;
        cfg.clone()
    };
    let config_dir = state.config_dir.clone();

    let (progress_tx, mut progress_rx) = tokio::sync::mpsc::unbounded_channel();
    let (log_tx, mut log_rx) = tokio::sync::mpsc::unbounded_channel();

    let app_handle = app.clone();
    let processing_state = state.processing.clone();
    
    tokio::spawn(async move {
        while let Some(event) = progress_rx.recv().await {
            let _ = app_handle.emit("progress", &event);
        }
    });

    let app2 = app.clone();
    tokio::spawn(async move {
        while let Some(event) = log_rx.recv().await {
            let _ = app2.emit("log", &event);
        }
    });

    tokio::spawn(async move {
        let orchestrator = orchestrator::Orchestrator::new(config, config_dir);
        let result = orchestrator.run(progress_tx, log_tx).await;
        if let Err(e) = result {
            log::error!("Processing failed: {}", e);
        }
        *processing_state.lock().unwrap() = false;
    });

    Ok("started".to_string())
}

pub fn run() {
    let app_dir = std::path::PathBuf::from(".");
    let config_path = resolve_config_path(&app_dir);
    let config = if config_path.exists() {
        config::load_config(&config_path).unwrap_or_else(|_| config::default_config())
    } else {
        config::default_config()
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState {
            config: StdMutex::new(config),
            config_dir: app_dir,
            processing: Arc::new(StdMutex::new(false)),
        })
        .invoke_handler(tauri::generate_handler![
            get_system_info,
            get_config,
            save_config,
            get_recommended_settings,
            get_seed_files,
            add_seed_file,
            remove_seed_file,
            start_processing,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
