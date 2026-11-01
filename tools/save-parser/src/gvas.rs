use crate::reader::{Reader, Result};
use serde::Serialize;
use std::collections::BTreeMap;

/// Generic value produced by walking a UE4 tagged-property list.
/// This mirrors the small subset of property types Foxhole's
/// PlayerMapDataSaveGame actually uses.
#[derive(Debug, Clone, Serialize)]
#[serde(untagged)]
pub enum Value {
    Int(i64),
    Float(f64),
    Bool(bool),
    Str(String),
    Vector2D { x: f32, y: f32 },
    Struct(BTreeMap<String, Value>),
    Array(Vec<Value>),
    Raw(String),
}

impl Value {
    pub fn as_i64(&self) -> Option<i64> {
        match self {
            Value::Int(v) => Some(*v),
            _ => None,
        }
    }
    pub fn as_str(&self) -> Option<&str> {
        match self {
            Value::Str(s) => Some(s),
            _ => None,
        }
    }
    pub fn as_struct(&self) -> Option<&BTreeMap<String, Value>> {
        match self {
            Value::Struct(m) => Some(m),
            _ => None,
        }
    }
    pub fn as_array(&self) -> Option<&Vec<Value>> {
        match self {
            Value::Array(v) => Some(v),
            _ => None,
        }
    }
}

#[derive(Debug, Clone)]
pub struct GvasHeader {
    pub save_version: u32,
    pub package_ue4_version: u32,
    pub engine_version: String,
    pub save_class: String,
}

pub fn parse_header(r: &mut Reader) -> Result<GvasHeader> {
    let magic = r.bytes(4)?;
    debug_assert_eq!(&magic, b"GVAS");
    let save_version = r.u32()?;
    let package_ue4_version = r.u32()?;
    if save_version >= 3 {
        r.u32()?; // package_ue5_version, unused by Foxhole (UE 4.24)
    }
    let major = r.u16()?;
    let minor = r.u16()?;
    let patch = r.u16()?;
    let build = r.u32()?;
    let _build_id = r.fstring()?;
    let _custom_version_format = r.u32()?;
    let n_custom = r.i32()?;
    for _ in 0..n_custom {
        r.guid()?;
        r.i32()?;
    }
    let save_class = r.fstring()?;
    Ok(GvasHeader {
        save_version,
        package_ue4_version,
        engine_version: format!("{major}.{minor}.{patch}.{build}"),
        save_class,
    })
}

/// Reads a tagged-property list until the terminating "None" property.
pub fn parse_property_list(r: &mut Reader) -> Result<BTreeMap<String, Value>> {
    let mut props = BTreeMap::new();
    loop {
        let name = r.fstring()?;
        if name.is_empty() || name == "None" {
            break;
        }
        let value = parse_tagged_value(r)?;
        props.insert(name, value);
    }
    Ok(props)
}

fn parse_tagged_value(r: &mut Reader) -> Result<Value> {
    let type_name = r.fstring()?;
    let size = r.i32()? as usize;
    let _array_index = r.i32()?;

    let mut struct_name = None;
    let mut inner_type = None;
    let mut enum_name = None;
    let mut bool_val = None;

    match type_name.as_str() {
        "StructProperty" => {
            struct_name = Some(r.fstring()?);
            r.guid()?; // struct guid, unused
        }
        "ByteProperty" | "EnumProperty" => {
            enum_name = Some(r.fstring()?);
        }
        "ArrayProperty" | "SetProperty" => {
            inner_type = Some(r.fstring()?);
        }
        "BoolProperty" => {
            bool_val = Some(r.u8()? != 0);
        }
        "MapProperty" => {
            r.fstring()?;
            r.fstring()?;
        }
        _ => {}
    }

    let has_guid = r.u8()?;
    if has_guid != 0 {
        r.bytes(16)?;
    }

    read_value(r, &type_name, size, struct_name, inner_type, enum_name, bool_val)
}

fn read_value(
    r: &mut Reader,
    type_name: &str,
    size: usize,
    struct_name: Option<String>,
    inner_type: Option<String>,
    enum_name: Option<String>,
    bool_val: Option<bool>,
) -> Result<Value> {
    Ok(match type_name {
        "IntProperty" => Value::Int(r.i32()? as i64),
        "UInt32Property" => Value::Int(r.u32()? as i64),
        "Int16Property" => Value::Int(r.i16()? as i64),
        "UInt16Property" => Value::Int(r.u16()? as i64),
        "Int64Property" => Value::Int(r.i64()?),
        "FloatProperty" => Value::Float(r.f32()? as f64),
        "DoubleProperty" => Value::Float(r.f64()?),
        "BoolProperty" => Value::Bool(bool_val.unwrap_or(false)),
        "StrProperty" | "NameProperty" => Value::Str(r.fstring()?),
        "ByteProperty" => match enum_name.as_deref() {
            None | Some("None") => Value::Int(r.u8()? as i64),
            _ => Value::Str(r.fstring()?),
        },
        "EnumProperty" => Value::Str(r.fstring()?),
        "StructProperty" => read_struct(r, struct_name.as_deref().unwrap_or(""), size)?,
        "ArrayProperty" => read_array(r, inner_type.as_deref().unwrap_or(""), size)?,
        _ => {
            // Unknown property type: skip its bytes rather than fail the
            // whole parse (Foxhole occasionally adds fields between patches).
            r.bytes(size)?;
            Value::Raw(format!("<unhandled {type_name}, {size} bytes>"))
        }
    })
}

fn read_struct(r: &mut Reader, struct_name: &str, size: usize) -> Result<Value> {
    let end = r.pos() + size as u64;
    let value = match struct_name {
        "Vector2D" => {
            let x = r.f32()?;
            let y = r.f32()?;
            Value::Vector2D { x, y }
        }
        "Guid" => Value::Str(r.guid()?),
        "DateTime" => Value::Int(r.u64()? as i64),
        _ => Value::Struct(parse_property_list(r)?),
    };
    // Struct fields are size-prefixed; trust `size` over our own parsing in
    // case of an unrecognized nested struct so the outer list stays aligned.
    r.set_pos(end);
    Ok(value)
}

fn read_array(r: &mut Reader, inner_type: &str, size: usize) -> Result<Value> {
    let end = r.pos() + size as u64;
    let count = r.i32()?;
    let mut items = Vec::with_capacity(count.max(0) as usize);

    if inner_type == "StructProperty" {
        // UE4 re-emits a redundant per-array tag header for struct arrays:
        // name, type, size, array index, struct name, struct guid, guid flag.
        r.fstring()?;
        r.fstring()?;
        r.i32()?;
        r.i32()?;
        r.fstring()?;
        r.guid()?;
        if r.u8()? != 0 {
            r.bytes(16)?;
        }
        for _ in 0..count {
            items.push(Value::Struct(parse_property_list(r)?));
        }
    } else {
        for _ in 0..count {
            let v = match inner_type {
                "IntProperty" => Value::Int(r.i32()? as i64),
                "StrProperty" | "NameProperty" => Value::Str(r.fstring()?),
                "ByteProperty" => Value::Int(r.u8()? as i64),
                "FloatProperty" => Value::Float(r.f32()? as f64),
                "Guid" => Value::Str(r.guid()?),
                _ => {
                    // Bail out cleanly for array element types we don't
                    // special-case yet; caller still gets a valid document.
                    r.set_pos(end);
                    items.push(Value::Raw(format!("<unhandled array of {inner_type}>")));
                    break;
                }
            };
            items.push(v);
        }
    }
    r.set_pos(end);
    Ok(Value::Array(items))
}
