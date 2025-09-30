use pyo3::prelude::*;
use rayon::prelude::*;
use std::collections::HashMap;
use ahash::{AHashMap, AHashSet};
use std::fs::{File, OpenOptions};
use std::io::{BufReader, BufWriter, BufRead, Write};
use memchr::memchr_iter;

/// Ultra-fast TSV line parser using memchr for tab finding
#[pyfunction]
fn parse_tsv_line_fast(line: &str, columns: Vec<String>) -> PyResult<HashMap<String, String>> {
    let mut result = HashMap::with_capacity(columns.len());
    let bytes = line.as_bytes();
    let mut last_pos = 0;
    let mut col_idx = 0;

    // Use memchr to find tabs - much faster than split()
    for tab_pos in memchr_iter(b'\t', bytes) {
        if col_idx < columns.len() {
            let value = std::str::from_utf8(&bytes[last_pos..tab_pos])
                .unwrap_or("")
                .to_string();
            result.insert(columns[col_idx].clone(), value);
            col_idx += 1;
        }
        last_pos = tab_pos + 1;
    }

    // Handle last field
    if col_idx < columns.len() && last_pos < bytes.len() {
        let value = std::str::from_utf8(&bytes[last_pos..])
            .unwrap_or("")
            .to_string();
        result.insert(columns[col_idx].clone(), value);
    }

    // Fill remaining columns with empty strings
    for i in (col_idx + 1)..columns.len() {
        result.insert(columns[i].clone(), String::new());
    }

    Ok(result)
}

/// Batch parse TSV lines in parallel with pre-allocation
#[pyfunction]
fn parse_tsv_batch_fast(lines: Vec<String>, columns: Vec<String>) -> PyResult<Vec<HashMap<String, String>>> {
    let column_refs: Vec<&str> = columns.iter().map(|s| s.as_str()).collect();

    let results: Vec<HashMap<String, String>> = lines
        .par_iter()
        .map(|line| {
            let mut record = HashMap::with_capacity(columns.len());
            let bytes = line.as_bytes();
            let mut last_pos = 0;
            let mut col_idx = 0;

            for tab_pos in memchr_iter(b'\t', bytes) {
                if col_idx < column_refs.len() {
                    let value = std::str::from_utf8(&bytes[last_pos..tab_pos])
                        .unwrap_or("")
                        .to_string();
                    record.insert(column_refs[col_idx].to_string(), value);
                    col_idx += 1;
                }
                last_pos = tab_pos + 1;
            }

            if col_idx < column_refs.len() && last_pos < bytes.len() {
                let value = std::str::from_utf8(&bytes[last_pos..])
                    .unwrap_or("")
                    .to_string();
                record.insert(column_refs[col_idx].to_string(), value);
            }

            record
        })
        .collect();

    Ok(results)
}

/// Build an index from records using AHash (fastest hash map)
#[pyfunction]
fn build_index(
    records: Vec<HashMap<String, String>>,
    index_column: String
) -> PyResult<HashMap<String, Vec<usize>>> {
    let mut index: AHashMap<String, Vec<usize>> = AHashMap::new();

    for (row_num, record) in records.iter().enumerate() {
        if let Some(key) = record.get(&index_column) {
            index.entry(key.clone())
                .or_insert_with(Vec::new)
                .push(row_num);
        }
    }

    // Convert back to standard HashMap for Python
    Ok(index.into_iter().collect())
}

/// Ultra-fast filtering using parallel processing
#[pyfunction]
fn filter_records_fast(
    records: Vec<HashMap<String, String>>,
    conditions: HashMap<String, String>
) -> PyResult<Vec<HashMap<String, String>>> {
    if conditions.is_empty() {
        return Ok(records);
    }

    // Pre-compute condition checks for speed
    let condition_vec: Vec<(&str, &str)> = conditions
        .iter()
        .map(|(k, v)| (k.as_str(), v.as_str()))
        .collect();

    let results: Vec<HashMap<String, String>> = records
        .into_par_iter()
        .filter(|record| {
            condition_vec.iter().all(|(key, value)| {
                record.get(*key).map_or(false, |v| v == *value)
            })
        })
        .collect();

    Ok(results)
}

/// Optimized TSV file reader with buffering
#[pyfunction]
fn read_tsv_file(
    file_path: String,
    columns: Vec<String>,
    limit: Option<usize>
) -> PyResult<Vec<HashMap<String, String>>> {
    let file = File::open(file_path)?;
    let reader = BufReader::with_capacity(65536, file);
    let mut records = Vec::new();
    let mut lines_read = 0;

    for line_result in reader.lines().skip(1) { // Skip header
        if let Some(max) = limit {
            if lines_read >= max {
                break;
            }
        }

        let line = line_result?;
        let record = parse_tsv_line_fast(&line, columns.clone())?;
        records.push(record);
        lines_read += 1;
    }

    Ok(records)
}

