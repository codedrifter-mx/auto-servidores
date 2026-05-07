use auto_servidores::config;
use auto_servidores::orchestrator::Orchestrator;
use std::sync::atomic::AtomicBool;
use std::sync::Arc;
use tokio::sync::mpsc;

fn make_test_config_for_orchestrator(output_dir: &str) -> auto_servidores::models::AppConfig {
    let mut cfg = config::default_config();
    cfg.api.timeout = 5;
    cfg.api.max_retries = 1;
    cfg.api.retry_base_delay = 0.01;
    cfg.rate_limit.min_interval = 0.0;
    cfg.rate_limit.inter_batch_delay = 0.0;
    cfg.rate_limit.cooldown_base = 0.01;
    cfg.rate_limit.cooldown_max = 0.1;
    cfg.rate_limit.max_concurrent = 50;
    cfg.processing.batch_size = 100;
    cfg.processing.max_workers = 50;
    cfg.output.dir = output_dir.to_string();
    cfg
}

#[tokio::test]
async fn test_orchestrator_empty_seed_dir() {
    let dir = tempfile::tempdir().unwrap();
    let output_dir = dir.path().join("output");
    let cfg = make_test_config_for_orchestrator(&output_dir.to_string_lossy());
    let orchestrator = Orchestrator::new(cfg, dir.path().to_path_buf());
    let (progress_tx, _progress_rx) = mpsc::unbounded_channel();
    let (log_tx, mut log_rx) = mpsc::unbounded_channel();
    let stop = Arc::new(AtomicBool::new(false));
    let result = orchestrator.run(progress_tx, log_tx, stop).await;
    assert!(result.is_ok());
    let mut found_completion = false;
    while let Ok(event) = log_rx.try_recv() {
        if event.message == "Procesamiento completado." {
            found_completion = true;
        }
    }
    assert!(found_completion);
}
