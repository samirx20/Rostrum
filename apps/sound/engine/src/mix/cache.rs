//! The sound engine's share of Rostrum's one cache (src/engine/cache/cache.ts): `<root>/sound/<sub>/`, the
//! root being ROSTRUM_CACHE_DIR, else ~/.rostrum/cache. Nothing is kept with ROSTRUM_CACHE_MB=0, nor in
//! tests (they pass their own folder). The host caps the root as a whole after each job (cacheTrim.ts,
//! least recently used first); here a hit renews its file's time and a write lands whole or not at all.

use std::path::{Path, PathBuf};

/// The folder of one of the engine's caches (`tracks`, `stretch`, `plugin`), or None when nothing is kept.
pub fn dir(sub: &str) -> Option<PathBuf> {
    if cfg!(test) || std::env::var("ROSTRUM_CACHE_MB").is_ok_and(|v| v.trim().parse::<f64>() == Ok(0.0)) {
        return None;
    }
    let root = match std::env::var_os("ROSTRUM_CACHE_DIR").filter(|v| !v.is_empty()) {
        Some(d) => PathBuf::from(d),
        None => PathBuf::from(std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME"))?).join(".rostrum").join("cache"),
    };
    Some(root.join("sound").join(sub))
}

/// A stored file's bytes, marked as just used; None when absent.
pub fn read(dir: &Path, name: &str) -> Option<Vec<u8>> {
    let file = dir.join(name);
    let bytes = std::fs::read(&file).ok()?;
    let _ = std::fs::File::options().write(true).open(&file).and_then(|f| f.set_modified(std::time::SystemTime::now()));
    Some(bytes)
}

/// Removes its file when dropped (a write that did not finish, on any path, panics included).
struct Scratch(PathBuf);

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

/// Stores a file under its name: written beside it, then renamed into place, so a reader never sees half a
/// file. A cache that cannot be written only costs the next render the same work.
pub fn write(dir: &Path, name: &str, bytes: &[u8]) {
    let file = dir.join(name);
    let tmp = Scratch(dir.join(format!("{name}.{}.tmp", std::process::id())));
    if std::fs::create_dir_all(dir).is_ok() && std::fs::write(&tmp.0, bytes).is_ok() {
        let _ = std::fs::rename(&tmp.0, &file);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn writes_whole_reads_back_and_renews_the_time() {
        let d = std::env::temp_dir().join(format!("rostrum-cache-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        assert!(dir("tracks").is_none(), "tests keep nothing in the user's cache");
        write(&d, "a.f32", &[1, 2, 3]);
        let names: Vec<_> = std::fs::read_dir(&d).unwrap().flatten().map(|e| e.file_name()).collect();
        assert_eq!(names, vec![std::ffi::OsString::from("a.f32")], "no scratch left");
        let old = std::time::SystemTime::now() - std::time::Duration::from_secs(3600);
        std::fs::File::options().write(true).open(d.join("a.f32")).unwrap().set_modified(old).unwrap();
        assert_eq!(read(&d, "a.f32"), Some(vec![1, 2, 3]));
        assert!(std::fs::metadata(d.join("a.f32")).unwrap().modified().unwrap() > old, "a hit is recent");
        assert_eq!(read(&d, "b.f32"), None);
        let _ = std::fs::remove_dir_all(d);
    }
}
