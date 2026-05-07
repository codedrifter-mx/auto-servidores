use crate::cache::ApiCache;
use crate::models::{AppConfig, PersonResult};
use reqwest::Client;
use serde_json::json;
use std::collections::HashMap;
use url::Url;

pub async fn process_person(
    name: &str,
    rfc: &str,
    config: &AppConfig,
    cache: &ApiCache,
    client: &Client,
    rate_gate: &crate::rate_limit::RateLimitGate,
) -> PersonResult {
    let mut result = PersonResult {
        name: name.to_string(),
        rfc: rfc.to_string(),
        status: "Not found".to_string(),
        comprobantes: None,
    };

    let search_params = json!({
        "busqueda": rfc,
        "collName": config.api.default_coll_name
    });

    let person_result = match cache.get(&config.api.endpoints.search, &search_params) {
        Some(cached) => cached,
        None => {
            let base = format!("{}{}", config.api.base_url, config.api.endpoints.search);
            let mut url = match Url::parse(&base) {
                Ok(u) => u,
                Err(e) => {
                    log::error!("Invalid search URL for {}: {}", name, e);
                    result.status = "Error".to_string();
                    return result;
                }
            };
            let url = url.query_pairs_mut()
                .append_pair("busqueda", rfc)
                .append_pair("collName", &config.api.default_coll_name)
                .finish()
                .to_string();
            let response = match post_with_retry(
                client,
                &url,
                rate_gate,
                config.api.max_retries,
                config.api.retry_base_delay,
            )
            .await
            {
                Ok(r) => r,
                Err(e) => {
                    log::error!("Error searching for {}: {}", name, e);
                    result.status = "Error".to_string();
                    return result;
                }
            };
            cache.set(&config.api.endpoints.search, &search_params, &response);
            response
        }
    };

    if person_result.get("estatus").is_none() || person_result.get("datos").is_none() {
        return result;
    }

    let datos = match person_result["datos"].as_array() {
        Some(d) if !d.is_empty() => d,
        _ => return result,
    };

    let person_data = &datos[0];
    let id_usr = match person_data.get("idUsrDecnet") {
        Some(id) => id.to_string().trim_matches('"').to_string(),
        None => return result,
    };

    if id_usr.is_empty() {
        return result;
    }

    let history_params = json!({
        "idUsrDecnet": id_usr,
        "collName": config.api.default_coll_name
    });

    let declaration_result = match cache.get(&config.api.endpoints.history, &history_params) {
        Some(cached) => cached,
        None => {
            let base = format!("{}{}", config.api.base_url, config.api.endpoints.history);
            let mut url = match Url::parse(&base) {
                Ok(u) => u,
                Err(e) => {
                    log::error!("Invalid history URL for {}: {}", name, e);
                    result.status = "Error".to_string();
                    return result;
                }
            };
            let url = url.query_pairs_mut()
                .append_pair("idUsrDecnet", &id_usr)
                .append_pair("collName", &config.api.default_coll_name)
                .finish()
                .to_string();
            let response = match post_with_retry(
                client,
                &url,
                rate_gate,
                config.api.max_retries,
                config.api.retry_base_delay,
            )
            .await
            {
                Ok(r) => r,
                Err(e) => {
                    log::error!("Error fetching history for {}: {}", name, e);
                    result.status = "Error".to_string();
                    return result;
                }
            };
            cache.set(&config.api.endpoints.history, &history_params, &response);
            response
        }
    };

    let mut comprobantes: HashMap<u32, String> = HashMap::new();
    let common = &config.filters.common_filters;

    if let Some(datos) = declaration_result.get("datos").and_then(|d| d.as_array()) {
        for declaration in datos {
            if let Some(year) = declaration.get("anio").and_then(|y| y.as_u64()) {
                let year_u32 = year as u32;
                if !config.filters.years_to_check.contains(&year_u32) {
                    continue;
                }
                let matches_tipo = common.tipoDeclaracion.is_empty()
                    || declaration
                        .get("tipoDeclaracion")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        == common.tipoDeclaracion;
                let matches_inst = common.institucionReceptora.is_empty()
                    || declaration
                        .get("institucionReceptora")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        == common.institucionReceptora;
                if matches_tipo && matches_inst {
                    if let Some(comp) = declaration.get("noComprobante").and_then(|v| v.as_str()) {
                        comprobantes.insert(year_u32, comp.to_string());
                    }
                    result.status = "Found".to_string();
                }
            }
        }
    }

    if !comprobantes.is_empty() {
        result.comprobantes = Some(comprobantes);
    }
    result
}

