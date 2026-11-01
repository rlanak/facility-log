use serde::Serialize;
use std::env;
use std::fs;

use foxhole_save_parser::model::PinnedLocation;

/// Formato de saída do `--json`: o `PinnedLocation` cru + a coordenada já
/// convertida pra grade do jogo (que é um método, não um campo, então não
/// sai sozinha no `Serialize` derivado). É o contrato lido pelo
/// facility-log (`app/services/save_reader.py`) — mudar nomes de campo
/// aqui quebra a leitura de lá.
#[derive(Serialize)]
struct LocationJson<'a> {
    #[serde(flatten)]
    location: &'a PinnedLocation,
    grid_coordinate: String,
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let show_all = args.iter().any(|a| a == "--all");
    // Modo máquina: todos os locais pinados, JSON compacto no stdout, nada
    // no stderr em caso de sucesso — pensado pra ser chamado por outro
    // programa, não por gente no terminal.
    let json_mode = args.iter().any(|a| a == "--json");
    let path = args.iter().find(|a| !a.starts_with("--")).cloned().unwrap_or_else(|| {
        eprintln!("uso: foxhole-save-parser [--all | --json] <caminho para o .sav>");
        eprintln!("  (sem --all, mostra só túneis de manutenção com mSupps em cache)");
        eprintln!("  (--json: todos os locais, JSON compacto com grid_coordinate, pra uso por outro programa)");
        std::process::exit(1);
    });

    let data = fs::read(&path).unwrap_or_else(|e| {
        eprintln!("erro lendo {path}: {e}");
        std::process::exit(1);
    });

    match foxhole_save_parser::parse_save(&data) {
        Ok(locations) => {
            if json_mode {
                let out: Vec<LocationJson> = locations
                    .iter()
                    .map(|l| LocationJson { location: l, grid_coordinate: l.grid_coordinate() })
                    .collect();
                println!("{}", serde_json::to_string(&out).unwrap());
            } else if show_all {
                println!("{}", serde_json::to_string_pretty(&locations).unwrap());
                eprintln!("\n{} locais pinados encontrados (todos os tipos)", locations.len());
            } else {
                let tunnels = foxhole_save_parser::model::maintenance_tunnels_with_msupps(&locations);
                println!("{}", serde_json::to_string_pretty(&tunnels).unwrap());
                eprintln!("\n{} túneis de manutenção com mSupps em cache", tunnels.len());
                eprintln!("({} locais pinados no total; use --all pra ver todos os tipos)", locations.len());
            }
        }
        Err(e) => {
            eprintln!("falha ao interpretar o save: {e}");
            std::process::exit(1);
        }
    }
}
