use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub api: ApiConfig,
    pub cache: CacheConfig,
    pub rate_limit: RateLimitConfig,
    pub filters: FiltersConfig,
    pub processing: ProcessingConfig,
    pub output: OutputConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiConfig {
    pub base_url: String,
    pub endpoints: ApiEndpoints,
    #[serde(default = "default_coll_name")]
    pub default_coll_name: String,
    #[serde(default = "default_timeout")]
    pub timeout: u64,
    #[serde(default = "default_max_retries")]
    pub max_retries: u32,
    #[serde(default = "default_retry_base_delay")]
    pub retry_base_delay: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiEndpoints {
    pub search: String,
    pub history: String,
}

fn default_coll_name() -> String { "100".to_string() }
fn default_timeout() -> u64 { 60 }
fn default_max_retries() -> u32 { 5 }
fn default_retry_base_delay() -> f64 { 2.0 }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default = "default_db_path")]
    pub db_path: String,
    #[serde(default = "default_ttl")]
    pub ttl_seconds: u64,
}

fn default_true() -> bool { true }
fn default_db_path() -> String { ".cache/api_cache.db".to_string() }
fn default_ttl() -> u64 { 3600 }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateLimitConfig {
    #[serde(default = "default_max_concurrent")]
    pub max_concurrent: usize,
    #[serde(default = "default_min_interval")]
    pub min_interval: f64,
    #[serde(default = "default_cooldown_base")]
    pub cooldown_base: f64,
    #[serde(default = "default_cooldown_max")]
    pub cooldown_max: f64,
    #[serde(default = "default_inter_batch_delay")]
    pub inter_batch_delay: f64,
}

