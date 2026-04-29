# Auto-Servidores: Guia Tecnica Completa

> Esta guia explica como funciona la aplicacion por dentro: la arquitectura Rust, los comandos disponibles, el flujo de datos, y como modificar cada parte.

---

## Tabla de Contenidos

1. [Arquitectura General](#arquitectura-general)
2. [Estructura de Archivos](#estructura-de-archivos)
3. [Modulos del Backend (Rust)](#modulos-del-backend-rust)
4. [Comandos Tauri Disponibles](#comandos-tauri-disponibles)
5. [Eventos del Backend al Frontend](#eventos-del-backend-al-frontend)
6. [Flujo de Datos: De Excel a Excel](#flujo-de-datos-de-excel-a-excel)
7. [Comandos de Desarrollo](#comandos-de-desarrollo)
8. [Comandos de Build](#comandos-de-build)
9. [Modificaciones Comunes](#modificaciones-comunes)

---

## Arquitectura General

```
+--------------------------------------------------+
|  Frontend (HTML/CSS/JS)                          |
|  - src/index.html, src/styles.css, src/app.js    |
|  - Corre dentro de WebView2 (Windows)            |
+--------------------------------------------------+
                    | invoke / events
                    v
+--------------------------------------------------+
|  Tauri Bridge                                    |
|  - Comandos: funciones Rust expuestas al JS      |
|  - Eventos: canal del Rust al JS en tiempo real  |
+--------------------------------------------------+
                    | llama modulos
                    v
+--------------------------------------------------+
|  Backend (Rust)                                  |
|  - config, cache, rate_limit, client             |
|  - seed_index, worker, compactor, orchestrator   |
+--------------------------------------------------+
                    | HTTP requests
                    v
+--------------------------------------------------+
|  API DeclaraNet (servidor externo)               |
+--------------------------------------------------+
```

La app es un **cliente HTTP masivo con GUI**. Lee archivos Excel, consulta un API gubernamental, y escribe resultados en Excel.

**Tecnologias clave:**
- **Tauri 2.0**: Framework desktop que combina un frontend web con un backend Rust
- **Tokio**: Runtime async de Rust (maneja todas las peticiones HTTP concurrentes)
- **Reqwest**: Cliente HTTP (equivalente a aiohttp en Python)
- **Rusqlite**: Base de datos SQLite embebida (cache de respuestas del API)
- **Calamine**: Lectura de Excel sin dependencias pesadas (reemplaza a pandas)
- **Rust_xlsxwriter**: Escritura de Excel (reemplaza a openpyxl)

---

## Estructura de Archivos

```
auto-servidores/
|
|-- src/                          # Frontend (HTML/CSS/JS)
|   |-- index.html               # Estructura de la UI
|   |-- styles.css               # Estilos dark theme
|   |-- app.js                   # Logica del frontend
|
|-- src-tauri/                   # Backend Rust + config de Tauri
|   |-- src/
|   |   |-- main.rs             # Punto de entrada de la app
|   |   |-- lib.rs              # Comandos Tauri y estado global
|   |   |-- models.rs           # Structs compartidos (Config, Resultados, etc.)
|   |   |-- config.rs           # Carga/guarda config.toml
|   |   |-- cache.rs            # Cache SQLite con TTL
|   |   |-- rate_limit.rs       # Limitador de tasa async
|   |   |-- client.rs           # Cliente HTTP con headers
|   |   |-- seed_index.rs       # Lectura de archivos Excel
|   |   |-- worker.rs           # Procesa una persona (busqueda + historial)
|   |   |-- compactor.rs        # Escribe archivos Excel de salida
|   |   |-- orchestrator.rs     # Orquesta el procesamiento por lotes
|   |   |-- system_info.rs      # Detecta CPU/RAM del sistema
|   |-- Cargo.toml              # Dependencias Rust
|   |-- tauri.conf.json         # Configuracion de ventana y bundle
|   |-- build.rs                # Script de build de Tauri
|   |-- capabilities/           # Permisos de la app
|
|-- config.toml                  # Configuracion por defecto (empaquetada)
|-- package.json                 # Dependencias Node/Vite
|-- vite.config.js               # Configuracion del servidor de desarrollo
|-- docs/                        # Documentacion
|   |-- RELEASE_TEMPLATE.md     # Plantilla para releases
|   |-- ARCHITECTURE.md         # Esta guia
|   |-- DELIVERY.md             # Guia de entrega
|
|-- seed/                        # Archivos Excel de entrada (no trackeados)
|-- output/                      # Archivos Excel de salida (no trackeados)
|-- .cache/                      # Cache SQLite (no trackeado)
```

---

## Modulos del Backend (Rust)

### 1. `models.rs` — Tipos de Datos

Define todos los structs que se usan en toda la app. Estos son **serializables** (se convierten a JSON automaticamente para comunicarse con el frontend).

```rust
pub struct AppConfig {
    pub api: ApiConfig,
    pub cache: CacheConfig,
    pub rate_limit: RateLimitConfig,
    pub filters: FiltersConfig,
    pub processing: ProcessingConfig,
    pub output: OutputConfig,
}

pub struct PersonResult {
    pub name: String,
    pub rfc: String,
    pub status: String,           // "Found", "Not found", "Error"
    pub comprobantes: Option<HashMap<u32, String>>,  // ano -> noComprobante
}

pub struct SeedFileInfo {
    pub filename: String,
    pub filepath: String,
    pub basename: String,
    pub row_count: usize,
}

pub struct ProgressEvent {
    pub processed: usize,
    pub total: usize,
}

pub struct LogEvent {
    pub message: String,
    pub level: String,            // "info", "warn", "error"
}
```

**Para modificar:** Si necesitas agregar un nuevo campo a la config o a los resultados, anadelo aqui y en `config.toml`.

---

### 2. `config.rs` — Configuracion TOML

**Funciones publicas:**

```rust
pub fn load_config(path: &Path) -> Result<AppConfig, String>
// Lee un archivo TOML y lo convierte a AppConfig

pub fn save_config(config: &AppConfig, path: &Path) -> Result<(), String>
// Escribe AppConfig a un archivo TOML (formato pretty)

pub fn default_config() -> AppConfig
// Devuelve la configuracion por defecto (hardcodeada)
```

**Ejemplo de uso:**
```rust
let config = config::load_config(Path::new("config.toml"))?;
println!("URL base: {}", config.api.base_url);
```

**Para modificar:** Si cambias el formato de `config.toml`, actualiza `default_config()` para que coincida.

---

### 3. `cache.rs` — Cache SQLite

Almacena respuestas del API en SQLite para evitar consultas repetidas.

**Clave publica:**

```rust
pub struct ApiCache {
    conn: Mutex<Connection>,
    ttl_seconds: u64,
    enabled: bool,
}

impl ApiCache {
    pub fn new(db_path: &Path, ttl_seconds: u64, enabled: bool) -> Result<Self, String>
    // Crea/abre la base de datos, inicializa tabla WAL

    pub fn get(&self, endpoint: &str, params: &serde_json::Value) -> Option<serde_json::Value>
    // Busca en cache. Si el TTL expiro, devuelve None.

    pub fn set(&self, endpoint: &str, params: &serde_json::Value, response: &serde_json::Value)
    // Guarda respuesta en cache (sobrescribe si existe)

    pub fn flush(&self)
    // Fuerza escritura a disco (SQLite ya lo hace, esto es noop seguro)
}
```

**Como funciona la clave:** Se genera un hash SHA-256 de `endpoint + JSON(params ordenados alfabeticamente)`. Esto asegura que la misma busqueda siempre genere la misma clave.

**Para modificar:** Cambia `ttl_seconds` en `config.toml` para ajustar cuanto tiempo duran las respuestas en cache.

---

### 4. `rate_limit.rs` — Limitador de Tasa

Evita que el API te bloquee por hacer demasiadas peticiones.

**Clave publica:**

```rust
pub struct RateLimitGate {
    semaphore: Arc<Semaphore>,      // Limita concurrencia
    min_interval: f64,              // Segundos min entre requests
    cooldown_until: Mutex<Instant>, // Hasta cuando esperar tras un 429
    cooldown_base: f64,             // Segundos base de cooldown
    cooldown_max: f64,              // Segundos max de cooldown
    consecutive_429s: Mutex<u32>,   // Contador de 429s consecutivos
}

impl RateLimitGate {
    pub fn new(max_concurrent: usize, min_interval: f64, cooldown_base: f64, cooldown_max: f64) -> Self

    pub async fn acquire(&self) -> RateLimitPermit
    // Adquiere un slot. Espera si hay cooldown activo o si no ha pasado min_interval.

    pub async fn report_429(&self) -> f64
    // Reporta un HTTP 429. Activa cooldown exponencial. Devuelve segundos de espera.

    pub async fn report_success(&self)
    // Reporta exito. Resetea el contador de 429s.
}
```

**Importante:** El `min_interval` se calcula **sin mantener el lock durante el sleep** (a diferencia del codigo Python original que tenia este bug). Esto permite verdadera concurrencia.

**Para modificar:** Ajusta `rate_limit` en `config.toml` si el API cambia sus limites.

---

### 5. `client.rs` — Cliente HTTP

Crea un cliente `reqwest` con los headers necesarios para que el API acepte las peticiones.

**Funciones publicas:**

```rust
pub fn create_client(config: &AppConfig) -> Result<Client, String>
// Crea un Client con timeout, connect_timeout, y headers de produccion

pub fn create_headers() -> reqwest::header::HeaderMap
// Devuelve headers: User-Agent, Accept, Origin, Referer, etc.
```

**Para modificar:** Si el API cambia sus headers requeridos, actualiza `create_headers()`.

---

### 6. `seed_index.rs` — Indice de Archivos Excel

Lee archivos `.xlsx` del directorio `seed/` y los expone en lotes.

**Clave publica:**

```rust
pub struct SeedIndex {
    seed_dir: PathBuf,
    index: Vec<SeedFileInfo>,
    cache: HashMap<PathBuf, Vec<Vec<String>>>,  // Cache de DataFrames en memoria
}

impl SeedIndex {
    pub fn new(seed_dir: &Path) -> Result<Self, String>
    // Escanea seed_dir y construye el indice de archivos .xlsx

    pub fn get_files(&self) -> &[SeedFileInfo]
    // Devuelve la lista de archivos con nombre, ruta, y conteo de filas

    pub fn load_batch(&mut self, filepath: &Path, start: usize, size: usize) -> Result<Vec<(String, String)>, String>
    // Lee un lote de filas. Cachea el archivo completo en memoria tras la primera lectura.
}
```

**Para modificar:** Si cambia el formato de los Excel (ej. hay encabezados), modifica `read_all_rows()` para saltar filas.

---

### 7. `worker.rs` — Procesamiento Individual

Procesa **una persona**: busca por RFC, obtiene historial, filtra por ano y tipo de declaracion.

**Funcion publica:**

```rust
pub async fn process_person(
    name: &str,
    rfc: &str,
    config: &AppConfig,
    cache: &ApiCache,
    client: &Client,
    rate_gate: &RateLimitGate,
) -> PersonResult
```

**Flujo interno:**
1. Busca en cache la llamada a `/buscarsp` para este RFC
2. Si no esta en cache, hace POST con retry
3. Si la persona existe, extrae `idUsrDecnet`
4. Busca en cache la llamada a `/historico` para ese ID
5. Si no esta en cache, hace POST con retry
6. Itera las declaraciones del historial, filtra por:
   - `anio` en `years_to_check`
   - `tipoDeclaracion` == `common_filters.tipoDeclaracion`
   - `institucionReceptora` == `common_filters.institucionReceptora`
7. Devuelve `PersonResult` con `Status: "Found"` si hay match, `"Not found"` si no, o `"Error"` si fallo la peticion

**Retry logic:** Si recibe HTTP 429/502/503/504, espera con backoff exponencial + jitter y reintenta hasta `max_retries`.

**Para modificar:** Si cambia la estructura de respuesta del API, ajusta los campos que se leen de los JSON.

---

### 8. `compactor.rs` — Escritura de Resultados

Escribe los archivos Excel de salida.

**Clave publica:**

```rust
pub struct Compactor<'a> {
    output_dir: &'a str,
    found_suffix: &'a str,
    not_found_suffix: &'a str,
    years: &'a [u32],
}

impl<'a> Compactor<'a> {
    pub fn new(config: &'a AppConfig) -> Self

    pub fn compact(&self, found: &[PersonResult], not_found: &[PersonResult], base_filename: &str) -> Result<CompactSummary, String>
    // Crea output_dir si no existe, escribe dos archivos Excel
}
```

**Estructura del Excel ENCONTRADOS:**
| Name | RFC | noComprobante_2025 | noComprobante_2026 |
|------|-----|--------------------|--------------------|
| JUAN PEREZ | XEXX... | COMP001 | COMP002 |

**Estructura del Excel NO_ENCONTRADOS:**
| Name | RFC |
|------|-----|
| MARIA LOPEZ | XEXX... |

**Para modificar:** Si necesitas mas columnas en el output, cambia `write_found()`.

---

### 9. `orchestrator.rs` — Orquestador Principal

Coordina todo el procesamiento: lee archivos, procesa por lotes, emite progreso.

**Clave publica:**

```rust
pub struct Orchestrator {
    config: AppConfig,
    config_dir: PathBuf,
}

impl Orchestrator {
    pub fn new(config: AppConfig, config_dir: PathBuf) -> Self

    pub async fn run(
        &self,
        progress_tx: mpsc::UnboundedSender<ProgressEvent>,
        log_tx: mpsc::UnboundedSender<LogEvent>,
    ) -> Result<(), String>
}
```

**Flujo interno:**
1. Inicializa cache, cliente HTTP, rate limiter, seed index
2. Por cada archivo en `seed/`:
   - Por cada lote de `batch_size` filas:
     - Crea tareas async para cada persona
     - Espera a que terminen con `futures::future::join_all()`
     - Clasifica resultados en `found` / `not_found`
     - Emite evento de progreso
     - Emite evento de log
     - Duerme `inter_batch_delay` segundos
   - Escribe archivos Excel de salida via `Compactor`
   - Emite log de resumen
3. Emite log de "Procesamiento completado"

**Para modificar:** Si quieres paralelismo entre archivos (en vez de secuencial), mueve el `for file_info` a dentro de `tokio::spawn`.

---

### 10. `system_info.rs` — Informacion del Sistema

Detecta CPU y RAM para la funcion de auto-configuracion.

```rust
pub fn get_system_info() -> SystemInfo
// Devuelve: cpu_cores, cpu_physical, ram_gb, os

pub fn recommend_settings() -> RecommendedSettings
// Devuelve: batch_size, max_workers basado en CPU/RAM
```

---

## Comandos Tauri Disponibles

Estos son las funciones Rust que el frontend puede llamar via JavaScript:

### `get_system_info()` → `SystemInfo`
Devuelve informacion del sistema operativo.

```javascript
const info = await invoke('get_system_info');
// { cpu_cores: 8, cpu_physical: 4, ram_gb: 16, os: "Windows 11" }
```

### `get_config()` → `AppConfig`
Devuelve la configuracion actual cargada.

```javascript
const config = await invoke('get_config');
```

### `save_config(new_config: AppConfig)` → `void`
Guarda la configuracion a `config.toml`.

```javascript
await invoke('save_config', { newConfig: config });
```

### `get_recommended_settings()` → `RecommendedSettings`
Devuelve valores recomendados basados en hardware.

```javascript
const rec = await invoke('get_recommended_settings');
// { batch_size: 25, max_workers: 8 }
```

### `get_seed_files()` → `Vec<SeedFileInfo>`
Lista los archivos Excel en `seed/`.

```javascript
const files = await invoke('get_seed_files');
// [{ filename: "datos.xlsx", filepath: "...", basename: "datos", row_count: 150 }]
```

### `add_seed_file(source_path: String)` → `String`
Copia un archivo al directorio `seed/`.

```javascript
const newPath = await invoke('add_seed_file', { sourcePath: "C:/Users/.../datos.xlsx" });
```

### `remove_seed_file(filename: String)` → `void`
Elimina un archivo del directorio `seed/`.

```javascript
await invoke('remove_seed_file', { filename: "datos.xlsx" });
```

### `start_processing()` → `String`
Inicia el procesamiento en un task async de fondo.

```javascript
await invoke('start_processing');
// Devuelve "started" inmediatamente (el procesamiento sigue en background)
```

---

## Eventos del Backend al Frontend

El backend envia eventos en tiempo real al frontend durante el procesamiento.

### Evento: `progress`
Payload: `ProgressEvent { processed: usize, total: usize }`

```javascript
import { listen } from '@tauri-apps/api/event';

listen('progress', (event) => {
    const { processed, total } = event.payload;
    const percent = (processed / total) * 100;
    progressBar.value = percent;
});
```

### Evento: `log`
Payload: `LogEvent { message: String, level: String }`

```javascript
listen('log', (event) => {
    const { message, level } = event.payload;
    console.log(`[${level}] ${message}`);
    // Ejemplos:
    // [info] Iniciando procesamiento de datos
    // [info] Procesando: datos.xlsx (150 filas)
    // [info] Lote completado: 25/150 registros
    // [info] Completado datos.xlsx: 10 encontrados, 140 no encontrados
    // [info] Procesamiento completado.
});
```

---

## Flujo de Datos: De Excel a Excel

```
seed/datos.xlsx
    |
    v
[seed_index.rs] Lee filas del Excel
    |
    v
[orchestrator.rs] Agrupa en lotes de batch_size
    |
    v
[worker.rs] Por cada persona:
    - Busca RFC en API (o cache)
    - Obtiene historial (o cache)
    - Filtra por ano e institucion
    |
    v
[orchestrator.rs] Acumula found[] y not_found[]
    |
    v
[compactor.rs] Escribe archivos Excel
    |
    v
output/datos_ENCONTRADOS.xlsx
output/datos_NO_ENCONTRADOS.xlsx
```

---

## Comandos de Desarrollo

### Requisitos previos
- [Rust](https://rustup.rs/) (instalado automaticamente via `winget install Rustlang.Rustup`)
- [Node.js](https://nodejs.org/) v22+

### Instalar dependencias
```bash
npm install
```

### Ejecutar en modo desarrollo
```bash
npm run tauri dev
```
Abre una ventana con la app. El frontend se recarga automaticamente al cambiar archivos en `src/`. El backend se recompila al cambiar archivos en `src-tauri/src/`.

### Ejecutar solo tests de Rust
```bash
cd src-tauri
cargo test --verbose
```

### Ejecutar solo el build de Rust (sin frontend)
```bash
cd src-tauri
cargo check        # Compilacion rapida (sin binario)
cargo build        # Build debug
cargo build --release  # Build optimizado
```

### Ejecutar solo el build del frontend
```bash
npm run build
```
Genera archivos estaticos en `dist/`.

---

## Comandos de Build

### Build de produccion completo (instalador .exe)
```bash
npm run tauri build
```

Esto genera:
- `src-tauri/target/release/auto-servidores.exe` — Ejecutable portable
- `src-tauri/target/release/bundle/nsis/auto-servidores_2.0.0_x64-setup.exe` — Instalador NSIS

### Build de debug (mas rapido, para pruebas)
```bash
npm run tauri build -- --debug
```

### Ver tamano del ejecutable
```bash
ls -la src-tauri/target/release/bundle/nsis/
```

---

## Modificaciones Comunes

### Cambiar la URL del API
Edita `config.toml` (o usa la pestana Configuracion en la UI):
```toml
[api]
base_url = "https://nueva-url.gob.mx"
```

### Agregar un nuevo ano a verificar
Edita `config.toml`:
```toml
[filters]
years_to_check = [2025, 2026, 2027]
```

### Cambiar los filtros de declaracion
Edita `config.toml`:
```toml
[filters.common_filters]
tipoDeclaracion = "MODIFICACION"
institucionReceptora = "OTRA INSTITUCION"
```

### Cambiar el tamano maximo del instalador
No aplica — el tamano es funcion del codigo Rust compilado. No hay runtime ni interprete embebido.

### Agregar una nueva columna al Excel de salida
1. Modifica `PersonResult` en `models.rs` para incluir el nuevo campo
2. Modifica `worker.rs` para extraer el campo del JSON del API
3. Modifica `compactor.rs` `write_found()` para escribir la nueva columna

### Cambiar el numero de reintentos
Edita `config.toml`:
```toml
[api]
max_retries = 10
retry_base_delay = 3.0
```

### Agregar un nuevo comando Tauri
1. Escribe la funcion en `lib.rs` con `#[tauri::command]`
2. Agregala a la lista en `.invoke_handler()`
3. Llamala desde el frontend con `invoke('nombre_comando', { args })`

### Cambiar el tema de colores
Edita las variables CSS en `src/styles.css` bajo `:root`.

---

## Dependencias Clave (Cargo.toml)

| Crate | Proposito |
|-------|-----------|
| `tauri` | Framework desktop |
| `tokio` | Runtime async |
| `reqwest` | Cliente HTTP |
| `rusqlite` | SQLite embebido |
| `calamine` | Lectura Excel |
| `rust_xlsxwriter` | Escritura Excel |
| `serde` + `serde_json` | Serializacion JSON |
| `toml` | Parsing TOML |
| `sha2` | Hashing para claves de cache |
| `sysinfo` | Deteccion de hardware |
| `futures` | `join_all` para esperar tareas async |

---

## Glossary

- **Tauri**: Framework que crea apps desktop usando un frontend web y un backend Rust
- **WebView2**: Motor de renderizado web de Windows (basado en Edge/Chromium)
- **Tokio**: Runtime async de Rust, equivalente a `asyncio` de Python
- **WAL**: Write-Ahead Logging, modo de SQLite que permite lecturas concurrentes
- **TTL**: Time To Live, tiempo de vida de una entrada en cache
- **Rate Limiting**: Tecnica para limitar la frecuencia de peticiones a un API
- **Backoff Exponencial**: Estrategia de retry donde el tiempo de espera se duplica tras cada fallo
- **NSIS**: Nullsoft Scriptable Install System, generador de instaladores para Windows
