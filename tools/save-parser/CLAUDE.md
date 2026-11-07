# CLAUDE.md — tools/save-parser (leitor do save do Foxhole)

> Este código veio do repo `foxhole-msupps-parser`, que foi **aposentado em 31/10/2026** junto com
> o `foxhole-msupps-tray` e todo o acompanhamento de mSupps (os dois repos/pastas foram apagados).
> O parser foi movido pra dentro do facility-log porque é o que lê o estoque de pins (ex: Material
> Transfer Stations) do save do jogo. Crate/binário renomeados pra `foxhole-save-parser`. O
> histórico abaixo menciona o tray e mSupps — é contexto de como o formato foi decifrado, não
> funcionalidade atual. O contexto do app em si está no `CLAUDE.md` da raiz do facility-log.

## O que é

Lê o save local do jogo **Foxhole** (`PlayerMapDataSaveGame`, formato **GVAS** do Unreal Engine
4.24) e extrai os locais pinados no mapa com o estoque em cache de cada um.

**Único consumidor: o facility-log**, que chama o binário como CLI —
`foxhole-save-parser --json <save>` imprime **todos** os locais pinados em JSON compacto (o
`PinnedLocation` serializado + `grid_coordinate`). Esse formato é um contrato:
`app/services/save_reader.py` lê esses campos, então renomear/remover campo aqui quebra lá. O
`.exe` do app embute o binário via `scripts/prepare_save_parser_vendor.py` (roda
`cargo build --release` aqui e copia pra `vendor/save-parser/`) — depois de mudar o parser, rode
esse script de novo. O `Dockerfile` compila esta pasta pra Linux. Validado contra o save da v1.67
do jogo (out/2026): formato não mudou.

## Como foi validado

Diferente do app Tauri (que não pôde ser compilado no ambiente onde foi
escrito), **este parser foi testado ponta a ponta contra o save real do
usuário** logo na primeira versão — rodei o binário compilado aqui mesmo
contra o arquivo `.sav` que ele enviou, e os números batiam com o que ele
via no jogo/no bot de Discord do regimento. Depois disso, ele também
rodou (`cargo run --release`) no PC dele várias vezes com sucesso. É a
parte mais confiável de todo o projeto.

## Como o formato foi decifrado

Não existe (ou não achamos) uma lib Rust madura pra ler GVAS do Foxhole
especificamente — existem libs genéricas de GVAS (tentei `pygvas` em
Python primeiro, mas tinha um bug de import quebrado no pacote publicado).
Decidi escrever um parser do zero, especificamente pro subconjunto de
tipos que o Foxhole usa:

1. Header GVAS padrão (magic `GVAS`, versões, engine `4.24.3.0`, nome da
   classe `/Script/War.PlayerMapDataSaveGame`)
2. Lista de propriedades "tagged" (o sistema de serialização de
   propriedades do UE4): cada propriedade tem nome, tipo, tamanho, e dado
   específico do tipo. Tipos vistos no Foxhole: `StructProperty`,
   `ArrayProperty` (inclusive array-de-struct, que tem um cabeçalho
   redundante emitido de novo dentro do próprio array — detalhe não-óbvio
   do formato), `IntProperty`, `StrProperty`/`NameProperty`,
   `ByteProperty`/`EnumProperty`, `BoolProperty`.
3. Structs especiais tratados manualmente: `Vector2D` (as coordenadas),
   `DateTime` (ticks .NET/UE), `Guid`.

Tipos de propriedade não mapeados não quebram o parse — são lidos como
bytes crus e devolvidos como `Value::Raw(...)` (ver `gvas.rs`). Isso
significa que updates do jogo que adicionem campos novos não derrubam o
parser, só não trazem os campos novos até serem mapeados.

## Descoberta importante: o que NÃO está no save

