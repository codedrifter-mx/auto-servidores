# Guia de Entrega: Como Crear un Release y Compartir la App

> Paso a paso para generar un instalador .exe, subirlo a GitHub Releases, y compartirlo con usuarios finales.

---

## Tabla de Contenidos

1. [Antes de Empezar](#antes-de-empezar)
2. [Opcion A: Release Automatico con GitHub Actions (Recomendado)](#opcion-a-release-automatico-con-github-actions-recomendado)
3. [Opcion B: Build Local y Subida Manual](#opcion-b-build-local-y-subida-manual)
4. [Verificacion del Instalador](#verificacion-del-instalador)
5. [Compartir con Usuarios](#compartir-con-usuarios)
6. [Actualizaciones Futuras](#actualizaciones-futuras)

---

## Antes de Empezar

### Requisitos

- Tienes push access al repositorio `codedrifter-mx/auto-servidores`
- El codigo en `master` compila y pasa tests (`cargo test` debe dar verde)
- GitHub Actions esta habilitado en el repositorio (esta por defecto en repos publicos)

### Que version estas lanzando?

Usamos [Versionado Semantico](https://semver.org/lang/es/):
- `MAJOR.MINOR.PATCH`
- Ejemplo: `v2.0.0`, `v2.1.0`, `v2.1.1`

| Tipo de cambio | Como subir version |
|----------------|--------------------|
| Fix de bug | `PATCH` (ej. `v2.0.1`) |
| Nueva feature | `MINOR` (ej. `v2.1.0`) |
| Breaking change | `MAJOR` (ej. `v3.0.0`) |

---

## Opcion A: Release Automatico con GitHub Actions (Recomendado)

Este es el flujo estandar. Solo necesitas crear un tag y GitHub hace el build por ti.

### Paso 1: Actualizar los numeros de version

Edita estos 3 archivos con la nueva version:

**`src-tauri/Cargo.toml`**
```toml
[package]
name = "auto-servidores"
version = "2.0.0"   # <-- Cambia aqui
```

**`src-tauri/tauri.conf.json`**
```json
{
  "version": "2.0.0"   // <-- Cambia aqui
}
```

**`package.json`**
```json
{
  "version": "2.0.0"   // <-- Cambia aqui
}
```

### Paso 2: Commitear los cambios de version

```bash
git add src-tauri/Cargo.toml src-tauri/tauri.conf.json package.json
git commit -m "chore: bump version to 2.0.0"
git push origin master
```

### Paso 3: Crear y subir un tag

```bash
git tag -a v2.0.0 -m "Release v2.0.0"
git push origin v2.0.0
```

**Que hace esto:**
- Crea un tag anotado `v2.0.0` en tu repo local
- Lo sube a GitHub
- El workflow `.github/workflows/release.yml` se activa automaticamente porque hay un push de tag `v*`

### Paso 4: Monitorear el build en GitHub Actions

1. Ve a https://github.com/codedrifter-mx/auto-servidores/actions
2. Busca el workflow que dice "Build & Release"
3. Espera a que termine (toma ~10-15 minutos)

**Que esta haciendo el CI:**
```
1. Checkout del codigo
2. Instala Rust toolchain
3. Instala Node.js
4. npm install
5. cd src-tauri && cargo test --verbose     (corre tests)
6. npm run tauri build                        (compila la app)
7. Sube el .exe a GitHub Releases
```

### Paso 5: Verificar el release

1. Ve a https://github.com/codedrifter-mx/auto-servidores/releases
2. Deberia aparecer un release llamado `v2.0.0`
3. En la seccion "Assets" debe haber un archivo:
   - `auto-servidores_2.0.0_x64-setup.exe`

### Paso 6: Editar las notas del release

Haz clic en "Edit" en el release y completa la informacion:

```markdown
### Auto Servidores v2.0.0

**Full rewrite to Rust + Tauri**

#### What's New
- Reescritura completa a Rust con Tauri 2.0
- GUI moderna con WebView2
- Tamano de distribucion reducido de ~31 MB a ~5-8 MB
- Arranque casi instantaneo
- Mismo formato de Excel de entrada/salida

#### Breaking Changes
- Ya no requiere Python instalado
- El config cambia de YAML a TOML
- Los seed files deben recolocarse manualmente

#### Installation
1. Descarga `auto-servidores_2.0.0_x64-setup.exe`
2. Ejecuta el instalador
3. Coloca tus archivos .xlsx en la carpeta `seed/`
```

---

## Opcion B: Build Local y Subida Manual

Usa esto si necesitas un build rapido sin esperar al CI, o si GitHub Actions no esta disponible.

### Paso 1: Verificar que todo compila

```bash
cd src-tauri
cargo test --verbose
cd ..
npm run build
```

### Paso 2: Hacer build de produccion

```bash
npm run tauri build
```

Esto toma ~5-10 minutos la primera vez (compila todo Rust en modo release).

### Paso 3: Verificar el instalador generado

```bash
ls src-tauri/target/release/bundle/nsis/
# Deberia mostrar:
# auto-servidores_2.0.0_x64-setup.exe
```

### Paso 4: Crear release manualmente en GitHub

1. Ve a https://github.com/codedrifter-mx/auto-servidores/releases
2. Click en "Draft a new release"
3. Selecciona "Choose a tag" → Escribe `v2.0.0` → "Create new tag"
4. Target: `master`
5. Title: `Auto Servidores v2.0.0`
6. Description: Copia la plantilla de `docs/RELEASE_TEMPLATE.md`
7. Arrastra el archivo `.exe` a la seccion "Attach binaries"
8. Click en "Publish release"

---

## Verificacion del Instalador

Antes de compartir, prueba el instalador en una maquina limpia (o VM):

### Que verificar
- [ ] El instalador se ejecuta sin errores
- [ ] La app se instala y aparece en el menu Inicio
- [ ] La app arranca en menos de 2 segundos
- [ ] El boton "Agregar Archivo" abre el dialogo de archivos
- [ ] Al agregar un Excel, aparece en la lista con el conteo de filas
- [ ] "Auto-Configurar" ajusta los sliders basado en el hardware
- [ ] "Iniciar Procesamiento" comienza y muestra logs en tiempo real
- [ ] La barra de progreso avanza
- [ ] Los archivos `_ENCONTRADOS.xlsx` y `_NO_ENCONTRADOS.xlsx` se generan en la carpeta output/

### Problemas comunes

| Problema | Causa probable | Solucion |
|----------|---------------|----------|
| "Missing DLL" al arrancar | Falta VC++ Redistributable | Instala [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| Pantalla en blanco | WebView2 no instalado | Instala [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) (usualmente ya viene en Win10/11) |
| No puede leer Excel | Formato no soportado | Asegurate que sea `.xlsx` (no `.xls`) y sin contrasena |
| API devuelve siempre "Not found" | Cambio en el API | Verifica `config.toml` → `api.base_url` y endpoints |

---

## Compartir con Usuarios

### Opcion 1: Link al GitHub Release (Recomendado)

Comparte directamente el link al release:

```
Hola, aqui esta la nueva version de Auto Servidores:

https://github.com/codedrifter-mx/auto-servidores/releases/tag/v2.0.0

Instrucciones:
1. Descarga el archivo .exe de la seccion "Assets"
2. Ejecuta el instalador
3. Coloca tus archivos Excel en la carpeta seed/
4. Abre la app y presiona "Iniciar Procesamiento"
```

### Opcion 2: Subir el .exe a otra plataforma

Si necesitas compartirlo fuera de GitHub:
- **Google Drive / Dropbox**: Sube el `.exe` y comparte el link
- **OneDrive for Business**: Ideal para compartir dentro de una organizacion
- **WeTransfer / SendAnywhere**: Para envios temporales

### Opcion 3: Distribucion interna (empresas)

Para despliegue masivo en una organizacion:
- **Intune / SCCM**: El `.exe` soporta instalacion silenciosa via parametros NSIS estandar
- **Group Policy**: Puedes empaquetar el instalador en un MSI usando herramientas como [MSI Wrapper](https://www.exemsi.com/)

---

## Actualizaciones Futuras

### Como lanzar una nueva version

Simplemente repite **Opcion A** (recomendado) o **Opcion B** con el nuevo numero de version.

**Ejemplo: Lanzar v2.1.0 con un bugfix**

```bash
# 1. Arregla el bug en el codigo
# 2. Actualiza versiones
git add src-tauri/Cargo.toml src-tauri/tauri.conf.json package.json
git commit -m "fix: corrige problema X"
git push origin master

# 3. Crea tag
git tag -a v2.1.0 -m "Release v2.1.0"
git push origin v2.1.0

# 4. Espera al CI en https://github.com/codedrifter-mx/auto-servidores/actions
# 5. Verifica en https://github.com/codedrifter-mx/auto-servidores/releases
```

### Migracion de usuarios de v1.x (Python) a v2.x (Rust)

Los usuarios que tenian la version Python deben:
1. Desinstalar la version anterior (si la instalaron via PyInstaller, solo borran la carpeta)
2. Instalar la nueva version via el `.exe`
3. **Recrear su configuracion**: La nueva version usa `config.toml` en vez de `config.yaml`
4. **Mover sus seed files**: Copiar los `.xlsx` a la nueva carpeta `seed/`

### Notas para usuarios finales

Puedes incluir esto en un email o documento:

```markdown
## Instalacion de Auto Servidores v2

### Requisitos
- Windows 10 o 11 (64 bits)
- ~20 MB de espacio en disco

### Instalacion
1. Descarga el archivo `auto-servidores_2.X.X_x64-setup.exe`
2. Haz doble clic para ejecutar el instalador
3. Sigue las instrucciones (puedes dejar las opciones por defecto)
4. La app se abrira automaticamente al finalizar

### Uso basico
1. **Agregar archivos**: En la barra lateral, haz clic en "Agregar Archivo" y selecciona tus archivos Excel
2. **Configurar**: Ajusta el tamano de lote y trabajadores, o usa "Auto-Configurar"
3. **Procesar**: Haz clic en "Iniciar Procesamiento"
4. **Resultados**: Los archivos Excel generados estan en la carpeta `output/` dentro del directorio de la app

### Formato de archivos de entrada
- Archivos `.xlsx` (Excel moderno)
- Sin fila de encabezado
- Columna A: Nombre completo
- Columna B: RFC

### Soporte
Si encuentras algun problema, crea un issue en:
https://github.com/codedrifter-mx/auto-servidores/issues
```

---

## Checklist Pre-Release

Antes de crear cualquier release, verifica:

- [ ] `cargo test --verbose` pasa (0 fallos)
- [ ] `npm run build` funciona sin errores
- [ ] Los numeros de version coinciden en los 3 archivos
- [ ] El CHANGELOG o notas de release estan escritos
- [ ] Se probo la app en una maquina limpia (o al menos localmente)
- [ ] La documentacion (`README.md`, `ARCHITECTURE.md`) esta actualizada
- [ ] Se creo y subio el tag correctamente
- [ ] El CI de GitHub Actions termino exitosamente
- [ ] El instalador aparece en la seccion Assets del release