/// Batch write with large buffer for maximum speed
#[pyfunction]
fn write_tsv_batch_fast(
    file_path: String,
    columns: Vec<String>,
    records: Vec<HashMap<String, String>>,
    append: bool
) -> PyResult<usize> {
    let file = if append {
        OpenOptions::new()
            .create(true)
            .append(true)
            .open(&file_path)?
    } else {
        File::create(&file_path)?
    };

    // Use 256KB buffer for fast writes
    let mut writer = BufWriter::with_capacity(262144, file);

    // If not appending, write header
    if !append {
        writeln!(writer, "{}", columns.join("\t"))?;
    }

    // Pre-allocate string buffer for each row
    let mut row_buffer = String::with_capacity(1024);

    for record in &records {
        row_buffer.clear();
        for (i, col) in columns.iter().enumerate() {
            if i > 0 {
                row_buffer.push('\t');
            }
            row_buffer.push_str(record.get(col).unwrap_or(&String::new()));
        }
        writeln!(writer, "{}", row_buffer)?;
    }

    writer.flush()?;
    Ok(records.len())
}

/// Count matching records without materializing results
#[pyfunction]
fn count_matching_fast(
    records: Vec<HashMap<String, String>>,
    conditions: HashMap<String, String>
) -> PyResult<usize> {
    if conditions.is_empty() {
        return Ok(records.len());
    }

    let condition_vec: Vec<(&str, &str)> = conditions
        .iter()
        .map(|(k, v)| (k.as_str(), v.as_str()))
        .collect();

    let count = records
        .par_iter()
        .filter(|record| {
            condition_vec.iter().all(|(key, value)| {
                record.get(*key).map_or(false, |v| v == *value)
            })
        })
        .count();

    Ok(count)
}

/// Find unique values in a column (useful for analytics)
#[pyfunction]
fn unique_values(
    records: Vec<HashMap<String, String>>,
    column: String
) -> PyResult<Vec<String>> {
    let unique_values: Vec<String> = records
        .par_iter()
        .filter_map(|record| record.get(&column).cloned())
        .collect();

    // Deduplicate using AHashSet
    let unique: AHashSet<String> = unique_values.into_iter().collect();

    Ok(unique.into_iter().collect())
}

/// Group by a column and count occurrences
#[pyfunction]
fn group_by_count(
    records: Vec<HashMap<String, String>>,
    column: String
) -> PyResult<HashMap<String, usize>> {
    let mut counts: AHashMap<String, usize> = AHashMap::new();

    for record in records {
        if let Some(value) = record.get(&column) {
            *counts.entry(value.clone()).or_insert(0) += 1;
        }
    }

    Ok(counts.into_iter().collect())
}

/// Aggregate sum of numeric column grouped by another column
#[pyfunction]
fn group_by_sum(
    records: Vec<HashMap<String, String>>,
    group_column: String,
    sum_column: String
) -> PyResult<HashMap<String, f64>> {
    let mut sums: AHashMap<String, f64> = AHashMap::new();

    for record in records {
        if let (Some(group), Some(value_str)) = (record.get(&group_column), record.get(&sum_column)) {
            if let Ok(value) = value_str.parse::<f64>() {
                *sums.entry(group.clone()).or_insert(0.0) += value;
            }
        }
    }

    Ok(sums.into_iter().collect())
}

/// Python module definition
#[pymodule]
fn dbbasic_rust(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_tsv_line_fast, m)?)?;
    m.add_function(wrap_pyfunction!(parse_tsv_batch_fast, m)?)?;
    m.add_function(wrap_pyfunction!(build_index, m)?)?;
    m.add_function(wrap_pyfunction!(filter_records_fast, m)?)?;
    m.add_function(wrap_pyfunction!(read_tsv_file, m)?)?;
    m.add_function(wrap_pyfunction!(write_tsv_batch_fast, m)?)?;
    m.add_function(wrap_pyfunction!(count_matching_fast, m)?)?;
    m.add_function(wrap_pyfunction!(unique_values, m)?)?;
    m.add_function(wrap_pyfunction!(group_by_count, m)?)?;
    m.add_function(wrap_pyfunction!(group_by_sum, m)?)?;
    Ok(())
}