Fomos procurados pelo usuário pra ver se o número de "consumo por hora"
que aparece no painel *Maintenance Settings* do jogo (contando estruturas
num raio configurável) estava salvo em algum lugar. Fizemos uma busca por
todas as strings ASCII do arquivo `.sav` procurando por
consumption/rate/hour/range/decay — **não existe nada disso**. Esse
número é calculado ao vivo pelo cliente do jogo, olhando o mundo ao redor
da estrutura, não é persistido. Isso mudou o design do app Tauri pra
incluir uma entrada manual de taxa (ver `CLAUDE.md` do tray). Se um dia
alguém quiser confirmar isso nas próprias notas do jogo:
- https://foxhole.wiki.gg/wiki/Maintenance_Supplies
- https://foxhole.wiki.gg/wiki/Decay
- https://foxhole.wiki.gg/wiki/Maintenance_Tunnel

## Estrutura do código

- `src/reader.rs` — leitor binário de baixo nível (strings UE com prefixo
  de tamanho i32 positivo=UTF-8/negativo=UTF-16LE, inteiros, GUID)
- `src/gvas.rs` — parser genérico da árvore de propriedades — não é
  específico do Foxhole, entende qualquer save UE4 com esse esquema
- `src/model.rs` — específico do domínio: extrai `PinnedMapToolTipsC` e
  achata pra `PinnedLocation`; também tem
  `maintenance_tunnels_with_msupps()`, o filtro que o app tray usa (só
  túneis de manutenção com estoque de mSupps — decisão explícita do
  usuário de escopo, não uma limitação técnica; o parser em si (`Value`,
  `parse_property_list`) continua genérico o suficiente pra extrair
  qualquer outro tipo de recurso/local se o escopo mudar)
- `src/lib.rs` — ponto de entrada público: `parse_save(bytes) ->
  Result<Vec<PinnedLocation>, ParseError>`
- `src/main.rs` — CLI fino (`cargo run --release -- [--all]
  <caminho.sav>`) só pra testar sem precisar do app Tauri

## Formato de dados de um `PinnedLocation`

```rust
pub struct PinnedLocation {
    pub map_id: String,              // ex: "EWorldConquestMapId::SableportHex"
    pub code_name: String,           // ex: "MaintenanceTunnel", "Seaport"
    pub coords_normalized: (f32, f32), // 0.0-1.0 dentro do hex — NÃO é a
                                      // grade letra+número que o jogo
                                      // mostra no mapa, não sabemos converter
    pub render_state: String,        // "IconOnly" ou "Expanded" — ver nota
                                      // sobre pins abaixo
    pub last_updated_unix: i64,      // convertido de ticks .NET/UE
    pub last_updated_iso: String,
    pub stockpile: Vec<StockpileItem>, // CodeName + Quantity, ex. "MaintenanceSupplies": 4820
}
```

## Nota sobre o mecanismo de pins do jogo (relevante pra qualquer expansão)

O Foxhole permite até 25 pins fixados por facção, que **persistem entre
sessões** até serem desafixados manualmente (Update 1.64). Isso já causou
confusão no uso real: o usuário via túneis no app que "não lembrava de
ter pinado" — eram pins antigos de guerras passadas. Não é bug do parser,
é o comportamento real do jogo. Também não confirmamos experimentalmente
se o valor em cache (`Quantity`) atualiza só por ter o pin fixado, ou se
precisa abrir/expandir o tooltip no mapa pra disparar uma atualização —
o campo `RenderState` (`IconOnly` vs `Expanded`) é uma pista, não uma
confirmação.

## Se for expandir o parser

- Pra outros tipos de recurso além de `MaintenanceSupplies`: já dá pra
  fazer, `StockpileItem` já é genérico (`code_name` + `quantity`) — só
  ajustar o filtro em `maintenance_tunnels_with_msupps()` ou criar um
  filtro novo ao lado dele.
- Pra outros tipos de save do Foxhole (não só `PlayerMapDataSaveGame`):
  o parser genérico (`gvas.rs`) deveria funcionar, mas o `model.rs`
  precisaria de uma função de extração nova pra qualquer struct raiz
  diferente.
- Nunca comite arquivos `.sav` reais no repo (dados de save do jogo) —
  já está no `.gitignore`.
