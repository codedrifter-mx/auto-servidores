use crate::models::{AppConfig, PersonResult};
use rust_xlsxwriter::Workbook;
use std::path::Path;

pub struct Compactor<'a> {
    output_dir: &'a str,
    found_suffix: &'a str,
    not_found_suffix: &'a str,
    years: &'a [u32],
}

impl<'a> Compactor<'a> {
    pub fn new(config: &'a AppConfig) -> Self {
        Self {
            output_dir: &config.output.dir,
            found_suffix: &config.output.found_suffix,
            not_found_suffix: &config.output.not_found_suffix,
            years: &config.filters.years_to_check,
        }
    }

    pub fn compact(
        &self,
        found: &[PersonResult],
        not_found: &[PersonResult],
        base_filename: &str,
    ) -> Result<CompactSummary, String> {
        std::fs::create_dir_all(self.output_dir)
            .map_err(|e| format!("Error creating output directory: {}", e))?;

        let found_path = self.write_found(found, base_filename)?;
        let not_found_path = self.write_not_found(not_found, base_filename)?;

        Ok(CompactSummary {
            found_count: found.len(),
            not_found_count: not_found.len(),
            found_path,
            not_found_path,
        })
    }

    fn write_found(
        &self,
        found: &[PersonResult],
        base_filename: &str,
    ) -> Result<Option<String>, String> {
        if found.is_empty() {
            return Ok(None);
        }
        let path = Path::new(self.output_dir)
            .join(format!("{}{}.xlsx", base_filename, self.found_suffix));
        let mut workbook = Workbook::new();
        let worksheet = workbook.add_worksheet();
        worksheet
            .write(0, 0, "Name")
            .map_err(|e| format!("Error writing header: {}", e))?;
        worksheet
            .write(0, 1, "RFC")
            .map_err(|e| format!("Error: {}", e))?;
        for (i, year) in self.years.iter().enumerate() {
            worksheet
                .write(0, (2 + i) as u16, format!("noComprobante_{}", year))
                .map_err(|e| format!("Error writing year header: {}", e))?;
        }
        for (row, person) in found.iter().enumerate() {
            let row_num = (row + 1) as u32;
            worksheet
                .write_string(row_num, 0, &person.name)
                .map_err(|e| format!("Error: {}", e))?;
            worksheet
                .write_string(row_num, 1, &person.rfc)
                .map_err(|e| format!("Error: {}", e))?;
            if let Some(ref comprobantes) = person.comprobantes {
                for (i, year) in self.years.iter().enumerate() {
                    let val = comprobantes.get(year).map(|s| s.as_str()).unwrap_or("");
                    worksheet
                        .write_string(row_num, (2 + i) as u16, val)
                        .map_err(|e| format!("Error: {}", e))?;
                }
            }
        }
        workbook
            .save(&path)
            .map_err(|e| format!("Error saving found file: {}", e))?;
        Ok(Some(path.to_string_lossy().to_string()))
    }

    fn write_not_found(
        &self,
        not_found: &[PersonResult],
        base_filename: &str,
    ) -> Result<Option<String>, String> {
        if not_found.is_empty() {
            return Ok(None);
        }
        let path = Path::new(self.output_dir)
            .join(format!("{}{}.xlsx", base_filename, self.not_found_suffix));
        let mut workbook = Workbook::new();
        let worksheet = workbook.add_worksheet();
        worksheet
            .write(0, 0, "Name")
            .map_err(|e| format!("Error: {}", e))?;
        worksheet
            .write(0, 1, "RFC")
            .map_err(|e| format!("Error: {}", e))?;
        for (row, person) in not_found.iter().enumerate() {
            let row_num = (row + 1) as u32;
            worksheet
                .write_string(row_num, 0, &person.name)
                .map_err(|e| format!("Error: {}", e))?;
            worksheet
                .write_string(row_num, 1, &person.rfc)
                .map_err(|e| format!("Error: {}", e))?;
        }
        workbook
            .save(&path)
            .map_err(|e| format!("Error saving not_found file: {}", e))?;
        Ok(Some(path.to_string_lossy().to_string()))
    }
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct CompactSummary {
    pub found_count: usize,
    pub not_found_count: usize,
    pub found_path: Option<String>,
    pub not_found_path: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn make_found_person(name: &str, rfc: &str, years: Vec<(u32, &str)>) -> PersonResult {
        let comprobantes: HashMap<u32, String> = years.into_iter()
            .map(|(y, v)| (y, v.to_string()))
            .collect();
        PersonResult {
            name: name.to_string(),
            rfc: rfc.to_string(),
            status: "Found".to_string(),
            comprobantes: if comprobantes.is_empty() { None } else { Some(comprobantes) },
        }
    }

    fn make_not_found_person(name: &str, rfc: &str) -> PersonResult {
        PersonResult {
            name: name.to_string(),
            rfc: rfc.to_string(),
            status: "Not found".to_string(),
            comprobantes: None,
        }
    }

    #[test]
    fn test_compact_found_writes_xlsx() {
        let dir = tempfile::tempdir().unwrap();
        let mut config = crate::config::default_config();
        config.output.dir = dir.path().to_string_lossy().to_string();
        config.filters.years_to_check = vec![2025, 2026];
        let compactor = Compactor::new(&config);
        let found = vec![make_found_person("JUAN PEREZ", "XEXX010101000", vec![
            (2025, "COMP001"),
            (2026, "COMP002"),
        ])];
        let not_found = vec![];
        let result = compactor.compact(&found, &not_found, "test_data").unwrap();
        assert_eq!(result.found_count, 1);
        assert_eq!(result.not_found_count, 0);
        let found_path = dir.path().join("test_data_ENCONTRADOS.xlsx");
        assert!(found_path.exists());
    }

    #[test]
    fn test_compact_not_found_writes_xlsx() {
        let dir = tempfile::tempdir().unwrap();
        let mut config = crate::config::default_config();
        config.output.dir = dir.path().to_string_lossy().to_string();
        config.filters.years_to_check = vec![2025];
        let compactor = Compactor::new(&config);
        let not_found = vec![make_not_found_person("MARIA LOPEZ", "XEXX020202000")];
        let result = compactor.compact(&[], &not_found, "test_data").unwrap();
        assert_eq!(result.found_count, 0);
        assert_eq!(result.not_found_count, 1);
        let not_found_path = dir.path().join("test_data_NO_ENCONTRADOS.xlsx");
        assert!(not_found_path.exists());
    }

    #[test]
    fn test_compact_empty_found_no_file() {
        let dir = tempfile::tempdir().unwrap();
        let mut config = crate::config::default_config();
        config.output.dir = dir.path().to_string_lossy().to_string();
        config.filters.years_to_check = vec![2025];
        let compactor = Compactor::new(&config);
        let result = compactor.compact(&[], &[], "empty_test").unwrap();
        assert_eq!(result.found_count, 0);
        assert_eq!(result.not_found_count, 0);
        assert!(result.found_path.is_none());
        assert!(result.not_found_path.is_none());
    }

    #[test]
    fn test_compact_creates_output_dir() {
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("nested").join("output");
        let mut config = crate::config::default_config();
        config.output.dir = nested.to_string_lossy().to_string();
        config.filters.years_to_check = vec![2025];
        let compactor = Compactor::new(&config);
        let found = vec![make_found_person("TEST", "RFC1", vec![(2025, "C1")])];
        compactor.compact(&found, &[], "dir_test").unwrap();
        assert!(nested.exists());
    }
}
