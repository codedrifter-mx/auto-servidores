# Web Scrapper de servidorespublicos.gob.mx

Un script de Python que consulta y verifica si los servidores públicos tienen declaración anual actualizada.

## Requisitos

* Python 3.10
* Última versión de Chrome
* Windows (Linux pendiente)

## Uso del script

1. Instala las librerías:
`
pip install -r requirements.txt
`

2. Coloca tus archivos Excel de origen dentro de la carpeta /seed, la 1ª columna debe ser "Nombres", la 2ª debe ser "RFC", de lo contrario fallará

3. Ejecuta:
`
python .\main.py
`

## Cómo funciona
El script lee los nombres y RFCs desde seed.xlsx, navega al sitio web de servidorespublicos.gob.mx, e intenta encontrar y descargar los documentos de declaración anual de cada servidor público listado. Utiliza Chrome en modo headless para navegar el sitio, lo que significa que Chrome se ejecuta en segundo plano sin una ventana visible.

## Salida
El script creará dos archivos Excel:

ENCONTRADAS.xlsx: Contiene los detalles de los servidores públicos cuyas declaraciones fueron encontradas y descargadas exitosamente.
NO_ENCONTRADAS.xlsx: Contiene los detalles de los servidores públicos cuyas declaraciones no fueron encontradas.
Cada archivo incluirá los nombres, RFCs y otros detalles relevantes extraídos durante el proceso de scraping.