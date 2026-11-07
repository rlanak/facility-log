use serde::Serialize;
use std::env;
use std::fs;

use foxhole_save_parser::model::PinnedLocation;

/// Cada local pinado + a coordenada já convertida pra grade do jogo (que é
/// um método, não um campo, então não sai sozinha no `Serialize` derivado).
/// É o contrato lido pelo facility-log (`app/services/save_reader.py`) —
/// mudar nomes de campo aqui quebra a leitura de lá.
#[derive(Serialize)]
struct LocationJson<'a> {
    #[serde(flatten)]
    location: &'a PinnedLocation,
    grid_coordinate: String,
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    // --json: JSON compacto no stdout e nada no stderr em caso de sucesso —
    // é como o app chama. Sem ele, o mesmo conteúdo formatado, pra gente ler.
    let json_mode = args.iter().any(|a| a == "--json");
    let path = args.iter().find(|a| !a.starts_with("--")).cloned().unwrap_or_else(|| {
        eprintln!("uso: foxhole-save-parser [--json] <caminho para o .sav>");
        std::process::exit(1);
    });

    let data = fs::read(&path).unwrap_or_else(|e| {
        eprintln!("erro lendo {path}: {e}");
        std::process::exit(1);
    });

    match foxhole_save_parser::parse_save(&data) {
        Ok(locations) => {
            let out: Vec<LocationJson> = locations
                .iter()
                .map(|l| LocationJson { location: l, grid_coordinate: l.grid_coordinate() })
                .collect();
            if json_mode {
                println!("{}", serde_json::to_string(&out).unwrap());
            } else {
                println!("{}", serde_json::to_string_pretty(&out).unwrap());
                eprintln!("\n{} locais pinados", out.len());
            }
        }
        Err(e) => {
            eprintln!("falha ao interpretar o save: {e}");
            std::process::exit(1);
        }
    }
}
