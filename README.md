# Auto-Servidores

Aplicación de escritorio para consulta masiva de declaraciones patrimoniales de servidores públicos mexicanos a través de la API de DeclaraNet, con caché integrado, control de tasa y generación de reportes en Excel.

> **English:** Desktop app for bulk querying Mexican public servants' asset declarations via the DeclaraNet API, with built-in caching, rate limiting, and Excel reporting.

Construida con Tauri 2.0 (Rust) y web frontend servido por Vite.

![Captura de pantalla](docs/screenshot.png)

## Características

- Procesamiento masivo de RFCs desde archivos Excel (`.xlsx`)
- Búsqueda automática en DeclaraNet: búsqueda por RFC + historial por `idUsrDecnet`
- Filtros configurables: años, tipo de declaración (` MODIFICACION`) e institución receptora
- Caché SQLite con SHA256 y TTL que comparten todos los trabajadores, evitando llamadas duplicadas al API
- Rate limiting adaptativo con_semaphore, intervalo mínimo y cooldown exponencial al recibir HTTP 429
- Progreso en tiempo real y log de eventos vía Tauri events
- Detención graceful del procesamiento con prevención de cierre de ventana
- Detección de CPU/RAM del sistema con recomendaciones de configuración automática
- Interfaz de configuración avanzada desde la aplicación
- Selector de archivos con diálogo nativo del sistema
- Pipeline de CI/CD con GitHub Actions para generar instalador NSIS automáticamente

## Requisitos

- **Windows 10/11**
- No se requiere Python ni dependencias adicionales (aplicación nativa)

### Desarrollo

