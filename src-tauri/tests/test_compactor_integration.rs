use auto_servidores::compactor::Compactor;
use auto_servidores::config;
use auto_servidores::models::PersonResult;
use calamine::{open_workbook, Reader, Xlsx};
use std::collections::HashMap;

fn make_found_person(name: &str, rfc: &str, comprobantes: HashMap<u32, String>) -> PersonResult {
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
fn test_compact_round_trip() {
    let dir = tempfile::tempdir().unwrap();
    let mut cfg = config::default_config();
    cfg.output.dir = dir.path().to_string_lossy().to_string();
    cfg.filters.years_to_check = vec![2025, 2026];
    let compactor = Compactor::new(&cfg);

    let mut comprobantes = HashMap::new();
    comprobantes.insert(2025, "COMP001".to_string());
    comprobantes.insert(2026, "COMP002".to_string());

    let found = vec![make_found_person("Jose Garcia", "XEXX010101000", comprobantes)];
    let not_found = vec![make_not_found_person("Maria Lopez", "XEXX020202000")];

    let result = compactor.compact(&found, &not_found, "roundtrip_test").unwrap();
    assert_eq!(result.found_count, 1);
    assert_eq!(result.not_found_count, 1);

    let found_path = dir.path().join("roundtrip_test_ENCONTRADOS.xlsx");
    let mut workbook: Xlsx<_> = open_workbook(&found_path).unwrap();
    let sheets = workbook.sheet_names();
    let range = workbook.worksheet_range(&sheets[0]).unwrap();
    let rows: Vec<_> = range.rows().collect();
    assert_eq!(rows.len(), 2);
    assert_eq!(rows[0].len(), 4);
}

#[test]
fn test_compact_unicode_names() {
    let dir = tempfile::tempdir().unwrap();
    let mut cfg = config::default_config();
    cfg.output.dir = dir.path().to_string_lossy().to_string();
    cfg.filters.years_to_check = vec![2025];
    let compactor = Compactor::new(&cfg);

    let mut comprobantes = HashMap::new();
    comprobantes.insert(2025, "C1".to_string());

    let found = vec![make_found_person("Nuno Fernandez", "XEXX010101000", comprobantes)];
    let result = compactor.compact(&found, &[], "unicode_test").unwrap();
    assert_eq!(result.found_count, 1);
    let found_path = dir.path().join("unicode_test_ENCONTRADOS.xlsx");
    assert!(found_path.exists());
}
