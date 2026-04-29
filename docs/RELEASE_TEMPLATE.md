# Release Template

## Step-by-step guide for creating a GitHub release:

1. **Update version numbers:**
   - `src-tauri/tauri.conf.json` → `version`
   - `src-tauri/Cargo.toml` → `version`
   - `package.json` → `version`
   - Commit: `chore: bump version to X.Y.Z`

2. **Create and push a tag:**
   ```bash
   git tag -a v2.0.0 -m "Release v2.0.0"
   git push origin v2.0.0
   ```

3. **Wait for CI to complete:**
   - The `release.yml` workflow triggers on tags starting with `v`
   - It runs tests, then builds the .exe
   - The .exe is uploaded as a release asset automatically

4. **Edit the GitHub release:**
   - Go to https://github.com/<user>/auto-servidores/releases
   - Find the draft release created by the workflow
   - Fill in the release notes using the template below:

---

## Release Notes Template:

### Auto Servidores vX.Y.Z

**Full rewrite to Rust + Tauri** — please read if upgrading from the Python version.

#### What's New
- [List major features/changes]

#### Bug Fixes
- [List fixes, reference issues]

#### Known Issues
- [List known issues]

#### Breaking Changes from v1.x (Python)
- Config format changed from YAML to TOML
- The application is now a native Windows .exe (no Python needed)
- Distribution size reduced from ~31 MB to ~5-8 MB
- Startup time is near-instant

#### Installation
1. Download `auto-servidores_X.Y.Z_x64-setup.exe` from the assets below
2. Run the installer
3. Place your Excel seed files in the `seed/` folder (within the app data directory)

#### Upgrading from v1.x
- Your `config.yaml` will need to be recreated as `config.toml`
- Seed files and cached data are NOT automatically migrated
- The output format remains the same (Excel with _ENCONTRADOS/_NO_ENCONTRADOS suffixes)
