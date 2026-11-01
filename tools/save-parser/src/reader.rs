use byteorder::{LittleEndian, ReadBytesExt};
use std::io::{Cursor, Read};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ReadError {
    #[error("unexpected end of data at offset {0}")]
    Eof(usize),
    #[error("invalid utf-16 string")]
    InvalidUtf16,
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
}

pub type Result<T> = std::result::Result<T, ReadError>;

/// Minimal little-endian binary cursor used to walk the GVAS property tree.
pub struct Reader<'a> {
    cursor: Cursor<&'a [u8]>,
    len: usize,
}

impl<'a> Reader<'a> {
    pub fn new(data: &'a [u8]) -> Self {
        Reader { cursor: Cursor::new(data), len: data.len() }
    }

    pub fn pos(&self) -> u64 {
        self.cursor.position()
    }

    pub fn set_pos(&mut self, pos: u64) {
        self.cursor.set_position(pos);
    }

    pub fn remaining(&self) -> usize {
        self.len.saturating_sub(self.cursor.position() as usize)
    }

    pub fn bytes(&mut self, n: usize) -> Result<Vec<u8>> {
        if self.remaining() < n {
            return Err(ReadError::Eof(self.cursor.position() as usize));
        }
        let mut buf = vec![0u8; n];
        self.cursor.read_exact(&mut buf)?;
        Ok(buf)
    }

    pub fn u8(&mut self) -> Result<u8> {
        Ok(self.cursor.read_u8()?)
    }

    pub fn u16(&mut self) -> Result<u16> {
        Ok(self.cursor.read_u16::<LittleEndian>()?)
    }

    pub fn i16(&mut self) -> Result<i16> {
        Ok(self.cursor.read_i16::<LittleEndian>()?)
    }

    pub fn u32(&mut self) -> Result<u32> {
        Ok(self.cursor.read_u32::<LittleEndian>()?)
    }

    pub fn i32(&mut self) -> Result<i32> {
        Ok(self.cursor.read_i32::<LittleEndian>()?)
    }

    pub fn u64(&mut self) -> Result<u64> {
        Ok(self.cursor.read_u64::<LittleEndian>()?)
    }

    pub fn i64(&mut self) -> Result<i64> {
        Ok(self.cursor.read_i64::<LittleEndian>()?)
    }

    pub fn f32(&mut self) -> Result<f32> {
        Ok(self.cursor.read_f32::<LittleEndian>()?)
    }

    pub fn f64(&mut self) -> Result<f64> {
        Ok(self.cursor.read_f64::<LittleEndian>()?)
    }

    pub fn guid(&mut self) -> Result<String> {
        let b = self.bytes(16)?;
        Ok(b.iter().map(|x| format!("{:02x}", x)).collect())
    }

    /// UE FString: i32 length prefix. Positive => UTF-8 (ANSI in practice),
    /// negative => UTF-16LE with the absolute value as char count (incl. null terminator).
    pub fn fstring(&mut self) -> Result<String> {
        let n = self.i32()?;
        if n == 0 {
            return Ok(String::new());
        }
        if n < 0 {
            let count = (-n) as usize;
            let bytes = self.bytes(count * 2)?;
            let units: Vec<u16> = bytes
                .chunks_exact(2)
                .map(|c| u16::from_le_bytes([c[0], c[1]]))
                .collect();
            let s = String::from_utf16(&units).map_err(|_| ReadError::InvalidUtf16)?;
            Ok(s.trim_end_matches('\0').to_string())
        } else {
            let bytes = self.bytes(n as usize)?;
            let s = String::from_utf8_lossy(&bytes).to_string();
            Ok(s.trim_end_matches('\0').to_string())
        }
    }
}
