use crate::models;

pub fn get_system_info() -> models::SystemInfo {
    let sys = sysinfo::System::new_all();
    models::SystemInfo {
        cpu_cores: sys.cpus().len(),
        cpu_physical: sys.physical_core_count().unwrap_or(sys.cpus().len()),
        ram_gb: (sys.total_memory() as f64 / (1024_u64.pow(3)) as f64).round(),
        os: format!("{} {}", sysinfo::System::name().unwrap_or_default(), sysinfo::System::os_version().unwrap_or_default()),
    }
}

pub fn recommend_settings() -> models::RecommendedSettings {
    let sys = sysinfo::System::new_all();
    let cores = sys.cpus().len();
    let ram_gb = sys.total_memory() as f64 / (1024_u64.pow(3)) as f64;
    let max_workers = cores.min(50);
    let batch_size = if ram_gb < 4.0 { 10 } else if ram_gb < 8.0 { 15 } else { 25 };
    models::RecommendedSettings { batch_size, max_workers }
}
