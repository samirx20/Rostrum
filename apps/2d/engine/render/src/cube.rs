//! `rostrum2d-render cube <file.cube> <table.f32>`: the host's `.cube` files read by the one parser
//! (rostrum-color `Cube`), so TypeScript never parses a LUT itself (docs/phase0/COLOUR_WAVE_B.md, C7).
//! Prints `{"kind": "1d" | "3d", "size", "domainMin", "domainMax", "title"}` and writes the table as
//! little-endian f32 RGB triples, red fastest; a malformed file exits 1 with its line number.

use rostrum_color::lut::Lut;
use rostrum_color::Cube;
use serde_json::json;

pub fn run(args: &[String]) {
    let [input, table] = args else {
        eprintln!("usage: rostrum2d-render cube <file.cube> <table.f32>");
        std::process::exit(2);
    };
    match read(input, table) {
        Ok(header) => println!("{header}"),
        Err(e) => {
            eprintln!("{input}: {e}");
            std::process::exit(1);
        }
    }
}

fn read(input: &str, table: &str) -> Result<serde_json::Value, String> {
    let text = std::fs::read_to_string(input).map_err(|e| e.to_string())?;
    let cube = Cube::parse(&text).map_err(|e| e.to_string())?;
    let (kind, size, min, max, data) = match &cube.lut {
        Lut::D1(l) => ("1d", l.data.len(), l.min, l.max, &l.data),
        Lut::D3(l) => ("3d", l.size, l.min, l.max, &l.data),
    };
    let bytes: Vec<u8> = data.iter().flatten().flat_map(|v| v.to_le_bytes()).collect();
    std::fs::write(table, bytes).map_err(|e| format!("{table}: {e}"))?;
    Ok(json!({ "kind": kind, "size": size, "domainMin": min, "domainMax": max, "title": cube.title }))
}
