use auto_servidores::seed_index::SeedIndex;
use rust_xlsxwriter::Workbook;
use std::path::Path;

fn create_xlsx(path: &Path, rows: Vec<Vec<&str>>) {
    let mut workbook = Workbook::new();
    let worksheet = workbook.add_worksheet();
    for (row_idx, row) in rows.iter().enumerate() {
        for (col_idx, cell) in row.iter().enumerate() {
            worksheet.write_string(row_idx as u32, col_idx as u16, *cell).unwrap();
        }
    }
    workbook.save(path).unwrap();
}

#[test]
fn test_seed_index_real_xlsx() {
    let dir = tempfile::tempdir().unwrap();
    let xlsx_path = dir.path().join("data.xlsx");
    create_xlsx(&xlsx_path, vec![
        vec!["ANA TORRES", "XEXX010101000"],
        vec!["LUIS MORALES", "XEXX020202000"],
        vec!["ROSA DIAZ", "XEXX030303000"],
    ]);
    let index = SeedIndex::new(dir.path()).unwrap();
    let files = index.get_files();
    assert_eq!(files.len(), 1);
    assert_eq!(files[0].filename, "data.xlsx");
    assert_eq!(files[0].row_count, 3);
}

#[test]
fn test_seed_index_multiple_files() {
    let dir = tempfile::tempdir().unwrap();
    create_xlsx(&dir.path().join("alpha.xlsx"), vec![vec!["A1", "RFC1"]]);
    create_xlsx(&dir.path().join("beta.xlsx"), vec![vec!["B1", "RFC2"], vec!["B2", "RFC3"]]);
    let index = SeedIndex::new(dir.path()).unwrap();
    let files = index.get_files();
    assert_eq!(files.len(), 2);
    let filenames: Vec<&str> = files.iter().map(|f| f.filename.as_str()).collect();
    assert!(filenames.contains(&"alpha.xlsx"));
    assert!(filenames.contains(&"beta.xlsx"));
}
