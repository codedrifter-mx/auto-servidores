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