async fn post_with_retry(
    client: &Client,
    url: &str,
    rate_gate: &crate::rate_limit::RateLimitGate,
    max_retries: u32,
    base_delay: f64,
) -> Result<serde_json::Value, String> {
    let mut last_status: Option<u16> = None;
    for attempt in 0..=max_retries {
        let _permit = rate_gate.acquire().await;
        match client.post(url).send().await {
            Ok(resp) => {
                last_status = Some(resp.status().as_u16());
                if resp.status().is_success() {
                    rate_gate.report_success().await;
                    let body = resp
                        .json::<serde_json::Value>()
                        .await
                        .map_err(|e| format!("Error parsing response: {}", e))?;
                    return Ok(body);
                }
                let status = resp.status().as_u16();
                if [429, 502, 503, 504].contains(&status) {
                    let cooldown = rate_gate.report_429().await;
                    log::warn!(
                        "HTTP {} on {}, cooldown {:.1}s (attempt {}/{})",
                        status,
                        &url[..80.min(url.len())],
                        cooldown,
                        attempt + 1,
                        max_retries
                    );
                    if attempt < max_retries {
                        let delay = base_delay * 2_f64.powi(attempt as i32)
                            * (1.0 + rand::random::<f64>() * 0.5);
                        tokio::time::sleep(std::time::Duration::from_secs_f64(delay)).await;
                        continue;
                    }
                }
                log::warn!("HTTP {} on {}", status, &url[..80.min(url.len())]);
            }
            Err(e) => {
                log::warn!("Network error on attempt {}: {}", attempt + 1, e);
                if attempt < max_retries {
                    let delay = base_delay * 2_f64.powi(attempt as i32)
                        * (1.0 + rand::random::<f64>() * 0.5);
                    tokio::time::sleep(std::time::Duration::from_secs_f64(delay)).await;
                    continue;
                }
            }
        }
    }
    Err(format!(
        "Request failed after {} retries, last status: {:?}",
        max_retries, last_status
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cache::ApiCache;
    use crate::config;
    use crate::rate_limit::RateLimitGate;
    use serde_json::json;

    fn make_test_config(mock_url: &str) -> AppConfig {
        let mut config = config::default_config();
        config.api.base_url = mock_url.to_string();
        config.api.endpoints.search = "/declaranet/consulta-servidores-publicos/buscarsp".to_string();
        config.api.endpoints.history = "/declaranet/consulta-servidores-publicos/historico".to_string();
        config.api.timeout = 5;
        config.api.max_retries = 2;
        config.api.retry_base_delay = 0.01;
        config.rate_limit.min_interval = 0.0;
        config.rate_limit.cooldown_base = 0.01;
        config.rate_limit.cooldown_max = 0.1;
        config.rate_limit.max_concurrent = 50;
        config.filters.years_to_check = vec![2025, 2026];
        config.filters.common_filters.tipoDeclaracion = "MODIFICACION".to_string();
        config.filters.common_filters.institucionReceptora = "INSTITUTO MEXICANO DEL SEGURO SOCIAL".to_string();
        config
    }

    fn make_test_cache() -> ApiCache {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_cache.db");
        ApiCache::new(&path, 3600, false).unwrap()
    }

    fn make_rate_gate() -> RateLimitGate {
        RateLimitGate::new(50, 0.0, 0.01, 0.1)
    }

    #[tokio::test]
    async fn test_process_person_found() {
        let mut server = mockito::Server::new_async().await;
        let search_body = json!({
            "estatus": true,
            "datos": [{"idUsrDecnet": "12345", "nombre": "JUAN PEREZ", "rfc": "XEXX010101000"}]
        });
        let history_body = json!({
            "datos": [{
                "anio": 2025,
                "tipoDeclaracion": "MODIFICACION",
                "institucionReceptora": "INSTITUTO MEXICANO DEL SEGURO SOCIAL",
                "noComprobante": "COMP001"
            }]
        });
        let search_mock = server.mock("POST", mockito::Matcher::Regex(r"^/declaranet/consulta-servidores-publicos/buscarsp.*".to_string()))
            .with_status(200)
            .with_body(search_body.to_string())
            .expect(1)
            .create();
        let history_mock = server.mock("POST", mockito::Matcher::Regex(r"^/declaranet/consulta-servidores-publicos/historico.*".to_string()))
            .with_status(200)
            .with_body(history_body.to_string())
            .expect(1)
            .create();
        let config = make_test_config(&server.url());
        let client = crate::client::create_client(&config).unwrap();
        let cache = make_test_cache();
        let rate_gate = make_rate_gate();
        let result = process_person("JUAN PEREZ", "XEXX010101000", &config, &cache, &client, &rate_gate).await;
        search_mock.assert();
        history_mock.assert();
        assert_eq!(result.status, "Found");
        assert!(result.comprobantes.is_some());
        assert_eq!(result.comprobantes.unwrap().get(&2025), Some(&"COMP001".to_string()));
    }

    #[tokio::test]
    async fn test_process_person_not_found_empty_datos() {
        let mut server = mockito::Server::new_async().await;
        let search_body = json!({"estatus": true, "datos": []});
        server.mock("POST", mockito::Matcher::Any)
            .with_status(200)
            .with_body(search_body.to_string())
            .expect(1)
            .create();
        let config = make_test_config(&server.url());
        let client = crate::client::create_client(&config).unwrap();
        let cache = make_test_cache();
        let rate_gate = make_rate_gate();
        let result = process_person("NOBODY", "XEXX990101000", &config, &cache, &client, &rate_gate).await;
        assert_eq!(result.status, "Not found");
    }

    #[tokio::test]
    async fn test_process_person_no_estatus() {
        let mut server = mockito::Server::new_async().await;
        let search_body = json!({"someField": "value"});
        server.mock("POST", mockito::Matcher::Any)
            .with_status(200)
            .with_body(search_body.to_string())
            .expect(1)
            .create();
        let config = make_test_config(&server.url());
        let client = crate::client::create_client(&config).unwrap();
        let cache = make_test_cache();
        let rate_gate = make_rate_gate();
        let result = process_person("NOBODY", "XEXX990101000", &config, &cache, &client, &rate_gate).await;
        assert_eq!(result.status, "Not found");
    }

    #[tokio::test]
    async fn test_process_person_api_error() {
        let mut server = mockito::Server::new_async().await;
        server.mock("POST", mockito::Matcher::Any)
            .with_status(500)
            .expect_at_least(1)
            .create();
        let config = make_test_config(&server.url());
        let client = crate::client::create_client(&config).unwrap();
        let cache = make_test_cache();
        let rate_gate = make_rate_gate();
        let result = process_person("ERROR", "XEXX990101000", &config, &cache, &client, &rate_gate).await;
        assert_eq!(result.status, "Error");
    }

    #[tokio::test]
    async fn test_process_person_filters_year() {
        let mut server = mockito::Server::new_async().await;
        let search_body = json!({
            "estatus": true,
            "datos": [{"idUsrDecnet": "999", "nombre": "TEST", "rfc": "XEXX010101000"}]
        });
        let history_body = json!({
            "datos": [{
                "anio": 2023,
                "tipoDeclaracion": "MODIFICACION",
                "institucionReceptora": "INSTITUTO MEXICANO DEL SEGURO SOCIAL",
                "noComprobante": "OLD"
            }]
        });
        server.mock("POST", mockito::Matcher::Regex(r"^/declaranet/consulta-servidores-publicos/buscarsp.*".to_string()))
            .with_status(200)
            .with_body(search_body.to_string())
            .expect(1)
            .create();
        server.mock("POST", mockito::Matcher::Regex(r"^/declaranet/consulta-servidores-publicos/historico.*".to_string()))
            .with_status(200)
            .with_body(history_body.to_string())
            .expect(1)
            .create();
        let config = make_test_config(&server.url());
        let client = crate::client::create_client(&config).unwrap();
        let cache = make_test_cache();
        let rate_gate = make_rate_gate();
        let result = process_person("TEST", "XEXX010101000", &config, &cache, &client, &rate_gate).await;
        assert_eq!(result.status, "Not found");
    }

    #[tokio::test]
    async fn test_process_person_filters_tipo() {
        let mut server = mockito::Server::new_async().await;
        let search_body = json!({
            "estatus": true,
            "datos": [{"idUsrDecnet": "999", "nombre": "TEST", "rfc": "XEXX010101000"}]
        });
        let history_body = json!({
            "datos": [{
                "anio": 2025,
                "tipoDeclaracion": "INICIAL",
                "institucionReceptora": "INSTITUTO MEXICANO DEL SEGURO SOCIAL",
                "noComprobante": "WRONG"
            }]
        });
        server.mock("POST", mockito::Matcher::Regex(r"^/declaranet/consulta-servidores-publicos/buscarsp.*".to_string()))
            .with_status(200)
            .with_body(search_body.to_string())
            .expect(1)
            .create();
        server.mock("POST", mockito::Matcher::Regex(r"^/declaranet/consulta-servidores-publicos/historico.*".to_string()))
            .with_status(200)
            .with_body(history_body.to_string())
            .expect(1)
            .create();
        let config = make_test_config(&server.url());
        let client = crate::client::create_client(&config).unwrap();
        let cache = make_test_cache();
        let rate_gate = make_rate_gate();
        let result = process_person("TEST", "XEXX010101000", &config, &cache, &client, &rate_gate).await;
        assert_eq!(result.status, "Not found");
    }
}
