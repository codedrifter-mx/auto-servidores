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
            .map_err(|e| format!("Error opening spreadsheet: {}", e))?;
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
        if let std::collections::hash_map::Entry::Vacant(e) = self.cache.entry(filepath.to_path_buf()) {
            let data = Self::read_all_rows(filepath)?;
            e.insert(data);
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
            .map_err(|e| format!("Error opening spreadsheet: {}", e))?;
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

    #[allow(dead_code)]
    pub fn refresh(&mut self) -> Result<(), String> {
        self.cache.clear();
        self.build_index()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rust_xlsxwriter::Workbook;

    fn create_test_xlsx(path: &Path, rows: Vec<Vec<impl AsRef<str>>>) {
        let mut workbook = Workbook::new();
        let worksheet = workbook.add_worksheet();
        for (row_idx, row) in rows.iter().enumerate() {
            for (col_idx, cell) in row.iter().enumerate() {
                worksheet.write_string(row_idx as u32, col_idx as u16, cell.as_ref()).unwrap();
            }
        }
        workbook.save(path).unwrap();
    }

    #[test]
    fn test_seed_index_reads_xlsx() {
        let dir = tempfile::tempdir().unwrap();
        let xlsx_path = dir.path().join("test_data.xlsx");
        create_test_xlsx(&xlsx_path, vec![
            vec!["JUAN PEREZ", "XEXX010101000"],
            vec!["MARIA LOPEZ", "XEXX020202000"],
            vec!["CARLOS RAMIREZ", "XEXX030303000"],
        ]);
        let index = SeedIndex::new(dir.path()).unwrap();
        let files = index.get_files();
        assert_eq!(files.len(), 1);
        assert_eq!(files[0].filename, "test_data.xlsx");
        assert_eq!(files[0].row_count, 3);
    }

    #[test]
    fn test_seed_index_skips_non_xlsx() {
        let dir = tempfile::tempdir().unwrap();
        let xlsx_path = dir.path().join("data.xlsx");
        let txt_path = dir.path().join("notes.txt");
        create_test_xlsx(&xlsx_path, vec![vec!["A", "B"]]);
        std::fs::write(&txt_path, "not a spreadsheet").unwrap();
        let index = SeedIndex::new(dir.path()).unwrap();
        let files = index.get_files();
        assert_eq!(files.len(), 1);
        assert_eq!(files[0].filename, "data.xlsx");
    }

    #[test]
    fn test_load_batch_pagination() {
        let dir = tempfile::tempdir().unwrap();
        let xlsx_path = dir.path().join("paged.xlsx");
        let mut rows = vec![];
        for i in 0..10 {
            rows.push(vec![format!("Name {}", i), format!("RFC{}", i)]);
        }
        create_test_xlsx(&xlsx_path, rows);
        let mut index = SeedIndex::new(dir.path()).unwrap();
        let batch1 = index.load_batch(&xlsx_path, 0, 5).unwrap();
        let batch2 = index.load_batch(&xlsx_path, 5, 5).unwrap();
        assert_eq!(batch1.len(), 5);
        assert_eq!(batch2.len(), 5);
        assert_eq!(batch1[0].0, "NAME 0");
    }

    #[test]
    fn test_load_batch_filters_empty_rows() {
        let dir = tempfile::tempdir().unwrap();
        let xlsx_path = dir.path().join("gaps.xlsx");
        create_test_xlsx(&xlsx_path, vec![
            vec!["JUAN PEREZ", "RFC1"],
            vec!["", ""],
            vec!["MARIA LOPEZ", "RFC2"],
        ]);
        let mut index = SeedIndex::new(dir.path()).unwrap();
        let batch = index.load_batch(&xlsx_path, 0, 100).unwrap();
        assert_eq!(batch.len(), 2);
    }

    #[test]
    fn test_load_batch_uppercases_name() {
        let dir = tempfile::tempdir().unwrap();
        let xlsx_path = dir.path().join("case.xlsx");
        create_test_xlsx(&xlsx_path, vec![
            vec!["juan perez", "RFC1"],
        ]);
        let mut index = SeedIndex::new(dir.path()).unwrap();
        let batch = index.load_batch(&xlsx_path, 0, 100).unwrap();
        assert_eq!(batch[0].0, "JUAN PEREZ");
    }

    #[test]
    fn test_seed_index_empty_dir() {
        let dir = tempfile::tempdir().unwrap();
        let index = SeedIndex::new(dir.path()).unwrap();
        assert!(index.get_files().is_empty());
    }
}
