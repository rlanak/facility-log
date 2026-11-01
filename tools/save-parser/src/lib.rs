pub mod reader;
pub mod gvas;
pub mod model;

use reader::Reader;
use std::collections::BTreeMap;

#[derive(Debug, thiserror::Error)]
pub enum ParseError {
    #[error("not a GVAS save file (bad magic bytes)")]
    BadMagic,
    #[error(transparent)]
    Read(#[from] reader::ReadError),
}

/// High-level entry point: bytes in, pinned-location list out.
/// This is what the Tauri app (and the CLI below) call after reading the
/// .sav file from disk.
pub fn parse_save(data: &[u8]) -> Result<Vec<model::PinnedLocation>, ParseError> {
    if data.len() < 4 || &data[0..4] != b"GVAS" {
        return Err(ParseError::BadMagic);
    }
    let mut r = Reader::new(data);
    let _header = gvas::parse_header(&mut r)?;
    let root: BTreeMap<String, gvas::Value> = gvas::parse_property_list(&mut r)?;
    Ok(model::extract_pinned_locations(&root))
}