fn default_max_concurrent() -> usize { 10 }
fn default_min_interval() -> f64 { 0.15 }
fn default_cooldown_base() -> f64 { 5.0 }
fn default_cooldown_max() -> f64 { 60.0 }
fn default_inter_batch_delay() -> f64 { 1.5 }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FiltersConfig {
    pub years_to_check: Vec<u32>,
    #[serde(default)]
    pub common_filters: CommonFilters,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[allow(non_snake_case)]
pub struct CommonFilters {
    #[serde(default = "default_tipo_declaracion")]
    pub tipoDeclaracion: String,
    #[serde(default = "default_institucion")]
    pub institucionReceptora: String,
}

fn default_tipo_declaracion() -> String { "MODIFICACION".to_string() }
fn default_institucion() -> String { "INSTITUTO MEXICANO DEL SEGURO SOCIAL".to_string() }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingConfig {
    #[serde(default = "default_batch_size")]
    pub batch_size: usize,
    #[serde(default = "default_max_workers")]
    pub max_workers: usize,
}

fn default_batch_size() -> usize { 100 }
fn default_max_workers() -> usize { 50 }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutputConfig {
    #[serde(default = "default_output_dir")]
    pub dir: String,
    #[serde(default = "default_found_suffix")]
    pub found_suffix: String,
    #[serde(default = "default_not_found_suffix")]
    pub not_found_suffix: String,
}

fn default_output_dir() -> String { "output".to_string() }
fn default_found_suffix() -> String { "_ENCONTRADOS".to_string() }
fn default_not_found_suffix() -> String { "_NO_ENCONTRADOS".to_string() }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PersonResult {
    pub name: String,
    pub rfc: String,
    pub status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub comprobantes: Option<HashMap<u32, String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemInfo {
    pub cpu_cores: usize,
    pub cpu_physical: usize,
    pub ram_gb: f64,
    pub os: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SeedFileInfo {
    pub filename: String,
    #[serde(skip_serializing)]
    pub filepath: String,
    pub basename: String,
    pub row_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecommendedSettings {
    pub batch_size: usize,
    pub max_workers: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProgressEvent {
    pub processed: usize,
    pub total: usize,
    pub found: usize,
    pub not_found: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEvent {
    pub message: String,
    pub level: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_appconfig_toml_roundtrip() {
        let config = crate::config::default_config();
        let toml_str = toml::to_string_pretty(&config).unwrap();
        let parsed: AppConfig = toml::from_str(&toml_str).unwrap();
        assert_eq!(parsed.api.base_url, config.api.base_url);
        assert_eq!(parsed.api.endpoints.search, config.api.endpoints.search);
        assert_eq!(parsed.api.default_coll_name, config.api.default_coll_name);
        assert_eq!(parsed.api.timeout, config.api.timeout);
        assert_eq!(parsed.api.max_retries, config.api.max_retries);
        assert_eq!(parsed.api.retry_base_delay, config.api.retry_base_delay);
        assert_eq!(parsed.cache.enabled, config.cache.enabled);
        assert_eq!(parsed.cache.db_path, config.cache.db_path);
        assert_eq!(parsed.cache.ttl_seconds, config.cache.ttl_seconds);
        assert_eq!(parsed.rate_limit.max_concurrent, config.rate_limit.max_concurrent);
        assert_eq!(parsed.rate_limit.min_interval, config.rate_limit.min_interval);
        assert_eq!(parsed.rate_limit.cooldown_base, config.rate_limit.cooldown_base);
        assert_eq!(parsed.rate_limit.cooldown_max, config.rate_limit.cooldown_max);
        assert_eq!(parsed.rate_limit.inter_batch_delay, config.rate_limit.inter_batch_delay);
        assert_eq!(parsed.filters.years_to_check, config.filters.years_to_check);
        assert_eq!(parsed.filters.common_filters.tipoDeclaracion, config.filters.common_filters.tipoDeclaracion);
        assert_eq!(parsed.filters.common_filters.institucionReceptora, config.filters.common_filters.institucionReceptora);
        assert_eq!(parsed.processing.batch_size, config.processing.batch_size);
        assert_eq!(parsed.processing.max_workers, config.processing.max_workers);
        assert_eq!(parsed.output.dir, config.output.dir);
        assert_eq!(parsed.output.found_suffix, config.output.found_suffix);
        assert_eq!(parsed.output.not_found_suffix, config.output.not_found_suffix);
    }

    #[test]
    fn test_personresult_json_roundtrip() {
        let mut comprobantes = std::collections::HashMap::new();
        comprobantes.insert(2025, "COMP001".to_string());
        let person = PersonResult {
            name: "JUAN PEREZ".to_string(),
            rfc: "XEXX010101000".to_string(),
            status: "Found".to_string(),
            comprobantes: Some(comprobantes),
        };
        let json = serde_json::to_string(&person).unwrap();
        let parsed: PersonResult = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.name, person.name);
        assert_eq!(parsed.rfc, person.rfc);
        assert_eq!(parsed.status, person.status);
        assert!(parsed.comprobantes.is_some());
        assert_eq!(parsed.comprobantes.unwrap().get(&2025), Some(&"COMP001".to_string()));
    }

    #[test]
    fn test_personresult_without_comprobantes() {
        let person = PersonResult {
            name: "MARIA LOPEZ".to_string(),
            rfc: "XEXX020202000".to_string(),
            status: "Not found".to_string(),
            comprobantes: None,
        };
        let json = serde_json::to_string(&person).unwrap();
        assert!(!json.contains("comprobantes"));
        let parsed: PersonResult = serde_json::from_str(&json).unwrap();
        assert!(parsed.comprobantes.is_none());
    }

    #[test]
    fn test_progress_event_json_shape() {
        let event = ProgressEvent {
            processed: 50,
            total: 100,
            found: 10,
            not_found: 40,
        };
        let json = serde_json::to_string(&event).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed["processed"], 50);
        assert_eq!(parsed["total"], 100);
        assert_eq!(parsed["found"], 10);
        assert_eq!(parsed["not_found"], 40);
    }
}
