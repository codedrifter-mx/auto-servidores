# Auto-Servidores

Herramienta Python para consultar de forma masiva el API de DeclaraNet y verificar si los servidores públicos tienen declaraciones anuales actualizadas.

## Requisitos

- **Python 3.13**
- Windows, Linux o macOS

## Instalación

1. Clona el repositorio y entra al directorio:
   ```bash
   git clone <url-del-repo>
   cd auto-servidores
   ```

2. Crea un entorno virtual (recomendado):
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   ```

3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

Para desarrollo y pruebas, instala también:
```bash
pip install -r requirements-dev.txt
```

## Uso

### Modo GUI (recomendado)

```bash
python gui.py
```

Abre una interfaz gráfica donde puedes:
- Arrastrar o seleccionar archivos Excel de origen
- Ajustar tamaño de lote, trabajadores máximos y parámetros de rate limit
- Ver logs en tiempo real y barra de progreso

### Modo headless (sin GUI)

```bash
python main.py --no-gui
```

## Formato de archivos de origen

Coloca tus archivos Excel (`.xlsx`) dentro de la carpeta `seed/`.

**No deben tener fila de encabezado.** La primera columna debe contener los nombres y la segunda columna los RFCs.

| A | B |
|---|---|
| JUAN PEREZ GARCIA | BEGX123456X01 |
| MARIA LOPEZ HDEZ | BEGX654321X02 |

## Configuración

Todos los parámetros son configurables desde `config.yaml`:

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

## Tests

```bash
pytest tests/ -v
```

## Licencia

Uso interno. El proyecto consulta datos públicos de servidores públicos mexicanos a través de la plataforma DeclaraNet.
