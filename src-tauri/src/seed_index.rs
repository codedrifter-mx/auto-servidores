use calamine::{open_workbook, Data, Reader, Xlsx};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use crate::models::SeedFileInfo;

pub struct SeedIndex {
    seed_dir: PathBuf,
    index: Vec<SeedFileInfo>,
    cache: HashMap<PathBuf, Vec<Vec<String>>>,
}

impl SeedIndex {
    pub fn new(seed_dir: &Path) -> Result<Self, String> {
        std::fs::create_dir_all(seed_dir)
            .map_err(|e| format!("Error creating seed directory: {}", e))?;
        let mut si = Self {
            seed_dir: seed_dir.to_path_buf(),
            index: Vec::new(),
            cache: HashMap::new(),
        };
        si.build_index()?;
        Ok(si)
    }

    fn build_index(&mut self) -> Result<(), String> {
        self.index.clear();
        let entries = std::fs::read_dir(&self.seed_dir)
            .map_err(|e| format!("Error reading seed directory: {}", e))?;
        for entry in entries {
            let entry = entry.map_err(|e| format!("Error reading dir entry: {}", e))?;
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) == Some("xlsx") {
                let filename = path.file_name().unwrap().to_string_lossy().to_string();
                let row_count = Self::count_rows(&path)?;
                self.index.push(SeedFileInfo {
                    filename,
                    filepath: path.to_string_lossy().to_string(),
                    basename: path.file_stem().unwrap().to_string_lossy().to_string(),
                    row_count,
                });
            }
        }
        self.index.sort_by(|a, b| a.filename.cmp(&b.filename));
        Ok(())
    }

    fn count_rows(path: &Path) -> Result<usize, String> {
        let mut workbook: Xlsx<_> = open_workbook(path)
            .map_err(|e| format!("Error opening {}: {}", path.display(), e))?;
        let sheets = workbook.sheet_names();
        if sheets.is_empty() {
            return Ok(0);
        }
        let first = &sheets[0];
        let range = workbook.worksheet_range(first)
            .map_err(|e| format!("Error reading sheet: {}", e))?;
        Ok(range.rows().count())
    }

    pub fn get_files(&self) -> &[SeedFileInfo] {
        &self.index
    }

    pub fn load_batch(
        &mut self,
        filepath: &Path,
        start: usize,
        size: usize,
    ) -> Result<Vec<(String, String)>, String> {
        if !self.cache.contains_key(&filepath.to_path_buf()) {
            let data = Self::read_all_rows(filepath)?;
            self.cache.insert(filepath.to_path_buf(), data);
        }
        let data = self.cache.get(&filepath.to_path_buf()).unwrap();
        let batch: Vec<(String, String)> = data
            .iter()
            .skip(start)
            .take(size)
            .filter_map(|row| {
                if row.len() >= 2 {
                    let name = row[0].trim().to_uppercase().replace("/", " ");
                    let rfc = row[1].trim().to_string();
                    if !name.is_empty() && !rfc.is_empty() {
                        return Some((name, rfc));
                    }
                }
                None
            })
            .collect();
        Ok(batch)
    }

    fn read_all_rows(path: &Path) -> Result<Vec<Vec<String>>, String> {
        let mut workbook: Xlsx<_> = open_workbook(path)
            .map_err(|e| format!("Error opening {}: {}", path.display(), e))?;
        let sheets = workbook.sheet_names();
        if sheets.is_empty() {
            return Ok(Vec::new());
        }
        let first = &sheets[0];
        let range = workbook.worksheet_range(first)
            .map_err(|e| format!("Error reading sheet: {}", e))?;
        let mut rows = Vec::new();
        for row in range.rows() {
            let cells: Vec<String> = row
                .iter()
                .map(|cell| match cell {
                    Data::String(s) => s.to_string(),
                    Data::Float(f) => f.to_string(),
                    Data::Int(i) => i.to_string(),
                    Data::Empty => String::new(),
                    _ => cell.to_string(),
                })
                .collect();
            rows.push(cells);
        }
        Ok(rows)
    }

    pub fn refresh(&mut self) -> Result<(), String> {
        self.cache.clear();
        self.build_index()
    }
}
