use rusqlite::{params, Connection};
use serde_json;
use sha2::{Sha256, Digest};
use std::path::Path;
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

pub struct ApiCache {
    conn: Mutex<Connection>,
    ttl_seconds: u64,
    enabled: bool,
}

impl ApiCache {
    pub fn new(db_path: &Path, ttl_seconds: u64, enabled: bool) -> Result<Self, String> {
        if !enabled {
            let conn = Connection::open_in_memory()
                .map_err(|e| format!("Error creating in-memory DB: {}", e))?;
            return Ok(Self {
                conn: Mutex::new(conn),
                ttl_seconds,
                enabled: false,
            });
        }
        if let Some(parent) = db_path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|e| format!("Error creating cache directory: {}", e))?;
        }
        let conn = Connection::open(db_path)
            .map_err(|e| format!("Error opening cache DB: {}", e))?;
        conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")
            .map_err(|e| format!("Error setting PRAGMA: {}", e))?;
        conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                response TEXT NOT NULL,
                timestamp REAL NOT NULL
            )",
            [],
        )
        .map_err(|e| format!("Error creating cache table: {}", e))?;
        Ok(Self {
            conn: Mutex::new(conn),
            ttl_seconds,
            enabled: true,
        })
    }

    fn make_key(&self, endpoint: &str, params: &serde_json::Value) -> String {
        let mut hasher = Sha256::new();
        let mut sorted = params.clone();
        if let serde_json::Value::Object(map) = &mut sorted {
            let mut sorted_map = serde_json::Map::new();
            let mut keys: Vec<_> = map.keys().cloned().collect();
            keys.sort();
            for k in keys {
                if let Some(v) = map.remove(&k) {
                    sorted_map.insert(k, v);
                }
            }
            *map = sorted_map;
        }
        hasher.update(endpoint.as_bytes());
        hasher.update(sorted.to_string().as_bytes());
        format!("{:x}", hasher.finalize())
    }

    pub fn get(
        &self,
        endpoint: &str,
        params: &serde_json::Value,
    ) -> Option<serde_json::Value> {
        if !self.enabled {
            return None;
        }
        let key = self.make_key(endpoint, params);
        let conn = self.conn.lock().ok()?;
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .ok()?
            .as_secs() as f64;
        let mut stmt = conn
            .prepare("SELECT response, timestamp FROM cache WHERE key = ?1")
            .ok()?;
        let result = stmt
            .query_row(params![key], |row| {
                let response: String = row.get(0)?;
                let timestamp: f64 = row.get(1)?;
                Ok((response, timestamp))
            })
            .ok()?;
        if (now - result.1) < self.ttl_seconds as f64 {
            serde_json::from_str(&result.0).ok()
        } else {
            None
        }
    }

    pub fn set(
        &self,
        endpoint: &str,
        params: &serde_json::Value,
        response: &serde_json::Value,
    ) {
        if !self.enabled {
            return;
        }
        let key = self.make_key(endpoint, params);
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs() as f64;
        let response_str = serde_json::to_string(response).unwrap_or_default();
        if let Ok(conn) = self.conn.lock() {
            let _ = conn.execute(
                "INSERT OR REPLACE INTO cache (key, response, timestamp) VALUES (?1, ?2, ?3)",
                params![key, response_str, now],
            );
        }
    }

    pub fn flush(&self) {
        if !self.enabled {
            return;
        }
        if let Ok(conn) = self.conn.lock() {
            let _ = conn.execute_batch(""); 
        }
    }

    #[allow(dead_code)]
    pub fn close(self) {
        if self.enabled {
            if let Ok(conn) = self.conn.into_inner() {
                let _ = conn.close();
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_cache_set_and_get() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.db");
        let cache = ApiCache::new(&path, 3600, true).unwrap();
        let params = json!({"busqueda": "XEXX010101000", "collName": "100"});
        let response = json!({"estatus": true, "datos": []});
        cache.set("/search", &params, &response);
        let result = cache.get("/search", &params);
        assert!(result.is_some());
        assert_eq!(result.unwrap()["estatus"], true);
    }

    #[test]
    fn test_cache_miss() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.db");
        let cache = ApiCache::new(&path, 3600, true).unwrap();
        let result = cache.get("/search", &json!({"busqueda": "nonexistent"}));
        assert!(result.is_none());
    }

    #[test]
    fn test_cache_disabled() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.db");
        let cache = ApiCache::new(&path, 3600, false).unwrap();
        let params = json!({"key": "value"});
        cache.set("/ep", &params, &json!({"data": 1}));
        let result = cache.get("/ep", &params);
        assert!(result.is_none());
    }

    #[test]
    fn test_cache_ttl_expiry() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.db");
        let cache = ApiCache::new(&path, 0, true).unwrap();
        let params = json!({"key": "value"});
        cache.set("/ep", &params, &json!({"data": 1}));
        let result = cache.get("/ep", &params);
        assert!(result.is_none());
    }
}
