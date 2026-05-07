use crate::models::AppConfig;
use std::fs;
use std::path::Path;

pub fn load_config(path: &Path) -> Result<AppConfig, String> {
    let content = fs::read_to_string(path)
        .map_err(|e| format!("Error reading config file: {}", e))?;
    let config: AppConfig = toml::from_str(&content)
        .map_err(|e| format!("Error parsing config: {}", e))?;
    Ok(config)
}

pub fn save_config(config: &AppConfig, path: &Path) -> Result<(), String> {
    let content = toml::to_string_pretty(config)
        .map_err(|e| format!("Error serializing config: {}", e))?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|e| format!("Error creating config directory: {}", e))?;
    }
    fs::write(path, content)
        .map_err(|e| format!("Error writing config: {}", e))?;
    Ok(())
}

pub fn default_config() -> AppConfig {
    AppConfig {
        api: crate::models::ApiConfig {
            base_url: "https://servicios.dkla8prod.buengobierno.gob.mx".to_string(),
            endpoints: crate::models::ApiEndpoints {
                search: "/declaranet/consulta-servidores-publicos/buscarsp".to_string(),
                history: "/declaranet/consulta-servidores-publicos/historico".to_string(),
            },
            default_coll_name: "100".to_string(),
            timeout: 60,
            max_retries: 5,
            retry_base_delay: 2.0,
        },
        cache: crate::models::CacheConfig {
            enabled: true,
            db_path: ".cache/api_cache.db".to_string(),
            ttl_seconds: 3600,
        },
        rate_limit: crate::models::RateLimitConfig {
            max_concurrent: 10,
            min_interval: 0.15,
            cooldown_base: 5.0,
            cooldown_max: 60.0,
            inter_batch_delay: 1.5,
        },
        filters: crate::models::FiltersConfig {
            years_to_check: vec![2025, 2026],
            common_filters: crate::models::CommonFilters {
                tipoDeclaracion: "MODIFICACION".to_string(),
                institucionReceptora: "INSTITUTO MEXICANO DEL SEGURO SOCIAL".to_string(),
            },
        },
        processing: crate::models::ProcessingConfig {
            batch_size: 100,
            max_workers: 50,
        },
        output: crate::models::OutputConfig {
            dir: "output".to_string(),
            found_suffix: "_ENCONTRADOS".to_string(),
            not_found_suffix: "_NO_ENCONTRADOS".to_string(),
        },
    }
}

pub fn validate_config(config: &AppConfig, _app_dir: &std::path::Path) -> Result<(), String> {
    if !config.api.base_url.starts_with("https://") && !config.api.base_url.starts_with("http://") {
        return Err("base_url must be a valid HTTP(S) URL".to_string());
    }
    if config.api.timeout == 0 || config.api.timeout > 300 {
        return Err("timeout must be between 1 and 300 seconds".to_string());
    }
    if config.api.max_retries > 20 {
        return Err("max_retries must be at most 20".to_string());
    }
    if config.api.retry_base_delay < 0.0 || config.api.retry_base_delay > 60.0 {
        return Err("retry_base_delay must be between 0 and 60 seconds".to_string());
    }
    if config.rate_limit.max_concurrent == 0 || config.rate_limit.max_concurrent > 200 {
        return Err("max_concurrent must be between 1 and 200".to_string());
    }
    if config.rate_limit.min_interval < 0.0 {
        return Err("min_interval must be non-negative".to_string());
    }
    if config.rate_limit.cooldown_base < 0.0 || config.rate_limit.cooldown_max > 300.0 {
        return Err("cooldown_base and cooldown_max must be reasonable (0-300s)".to_string());
    }
    if config.rate_limit.cooldown_base > config.rate_limit.cooldown_max {
        return Err("cooldown_base must not exceed cooldown_max".to_string());
    }
    if config.processing.batch_size == 0 || config.processing.batch_size > 10000 {
        return Err("batch_size must be between 1 and 10000".to_string());
    }
    if config.processing.max_workers == 0 || config.processing.max_workers > 500 {
        return Err("max_workers must be between 1 and 500".to_string());
    }
    if config.cache.db_path.contains("..") {
        return Err("cache db_path must not contain path traversal sequences".to_string());
    }
    if config.output.dir.contains("..") {
        return Err("output dir must not contain path traversal sequences".to_string());
    }
    if config.filters.years_to_check.len() > 50 {
        return Err("years_to_check must contain at most 50 years".to_string());
    }
    Ok(())
}

