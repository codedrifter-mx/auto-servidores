mod cache;
mod client;
mod compactor;
mod config;
mod models;
mod orchestrator;
mod rate_limit;
mod seed_index;
mod worker;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hola, {}!", name)
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
