use auto_servidores::config;

#[test]
fn test_config_save_load_preserves_all_fields() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("config.toml");
    let original = config::default_config();
    config::save_config(&original, &path).unwrap();
    let loaded = config::load_config(&path).unwrap();
    assert_eq!(loaded.api.base_url, original.api.base_url);
    assert_eq!(loaded.api.endpoints.search, original.api.endpoints.search);
    assert_eq!(loaded.api.endpoints.history, original.api.endpoints.history);
    assert_eq!(loaded.api.default_coll_name, original.api.default_coll_name);
    assert_eq!(loaded.api.timeout, original.api.timeout);
    assert_eq!(loaded.api.max_retries, original.api.max_retries);
    assert_eq!(loaded.api.retry_base_delay, original.api.retry_base_delay);
    assert_eq!(loaded.cache.enabled, original.cache.enabled);
    assert_eq!(loaded.cache.db_path, original.cache.db_path);
    assert_eq!(loaded.cache.ttl_seconds, original.cache.ttl_seconds);
    assert_eq!(loaded.rate_limit.max_concurrent, original.rate_limit.max_concurrent);
    assert_eq!(loaded.rate_limit.min_interval, original.rate_limit.min_interval);
    assert_eq!(loaded.rate_limit.cooldown_base, original.rate_limit.cooldown_base);
    assert_eq!(loaded.rate_limit.cooldown_max, original.rate_limit.cooldown_max);
    assert_eq!(loaded.rate_limit.inter_batch_delay, original.rate_limit.inter_batch_delay);
    assert_eq!(loaded.filters.years_to_check, original.filters.years_to_check);
    assert_eq!(loaded.filters.common_filters.tipoDeclaracion, original.filters.common_filters.tipoDeclaracion);
    assert_eq!(loaded.filters.common_filters.institucionReceptora, original.filters.common_filters.institucionReceptora);
    assert_eq!(loaded.processing.batch_size, original.processing.batch_size);
    assert_eq!(loaded.processing.max_workers, original.processing.max_workers);
    assert_eq!(loaded.output.dir, original.output.dir);
    assert_eq!(loaded.output.found_suffix, original.output.found_suffix);
    assert_eq!(loaded.output.not_found_suffix, original.output.not_found_suffix);
}

#[test]
fn test_config_validation_rejects_traversal() {
    let dir = tempfile::tempdir().unwrap();
    let mut config = config::default_config();
    config.cache.db_path = "../../../etc/passwd".to_string();
    assert!(config::validate_config(&config, dir.path()).is_err());
    config.cache.db_path = ".cache/api_cache.db".to_string();
    config.output.dir = "../../tmp".to_string();
    assert!(config::validate_config(&config, dir.path()).is_err());
}
