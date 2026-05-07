pub mod cache;
pub mod client;
pub mod compactor;
pub mod config;
pub mod models;
pub mod orchestrator;
pub mod rate_limit;
pub mod seed_index;
pub mod system_info;
pub mod worker;

use models::AppConfig;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex as StdMutex};
use tauri::{Emitter, Manager};

struct AppState {
    config: StdMutex<AppConfig>,
    app_dir: PathBuf,
    processing: Arc<StdMutex<bool>>,
    stop_requested: Arc<AtomicBool>,
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
    config::validate_config(&new_config, &state.app_dir)?;
    let path = state.app_dir.join("config.toml");
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
    let seed_dir = state.app_dir.join("seed");
    let index = seed_index::SeedIndex::new(&seed_dir)?;
    Ok(index.get_files().to_vec())
}

#[tauri::command]
fn add_seed_file(
    source_path: String,
    state: tauri::State<'_, AppState>,
) -> Result<String, String> {
    let source = PathBuf::from(&source_path);
    if source.extension().and_then(|e| e.to_str()) != Some("xlsx") {
        return Err("Only .xlsx files are allowed".to_string());
    }
    if !source.is_file() {
        return Err("Source path is not a valid file".to_string());
    }
    let seed_dir = state.app_dir.join("seed");
    std::fs::create_dir_all(&seed_dir)
        .map_err(|e| format!("Error creating seed directory: {}", e))?;
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
    let canonical_seed = seed_dir
        .canonicalize()
        .map_err(|e| format!("Invalid seed directory: {}", e))?;
    let canonical_dest = dest
        .canonicalize()
        .unwrap_or_else(|_| dest.clone());
    if !canonical_dest.starts_with(&canonical_seed) && canonical_dest != dest {
        return Err("Destination path escapes seed directory".to_string());
    }
    std::fs::copy(&source, &dest)
        .map_err(|e| format!("Error copying file: {}", e))?;
    Ok(filename)
}

#[tauri::command]
fn remove_seed_file(
    filename: String,
    state: tauri::State<'_, AppState>,
) -> Result<(), String> {
    if filename.contains(std::path::MAIN_SEPARATOR)
        || filename.contains('/')
        || filename.contains('\\')
    {
        return Err("Invalid filename: path separators not allowed".to_string());
    }
    let seed_dir = state.app_dir.join("seed");
    let path = seed_dir.join(&filename);
    let canonical_seed = seed_dir
        .canonicalize()
        .map_err(|e| format!("Invalid seed directory: {}", e))?;
    let canonical_path = match path.canonicalize() {
        Ok(p) => p,
        Err(_) => return Ok(()),
    };
    if !canonical_path.starts_with(&canonical_seed) {
        return Err("Path traversal detected".to_string());
    }
    std::fs::remove_file(&canonical_path)
        .map_err(|e| format!("Error removing file: {}", e))?;
    Ok(())
}

#[tauri::command]
fn stop_processing(state: tauri::State<'_, AppState>) {
    state.stop_requested.store(true, Ordering::Relaxed);
}

#[tauri::command]
fn open_output_dir(state: tauri::State<'_, AppState>) -> Result<(), String> {
    let config = state.config.lock().map_err(|e| e.to_string())?;
    if config.output.dir.contains("..") {
        return Err("Invalid output directory path".to_string());
    }
    let output_dir = state.app_dir.join(&config.output.dir);
    std::fs::create_dir_all(&output_dir)
        .map_err(|e| format!("Error creating output directory: {}", e))?;
    let canonical_app = state
        .app_dir
        .canonicalize()
        .map_err(|e| format!("Invalid app directory: {}", e))?;
    let canonical_output = output_dir
        .canonicalize()
        .map_err(|e| format!("Invalid output directory: {}", e))?;
    if !canonical_output.starts_with(&canonical_app) {
        return Err("Output directory must be within app directory".to_string());
    }
    if !canonical_output.is_dir() {
        return Err("Output path is not a directory".to_string());
    }
    opener::open(&canonical_output)
        .map_err(|e| format!("Error opening output directory: {}", e))
}

#[tauri::command]
async fn start_processing(
    app: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
) -> Result<String, String> {
    let mut processing = state.processing.lock().map_err(|e| e.to_string())?;
    if *processing {
        return Err("Processing already in progress".to_string());
    }
    *processing = true;
    drop(processing);
    state.stop_requested.store(false, Ordering::Relaxed);

    let config = {
        let cfg = state.config.lock().map_err(|e| e.to_string())?;
        cfg.clone()
    };
    let app_dir = state.app_dir.clone();
    let stop_requested = Arc::clone(&state.stop_requested);

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
        let orchestrator = orchestrator::Orchestrator::new(config, app_dir);
        let result = orchestrator.run(progress_tx, log_tx, stop_requested).await;
        if let Err(e) = result {
            log::error!("Processing failed: {}", e);
        }
        let mut guard = processing_state.lock().unwrap_or_else(|e| e.into_inner());
        *guard = false;
    });

    Ok("started".to_string())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let app_dir = app.path().app_data_dir()
                .unwrap_or_else(|_| {
                    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
                });
            
            std::fs::create_dir_all(&app_dir)
                .map_err(|e| format!("Failed to create app data dir: {}", e))?;

            let config_path = app_dir.join("config.toml");
            
            if !config_path.exists() {
                let bundled = app.path().resource_dir()
                    .map(|r| r.join("config.toml"))
                    .unwrap_or_else(|_| PathBuf::from("config.toml"));
                
                if bundled.exists() {
                    let _ = std::fs::copy(&bundled, &config_path);
                }
            }

            let config = if config_path.exists() {
                config::load_config(&config_path).unwrap_or_else(|_| config::default_config())
            } else {
                config::default_config()
            };

            let processing = Arc::new(StdMutex::new(false));
            let stop_requested = Arc::new(AtomicBool::new(false));

            let processing_clone = Arc::clone(&processing);
            let app_handle = app.handle().clone();
            
            let window = app.get_webview_window("main").unwrap();
            window.on_window_event(move |event| {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    if *processing_clone.lock().unwrap_or_else(|e| e.into_inner()) {
                        api.prevent_close();
                        let _ = app_handle.emit_to("main", "confirm-close", ());
                    }
                }
            });

            app.manage(AppState {
                config: StdMutex::new(config),
                app_dir,
                processing,
                stop_requested,
            });

            Ok(())
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
            stop_processing,
            open_output_dir,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
