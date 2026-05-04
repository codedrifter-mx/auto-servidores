use crate::cache::ApiCache;
use crate::client::create_client;
use crate::compactor::Compactor;
use crate::models::AppConfig;
use crate::rate_limit::RateLimitGate;
use crate::seed_index::SeedIndex;
use crate::worker::process_person;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::sync::mpsc;

pub struct Orchestrator {
    config: AppConfig,
    config_dir: PathBuf,
}

impl Orchestrator {
    pub fn new(config: AppConfig, config_dir: PathBuf) -> Self {
        Self { config, config_dir }
    }

    pub async fn run(
        &self,
        progress_tx: mpsc::UnboundedSender<crate::models::ProgressEvent>,
        log_tx: mpsc::UnboundedSender<crate::models::LogEvent>,
        stop_requested: Arc<AtomicBool>,
    ) -> Result<(), String> {
        let _ = log_tx.send(crate::models::LogEvent {
            message: "Iniciando procesamiento de datos".to_string(),
            level: "info".to_string(),
        });

        let cache_path = self.resolve_path(&self.config.cache.db_path);
        let output_dir = self.resolve_path(&self.config.output.dir);
        let seed_dir = self.config_dir.join("seed");

        let cache = ApiCache::new(
            &cache_path,
            self.config.cache.ttl_seconds,
            self.config.cache.enabled,
        )?;
        let client = create_client(&self.config)?;
        let rate_gate = RateLimitGate::new(
            self.config.rate_limit.max_concurrent,
            self.config.rate_limit.min_interval,
            self.config.rate_limit.cooldown_base,
            self.config.rate_limit.cooldown_max,
        );
        let mut seed_index = SeedIndex::new(&seed_dir)?;

        let files = seed_index.get_files().to_vec();
        let total_rows: usize = files.iter().map(|f| f.row_count).sum();
        let mut processed_overall: usize = 0;
        let mut found_overall: usize = 0;
        let mut not_found_overall: usize = 0;

        for file_info in &files {
            let mut found = Vec::new();
            let mut not_found = Vec::new();

            let _ = log_tx.send(crate::models::LogEvent {
                message: format!(
                    "Procesando: {} ({} filas)",
                    file_info.filename, file_info.row_count
                ),
                level: "info".to_string(),
            });

            let batch_size = self.config.processing.batch_size;
            let mut processed_in_file = 0;

            let mut stopped = false;

            for start in (0..file_info.row_count).step_by(batch_size) {
                let batch = seed_index.load_batch(
                    &PathBuf::from(&file_info.filepath),
                    start,
                    batch_size,
                )?;

                let mut tasks = Vec::new();
                for (name, rfc) in &batch {
                    let task = process_person(name, rfc, &self.config, &cache, &client, &rate_gate);
                    tasks.push(task);
                }

                let results = futures::future::join_all(tasks).await;
                for result in results {
                    match result.status.as_str() {
                        "Found" => found.push(result),
                        _ => not_found.push(result),
                    }
                    processed_in_file += 1;
                    processed_overall += 1;
                }

                cache.flush();

                let _ = progress_tx.send(crate::models::ProgressEvent {
                    processed: processed_overall,
                    total: total_rows,
                    found: found_overall + found.len(),
                    not_found: not_found_overall + not_found.len(),
                });

                let _ = log_tx.send(crate::models::LogEvent {
                    message: format!(
                        "Lote completado: {}/{} registros",
                        processed_in_file, file_info.row_count
                    ),
                    level: "info".to_string(),
                });

                if stop_requested.load(Ordering::Relaxed) {
                    let _ = log_tx.send(crate::models::LogEvent {
                        message: "Procesamiento detenido por el usuario.".to_string(),
                        level: "warn".to_string(),
                    });
                    stopped = true;
                    break;
                }

                let delay = self.config.rate_limit.inter_batch_delay;
                if delay > 0.0 {
                    tokio::time::sleep(std::time::Duration::from_secs_f64(delay)).await;
                }
            }

            let output_config = AppConfig {
                output: crate::models::OutputConfig {
                    dir: output_dir.to_string_lossy().to_string(),
                    found_suffix: self.config.output.found_suffix.clone(),
                    not_found_suffix: self.config.output.not_found_suffix.clone(),
                },
                filters: self.config.filters.clone(),
                ..self.config.clone()
            };
            let compactor = Compactor::new(&output_config);
            let summary = compactor.compact(&found, &not_found, &file_info.basename)?;

            found_overall += found.len();
            not_found_overall += not_found.len();

            let _ = log_tx.send(crate::models::LogEvent {
                message: format!(
                    "Completado {}: {} encontrados, {} no encontrados",
                    file_info.filename, summary.found_count, summary.not_found_count
                ),
                level: "info".to_string(),
            });

            if stopped {
                break;
            }
        }

        let _ = log_tx.send(crate::models::LogEvent {
            message: "Procesamiento completado.".to_string(),
            level: "info".to_string(),
        });

        Ok(())
    }

    fn resolve_path(&self, path: &str) -> PathBuf {
        let p = PathBuf::from(path);
        if p.is_absolute() {
            p
        } else {
            self.config_dir.join(path)
        }
    }
}
