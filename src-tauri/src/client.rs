use reqwest::Client;
use std::time::Duration;
use crate::models::AppConfig;

pub fn create_client(config: &AppConfig) -> Result<Client, String> {
    let client = Client::builder()
        .timeout(Duration::from_secs(config.api.timeout))
        .connect_timeout(Duration::from_secs(10))
        .default_headers(create_headers())
        .build()
        .map_err(|e| format!("Error creating HTTP client: {}", e))?;
    Ok(client)
}

pub fn create_headers() -> reqwest::header::HeaderMap {
    let mut headers = reqwest::header::HeaderMap::new();
    headers.insert(
        reqwest::header::CONTENT_TYPE,
        "application/json".parse().unwrap(),
    );
    headers.insert(
        reqwest::header::USER_AGENT,
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            .parse().unwrap(),
    );
    headers.insert(
        reqwest::header::ACCEPT,
        "application/json, text/plain, */*".parse().unwrap(),
    );
    headers.insert(
        reqwest::header::ACCEPT_LANGUAGE,
        "es-MX,es;q=0.9,en;q=0.8".parse().unwrap(),
    );
    headers.insert(
        reqwest::header::ORIGIN,
        "https://servicios.dkla8prod.buengobierno.gob.mx".parse().unwrap(),
    );
    headers.insert(
        reqwest::header::REFERER,
        "https://servicios.dkla8prod.buengobierno.gob.mx/declaranet/consulta-servidores-publicos/buscarsp".parse().unwrap(),
    );
    headers
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::default_config;

    #[test]
    fn test_create_client_succeeds() {
        let config = default_config();
        let client = create_client(&config);
        assert!(client.is_ok());
    }

    #[test]
    fn test_create_headers_has_required_keys() {
        let headers = create_headers();
        assert!(headers.contains_key(reqwest::header::CONTENT_TYPE));
        assert!(headers.contains_key(reqwest::header::USER_AGENT));
        assert!(headers.contains_key(reqwest::header::ACCEPT));
        assert!(headers.contains_key(reqwest::header::ORIGIN));
        assert!(headers.contains_key(reqwest::header::REFERER));
    }
}
