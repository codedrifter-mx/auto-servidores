# Auto-Servidores

Herramienta para consultar de forma masiva el API de DeclaraNet y verificar si los servidores públicos tienen declaraciones anuales actualizadas.

## Requisitos

- **Windows 10/11**
- No se requiere Python ni ninguna dependencia adicional (aplicación nativa)

## Instalación

1. Descarga el instalador `.exe` más reciente desde la pestaña [Releases](https://github.com/codedrifter-mx/auto-servidores/releases)
2. Ejecuta el instalador
3. La aplicación se instalará y podrás ejecutarla desde el menú Inicio o el acceso directo en el escritorio

## Uso

1. **Agrega archivos de origen**: En la barra lateral, haz clic en "Agregar Archivo" y selecciona tus archivos Excel (`.xlsx`)
2. **Configura parámetros**: Ajusta el tamaño de lote y trabajadores máximos con los sliders, o usa "Auto-Configurar"
3. **Inicia el procesamiento**: Haz clic en "Iniciar Procesamiento"
4. **Revisa resultados**: Los archivos de salida se generarán en la carpeta `output/`

## Formato de archivos de origen

Coloca tus archivos Excel (`.xlsx`) dentro de la carpeta `seed/`.

**No deben tener fila de encabezado.** La primera columna debe contener los nombres y la segunda columna los RFCs.

| A | B |
|---|---|
| JUAN PEREZ GARCIA | BEGX123456X01 |
| MARIA LOPEZ HDEZ | BEGX654321X02 |

## Configuración

Todos los parámetros son configurables desde `config.toml`:

- `api.base_url`: URL base del servicio DeclaraNet
- `api.max_retries` / `api.retry_base_delay`: Reintentos y espera exponencial
- `rate_limit.max_concurrent`: Conexiones simultáneas máximas
- `rate_limit.min_interval`: Intervalo mínimo entre requests
- `rate_limit.cooldown_base` / `cooldown_max`: Backoff exponencial al recibir 429
- `processing.batch_size`: Tamaño de lote para leer del Excel
- `processing.max_workers`: Tareas concurrentes máximas
- `output.dir`: Carpeta de salida (por defecto `output/`)

## Salida

El programa genera dos archivos Excel por cada archivo de origen:

- `{nombre}_ENCONTRADOS.xlsx`: Servidores con declaraciones encontradas
- `{nombre}_NO_ENCONTRADOS.xlsx`: Servidores no encontrados o sin declaración

Los archivos se guardan en la carpeta configurada en `output.dir`.

## Caché

Las respuestas del API se almacenan en SQLite (`.cache/api_cache.db`) con TTL configurable. Esto acelera re-ejecuciones y reduce la carga sobre el servidor.

## Desarrollo

### Construir desde el código fuente

Requisitos:
- [Rust](https://rustup.rs/)
- [Node.js](https://nodejs.org/) v22+

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
```

### Ejecutar tests

```bash
cd src-tauri
cargo test --verbose
```

## Arquitectura

- **Backend**: Rust con Tauri 2.0
  - `config.rs`: Carga/guardado de configuración TOML
  - `cache.rs`: Caché SQLite con TTL
  - `rate_limit.rs`: Limitador de tasa async
  - `client.rs`: Cliente HTTP con headers de producción
  - `seed_index.rs`: Lectura de Excel con caché de DataFrames
  - `worker.rs`: Procesamiento de persona (búsqueda + historial)
  - `compactor.rs`: Escritura de archivos Excel de salida
  - `orchestrator.rs`: Bucle principal de procesamiento por lotes
- **Frontend**: HTML/CSS/JS vanilla servido por Vite
- **Empaquetado**: Tauri bundler (NSIS installer para Windows)

## Licencia

Uso interno. El proyecto consulta datos públicos de servidores públicos mexicanos a través de la plataforma DeclaraNet.