#[allow(dead_code)]
pub fn resolve_config_path(app_dir: &std::path::Path) -> std::path::PathBuf {
    let config_path = app_dir.join("config.toml");
    if config_path.exists() {
        return config_path;
    }
    config_path
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn test_load_valid_config() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.toml");
        let mut f = fs::File::create(&path).unwrap();
        write!(f, r#"
[api]
base_url = "https://example.com"
default_coll_name = "100"
timeout = 60
max_retries = 5
retry_base_delay = 2.0

[api.endpoints]
search = "/search"
history = "/history"

[cache]
enabled = true
db_path = ".cache/test.db"
ttl_seconds = 3600

[rate_limit]
max_concurrent = 10
min_interval = 0.15
cooldown_base = 5.0
cooldown_max = 60.0
inter_batch_delay = 1.5

[filters]
years_to_check = [2025, 2026]

[filters.common_filters]
tipoDeclaracion = "MODIFICACION"
institucionReceptora = "IMSS"

[processing]
batch_size = 100
max_workers = 50

[output]
dir = "output"
found_suffix = "_ENCONTRADOS"
not_found_suffix = "_NO_ENCONTRADOS"
"#).unwrap();

        let config = load_config(&path).unwrap();
        assert_eq!(config.api.base_url, "https://example.com");
        assert_eq!(config.rate_limit.max_concurrent, 10);
        assert_eq!(config.filters.years_to_check, vec![2025, 2026]);
    }

    #[test]
    fn test_save_and_reload_config() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.toml");
        let config = default_config();
        save_config(&config, &path).unwrap();
        let loaded = load_config(&path).unwrap();
        assert_eq!(loaded.api.base_url, config.api.base_url);
        assert_eq!(loaded.rate_limit.max_concurrent, config.rate_limit.max_concurrent);
    }

    #[test]
    fn test_load_missing_file_returns_error() {
        let result = load_config(std::path::Path::new("/nonexistent/config.toml"));
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_config_valid() {
        let config = default_config();
        let dir = tempfile::tempdir().unwrap();
        assert!(validate_config(&config, dir.path()).is_ok());
    }

    #[test]
    fn test_validate_config_invalid_url() {
        let mut config = default_config();
        config.api.base_url = "not-a-url".to_string();
        let dir = tempfile::tempdir().unwrap();
        assert!(validate_config(&config, dir.path()).is_err());
    }

    #[test]
    fn test_validate_config_zero_timeout() {
        let mut config = default_config();
        config.api.timeout = 0;
        let dir = tempfile::tempdir().unwrap();
        assert!(validate_config(&config, dir.path()).is_err());
    }

    #[test]
    fn test_validate_config_path_traversal_db() {
        let mut config = default_config();
        config.cache.db_path = "../etc/passwd".to_string();
        let dir = tempfile::tempdir().unwrap();
        assert!(validate_config(&config, dir.path()).is_err());
    }

    #[test]
    fn test_validate_config_path_traversal_output() {
        let mut config = default_config();
        config.output.dir = "../../../tmp".to_string();
        let dir = tempfile::tempdir().unwrap();
        assert!(validate_config(&config, dir.path()).is_err());
    }

    #[test]
    fn test_validate_config_cooldown_inversion() {
        let mut config = default_config();
        config.rate_limit.cooldown_base = 60.0;
        config.rate_limit.cooldown_max = 5.0;
        let dir = tempfile::tempdir().unwrap();
        assert!(validate_config(&config, dir.path()).is_err());
    }

    #[test]
    fn test_default_config_is_valid() {
        let config = default_config();
        let dir = tempfile::tempdir().unwrap();
        assert!(validate_config(&config, dir.path()).is_ok());
    }

    #[test]
    fn test_load_malformed_toml() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.toml");
        fs::write(&path, "this is not valid toml [[[").unwrap();
        let result = load_config(&path);
        assert!(result.is_err());
    }

    #[test]
    fn test_save_creates_parent_dirs() {
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("a").join("b").join("config.toml");
        let config = default_config();
        save_config(&config, &nested).unwrap();
        assert!(nested.exists());
    }
}
