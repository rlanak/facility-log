use crate::gvas::Value;
use serde::Serialize;
use std::collections::BTreeMap;

/// One stockpile line item cached inside a pinned location (e.g. "FacilityMaterials1": 820).
#[derive(Debug, Clone, Serialize)]
pub struct StockpileItem {
    pub code_name: String,
    pub quantity: i64,
}

/// A single location the player pinned on the map, with whatever resource
/// snapshot the game cached the last time they looked at it.
#[derive(Debug, Clone, Serialize)]
pub struct PinnedLocation {
    pub map_id: String,
    pub code_name: String,
    pub coords_normalized: (f32, f32),
    pub render_state: String,
    /// Ticks since 0001-01-01 (UE FDateTime), converted to Unix seconds.
    pub last_updated_unix: i64,
    pub last_updated_iso: String,
    /// Flattened, most-recent-known stockpile items across the entry's
    /// initial/recent detail snapshots (Foxhole keeps both; we prefer
    /// "RecentMapItemDetails" when it has data, else "InitalMapItemDetails").
    pub stockpile: Vec<StockpileItem>,
}

impl PinnedLocation {
    /// Converte a coordenada normalizada (0.0-1.0 dentro do hex) pro
    /// sistema de grade do próprio jogo, tipo "G6k1": segundo a wiki
    /// oficial (Map_Screen > Map Coordinates), cada região tem uma grade
    /// de letras A-Q (17 colunas) por números 1-15 (15 linhas), e cada
    /// quadrado grande dessa grade é subdividido em 9 menores, numerados
    /// como um teclado numérico (1-9, estilo telefone: 1 no canto
    /// superior esquerdo, 9 no inferior direito).
    ///
    /// **Não verificado byte a byte** contra o jogo — é a interpretação
    /// mais direta da documentação oficial aplicada ao
    /// `coords_normalized` que já temos, mas nunca comparamos um valor
    /// convertido aqui com o que o jogo mostra pra um pin conhecido.
    /// Antes de confiar 100%, vale conferir: pegue um pin com
    /// coordenada conhecida no jogo (Ctrl+clique no mapa copia a
    /// coordenada pro chat) e compare com o que essa função devolve pra
    /// aquele mesmo pin.
    pub fn grid_coordinate(&self) -> String {
        const COLUMNS: usize = 17; // A a Q
        const ROWS: usize = 15; // 1 a 15

        let (x, y) = self.coords_normalized;
        let x = x.clamp(0.0, 0.999_999);
        let y = y.clamp(0.0, 0.999_999);

        let col_f = x * COLUMNS as f32;
        let row_f = y * ROWS as f32;
        let col = (col_f as usize).min(COLUMNS - 1);
        let row = (row_f as usize).min(ROWS - 1);

        // Posição dentro do quadrado grande (0.0-1.0 em cada eixo), pra
        // achar a subcélula do teclado numérico.
        let local_x = col_f - col as f32;
        let local_y = row_f - row as f32;
        let keypad_col = ((local_x * 3.0) as usize).min(2);
        let keypad_row = ((local_y * 3.0) as usize).min(2);
        let keypad = keypad_row * 3 + keypad_col + 1;

        let letter = (b'A' + col as u8) as char;
        format!("{letter}{}k{keypad}", row + 1)
    }
}

const TICKS_PER_SECOND: i64 = 10_000_000;
/// Seconds between 0001-01-01T00:00:00 (FDateTime epoch) and 1970-01-01 (Unix epoch).
const EPOCH_OFFSET_SECONDS: i64 = 62_135_596_800;

fn ticks_to_unix(ticks: i64) -> i64 {
    ticks / TICKS_PER_SECOND - EPOCH_OFFSET_SECONDS
}

fn extract_stockpile(detail: &BTreeMap<String, Value>) -> Vec<StockpileItem> {
    detail
        .get("StockpileInfo")
        .and_then(Value::as_struct)
        .and_then(|s| s.get("Items"))
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_struct)
                .filter_map(|m| {
                    let code_name = m.get("CodeName")?.as_str()?.to_string();
                    let quantity = m.get("Quantity")?.as_i64()?;
                    Some(StockpileItem { code_name, quantity })
                })
                .collect()
        })
        .unwrap_or_default()
}

/// Walks the parsed root property map and extracts every pinned location
/// under `PinnedMapToolTipsC`, flattening what the app needs (stockpile
/// snapshot, coords, hex, last-seen time).
pub fn extract_pinned_locations(root: &BTreeMap<String, Value>) -> Vec<PinnedLocation> {
    let Some(entries) = root.get("PinnedMapToolTipsC").and_then(Value::as_array) else {
        return Vec::new();
    };

    entries
        .iter()
        .filter_map(Value::as_struct)
        .filter_map(|entry| {
            let map_id = entry.get("MapId")?.as_str()?.to_string();
            let code_name = entry.get("CodeName")?.as_str()?.to_string();
            let render_state = entry
                .get("RenderState")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let coords = entry.get("NormalizedMapCoords").and_then(|v| match v {
                Value::Vector2D { x, y } => Some((*x, *y)),
                _ => None,
            })?;
            let ticks = entry.get("LastUpdated").and_then(Value::as_i64).unwrap_or(0);
            let last_updated_unix = ticks_to_unix(ticks);
            let last_updated_iso = unix_to_iso(last_updated_unix);

            let recent = entry
                .get("RecentMapItemDetails")
                .and_then(Value::as_struct)
                .map(extract_stockpile)
                .unwrap_or_default();
            let initial = entry
                .get("InitalMapItemDetails")
                .and_then(Value::as_struct)
                .map(extract_stockpile)
                .unwrap_or_default();
            let stockpile = if !recent.is_empty() { recent } else { initial };

            Some(PinnedLocation {
                map_id,
                code_name,
                coords_normalized: coords,
                render_state,
                last_updated_unix,
                last_updated_iso,
                stockpile,
            })
        })
        .collect()
}

/// UTC ISO-8601 string for display.
fn unix_to_iso(unix_seconds: i64) -> String {
    use std::time::{Duration, UNIX_EPOCH};
    let t = UNIX_EPOCH + Duration::from_secs(unix_seconds.max(0) as u64);
    let datetime: chrono::DateTime<chrono::Utc> = t.into();
    datetime.format("%Y-%m-%dT%H:%M:%SZ").to_string()
}