- [Rust](https://rustup.rs/) (edition 2021)
- [Node.js](https://nodejs.org/) v22+
- [Tauri CLI](https://v2.tauri.app/) (`npm install` lo instala como dependencia)

## Instalación

1. Descarga el instalador `.exe` más reciente desde la pestaña [Releases](https://github.com/codedrifter-mx/auto-servidores/releases)
2. Ejecuta el instalador
3. La aplicación se instalará y podrás ejecutarla desde el menú Inicio o el acceso directo en el escritorio

## Uso

1. **Agrega archivos de origen**: Haz clic en "Agregar Archivo" para seleccionar tus archivos Excel (`.xlsx`) mediante el diálogo del sistema
2. **Configura parámetros**: Ajusta el tamaño de lote y trabajadores máximos con los sliders
3. **Inicia el procesamiento**: Haz clic en "Iniciar Procesamiento"
4. **Detén si es necesario**: El botón cambia a "Detener" durante el procesamiento; la ventana no se cierra mientras haya tareas en curso
5. **Revisa resultados**: Los archivos de salida se generarán en la carpeta `output/`

## Formato de archivos de origen

Coloca tus archivos Excel (`.xlsx`) dentro de la carpeta `seed/`, o agrégatelos desde la interfaz.

**No deben tener fila de encabezado.** La primera columna debe contener los nombres y la segunda columna los RFCs.

| A | B |
|---|---|
| JUAN PEREZ GARCIA | BEGX123456X01 |
| MARIA LOPEZ HDEZ | BEGX654321X02 |

## Configuración

Todos los parámetros son configurables desde `config.toml` y la pestaña "Configuración Avanzada" de la aplicación:

### API

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `api.base_url` | URL base del servicio DeclaraNet | `https://servicios.dkla8prod.buengobierno.gob.mx` |
| `api.default_coll_name` | ID de colección para las búsquedas | `100` |
| `api.timeout` | Timeout por request en segundos | `60` |
| `api.max_retries` | Reintentos máximos por request | `5` |
| `api.retry_base_delay` | Base de espera exponencial entre reintentos (seg) | `2.0` |
| `api.endpoints.search` | Endpoint de búsqueda de servidor público | `/declaranet/consulta-servidores-publicos/buscarsp` |
| `api.endpoints.history` | Endpoint de historial de declaraciones | `/declaranet/consulta-servidores-publicos/historico` |

### Caché

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `cache.enabled` | Habilitar/deshabilitar caché | `true` |
| `cache.db_path` | Ruta al archivo SQLite | `.cache/api_cache.db` |
| `cache.ttl_seconds` | Tiempo de vida de las respuestas en caché (seg) | `3600` |

Las respuestas del API se almacenan en SQLite (.cache/api_cache.db) con TTL configurable. La clave de caché es un hash SHA256 del endpoint + parámetros ordenados, y se usa en modo WAL para mayor concurrencia. Todos los trabajadores comparten el mismo caché, por lo que si un RFC ya fue consultado por otro lote o ejecución anterior, se reutiliza la respuesta sin llamar al API de nuevo. Esto acelera re-ejecuciones y reduce la carga sobre el servidor.

### Rate Limit

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `rate_limit.max_concurrent` | Conexiones simultáneas máximas (semaphore) | `10` |
| `rate_limit.min_interval` | Intervalo mínimo entre requests (seg) | `0.15` |
| `rate_limit.cooldown_base` | Backoff base al recibir 429 (seg) | `5.0` |
| `rate_limit.cooldown_max` | Backoff máximo al recibir 429 (seg) | `60.0` |
| `rate_limit.inter_batch_delay` | Pausa entre lotes consecutivos (seg) | `1.5` |

### Filtros

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `filters.years_to_check` | Años de declaraciones a verificar | `[2025, 2026]` |
| `filters.common_filters.tipoDeclaracion` | Tipo de declaración a buscar | `MODIFICACION` |
| `filters.common_filters.institucionReceptora` | Institución receptora a filtrar | `INSTITUTO MEXICANO DEL SEGURO SOCIAL` |

### Procesamiento

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `processing.batch_size` | Tamaño de lote para leer del Excel | `100` |
| `processing.max_workers` | Tareas concurrentes máximas | `1000` |

### Salida

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `output.dir` | Carpeta de salida | `output` |
| `output.found_suffix` | Sufijo del archivo de encontrados | `_ENCONTRADOS` |
| `output.not_found_suffix` | Sufijo del archivo de no encontrados | `_NO_ENCONTRADOS` |

## Salida

El programa genera dos archivos Excel por cada archivo de origen:

- `{nombre}_ENCONTRADOS.xlsx`: Servidores con declaraciones encontradas
  - Columnas: `Name`, `RFC`, `noComprobante_2025`, `noComprobante_2026`, ... (una columna por año configurado)
- `{nombre}_NO_ENCONTRADOS.xlsx`: Servidores no encontrados o sin declaración
  - Columnas: `Name`, `RFC`

Los archivos se guardan en la carpeta configurada en `output.dir`.

## Arquitectura

### Tech Stack

| Capa | Tecnología |
|------|------------|
| Backend | Rust (Tauri 2.0) — reqwest, tokio, rusqlite, calamine, rust_xlsxwriter |
| Caché | SQLite con SHA256 + WAL mode |
| Frontend | HTML/CSS/JS vanilla + Vite |
| Empaquetado | Tauri bundler (NSIS installer para Windows) |

### Módulos Rust

| Módulo | Responsabilidad |
|--------|-----------------|
| `lib.rs` | Punto de entrada Tauri, registro de comandos y estado de la app |
| `config.rs` | Carga/guardado de configuración TOML |
| `models.rs` | Estructuras de datos serializables (AppConfig, PersonResult, eventos) |
| `cache.rs` | Caché SQLite con TTL y hashing SHA256 — compartido entre todos los workers |
| `rate_limit.rs` | Limitador de tasa async con semaphore, cooldown exponencial y min_interval |
| `client.rs` | Cliente HTTP reqwest con headers de producción y timeout configurable |
| `seed_index.rs` | Lectura de Excel con caché de DataFrames en memoria |
| `worker.rs` | Procesamiento de persona: búsqueda por RFC → historial por idUsrDecnet → filtrado por año/tipo/institución |
| `compactor.rs` | Escritura de archivos Excel de salida con rust_xlsxwriter |
| `orchestrator.rs` | Bucle principal: procesa lotes secuenciales con workers concurrentes, emite progress/log events |
| `system_info.rs` | Detección de CPU/RAM y recomendaciones de configuración automática |

### Flujo de procesamiento

1. **Lectura**: `seed_index` carga filas del Excel en lotes
2. **Búsqueda**: cada `worker` busca el RFC en DeclaraNet (endpoint `search`)
3. **Historial**: si se encuentra, obtiene el historial de declaraciones (endpoint `history`)
4. **Filtrado**: aplica filtros de año, tipo de declaración e institución
5. **Caché**: las respuestas se almacenan en SQLite; los workers reutilizan resultados previos en lugar de repetir llamadas al API
6. **Escritura**: `compactor` genera los archivos Excel de encontrados y no encontrados

## CI/CD

GitHub Actions (`.github/workflows/release.yml`):

- **Push a master / PR**: ejecuta `cargo test` y build de verificación
- **Tag `v*`**: genera el instalador NSIS `.exe` y lo publica como release asset

## Desarrollo

```bash
# Clonar el repositorio
git clone <url-del-repo>
cd auto-servidores

# Instalar dependencias de frontend
npm install

# Ejecutar en modo desarrollo
npm run tauri dev

# Construir para producción
npm run tauri build

# Ejecutar tests
cd src-tauri
cargo test --verbose
```

## Licencia

Uso interno. El proyecto consulta datos públicos de servidores públicos mexicanos a través de la plataforma DeclaraNet.