# tools/save-parser — leitor do save do Foxhole

Lê o save local do jogo (`PlayerMapDataSaveGame`, formato **GVAS** do Unreal Engine 4.24) e extrai os
locais pinados no mapa com o estoque em cache de cada um. Único consumidor: o facility-log
(`app/services/save_reader.py`), que chama o binário como CLI.

```bash
cargo build --release                       # ou: python scripts/build_save_parser.py (na raiz)
foxhole-save-parser --json <arquivo.sav>    # JSON compacto (como o app chama)
foxhole-save-parser <arquivo.sav>           # mesmo conteúdo formatado, pra ler
```

**O JSON é um contrato:** lista de `PinnedLocation` + `grid_coordinate`. Renomear ou remover campo aqui
quebra a leitura no app. O `Dockerfile` da raiz compila esta pasta pra Linux. Validado contra saves
reais, inclusive da v1.67 do jogo.

## Código

- `src/reader.rs` — leitor binário (strings UE com prefixo i32: positivo = UTF-8, negativo = UTF-16LE;
  inteiros; GUID).
- `src/gvas.rs` — parser genérico de propriedades "tagged" do UE4: `StructProperty`, `ArrayProperty`
  (array de struct tem um cabeçalho redundante repetido dentro do array — detalhe não óbvio),
  `IntProperty`, `StrProperty`/`NameProperty`, `ByteProperty`/`EnumProperty`, `BoolProperty`; structs
  `Vector2D`, `DateTime` (ticks .NET/UE) e `Guid`. Tipo não mapeado vira `Value::Raw` em vez de quebrar —
  campo novo do jogo não derruba o parse.
- `src/model.rs` — extrai `PinnedMapToolTipsC` e achata em `PinnedLocation`. Estoque: prefere
  `RecentMapItemDetails`, senão `InitalMapItemDetails` (com o erro de grafia do próprio jogo).
- `src/lib.rs` — `parse_save(bytes) -> Result<Vec<PinnedLocation>, ParseError>`.
- `src/main.rs` — o CLI.

```rust
pub struct PinnedLocation {
    pub map_id: String,                 // ex: "EWorldConquestMapId::WestgateHex"
    pub code_name: String,              // tipo do local, ex: "FacilityTransferMaterial"
    pub coords_normalized: (f32, f32),  // 0.0-1.0 dentro do hex
    pub render_state: String,           // "IconOnly" ou "Expanded"
    pub last_updated_unix: i64,         // de ticks UE
    pub last_updated_iso: String,
    pub stockpile: Vec<StockpileItem>,  // code_name + quantity
}
```

`grid_coordinate()` converte `coords_normalized` pra grade do jogo (A-Q × 1-15, cada quadrado com 9
subcélulas como teclado numérico, ex: "G6k1"), pela documentação da wiki — **não conferido** contra um
pin de coordenada conhecida.

## Comportamento do jogo

- Até 25 pins por facção, que persistem entre sessões e guerras até serem despinados — pin "que ninguém
  lembra" é pin antigo, não bug.
- O estoque em cache só atualiza quando o jogador abre o tooltip do pin; `RenderState` é pista, não
  confirmação.
- O save **não** guarda valores calculados ao vivo pelo cliente (ex: consumo por hora de uma estrutura).
- Nunca commitar `.sav` real.
