//! Skia's compiled GPU programs kept on disk between runs (Skia's `GrContextOptions::PersistentCache`), so a draw kind
//! met before (a turned picture, a blur, a blend) costs a program load (~0.1 ms) instead of a driver compile (10-100 ms
//! each, paid on the screen's first frame of that kind). Skia stores each program it builds here (as the driver's
//! binary, `ShaderCacheStrategy::BackendBinary`) and asks for it by its key before building one; a binary the driver
//! refuses (a new driver) is built again from source and stored again.
//!
//! One folder per engine build and GPU (`~/.rostrum/cache/2d-programs/<build>-<gpu>`): a new build never reads an
//! older build's programs; folders not used for PRUNE_DAYS are deleted. At most MOST_BYTES are stored.
//!
//! skia-safe does not wrap the C++ interface yet, so the object Skia calls is made here: a vtable of `extern "system"`
//! functions in the Windows x64 C++ layout (destructor, `load`, then `store`, whose two overloads both point at one
//! function taking the longer form: the shorter call leaves the description's register unused). `load` returns an
//! `sk_sp<SkData>` through the hidden result pointer MSVC passes for a class returned by a member function.

use std::ffi::c_void;
use std::mem::ManuallyDrop;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

use skia_safe::Data;

/// The most bytes of programs kept for one build (a scene's few hundred programs are a few MB).
const MOST_BYTES: usize = 64 << 20;
/// A folder of another build not used for this many days is deleted.
const PRUNE_DAYS: u64 = 14;

#[repr(C)]
struct VTable {
    drop: extern "system" fn(*mut Cache, u32) -> *mut Cache,
    load: extern "system" fn(*mut Cache, *mut *mut c_void, *const c_void) -> *mut *mut c_void,
    store: [extern "system" fn(*mut Cache, *const c_void, *const c_void, *const c_void); 2],
}

/// The C++ object: its vtable first.
#[repr(C)]
struct Cache {
    vtable: &'static VTable,
    dir: PathBuf,
    bytes: AtomicUsize,
}

/// Programs loaded from and stored to disk by this process (the test reads them).
static LOADS: AtomicUsize = AtomicUsize::new(0);
static STORES: AtomicUsize = AtomicUsize::new(0);

static VTABLE: VTable = VTable { drop: never_dropped, load, store: [store, store] };

/// Skia only holds a pointer to the cache (the process's one, never freed): its destructor is never called.
extern "system" fn never_dropped(this: *mut Cache, _flags: u32) -> *mut Cache {
    this
}

/// The bytes of an `SkData` Skia lends.
fn bytes<'a>(data: *const c_void) -> &'a [u8] {
    // `Data` is a pointer to the SkData (skia-safe's RCHandle): borrowed here, never unreferenced.
    let d = ManuallyDrop::new(unsafe { std::mem::transmute::<*const c_void, Data>(data) });
    let b: &[u8] = d.as_bytes();
    unsafe { std::slice::from_raw_parts(b.as_ptr(), b.len()) }
}

fn file(dir: &Path, key: &[u8]) -> PathBuf {
    // FNV-1a over the key: the file's name (the key itself is stored first and checked on load).
    let h = key.iter().fold(0xcbf2_9ce4_8422_2325u64, |h, &b| (h ^ b as u64).wrapping_mul(0x100_0000_01b3));
    dir.join(format!("{h:016x}.bin"))
}

extern "system" fn load(this: *mut Cache, out: *mut *mut c_void, key: *const c_void) -> *mut *mut c_void {
    let cache = unsafe { &*this };
    let key = bytes(key);
    let found = std::fs::read(file(&cache.dir, key)).ok().and_then(|b| {
        let n = u32::from_le_bytes(b.get(..4)?.try_into().ok()?) as usize;
        (b.get(4..4 + n)? == key).then(|| Data::new_copy(&b[4 + n..]))
    });
    LOADS.fetch_add(found.is_some() as usize, Ordering::Relaxed);
    // The result's reference goes to Skia's sk_sp.
    unsafe { *out = found.map_or(std::ptr::null_mut(), |d| std::mem::transmute::<Data, *mut c_void>(d)) };
    out
}

extern "system" fn store(this: *mut Cache, key: *const c_void, data: *const c_void, _description: *const c_void) {
    let cache = unsafe { &*this };
    let (key, data) = (bytes(key), bytes(data));
    let n = 4 + key.len() + data.len();
    if cache.bytes.fetch_add(n, Ordering::Relaxed) + n > MOST_BYTES {
        return;
    }
    let mut b = Vec::with_capacity(n);
    b.extend_from_slice(&(key.len() as u32).to_le_bytes());
    b.extend_from_slice(key);
    b.extend_from_slice(data);
    // Written whole, then renamed into place: another engine (an export's workers, a second window) reads it whole or not at all.
    let path = file(&cache.dir, key);
    let tmp = path.with_extension(format!("{}.tmp", std::process::id()));
    if std::fs::write(&tmp, &b).is_err() || std::fs::rename(&tmp, &path).is_err() {
        let _ = std::fs::remove_file(&tmp);
    } else {
        STORES.fetch_add(1, Ordering::Relaxed);
    }
}

/// The process's cache for the GPU named `renderer`, made on first use (None when no folder can be made: programs are
/// then built each run, as before).
fn get(renderer: &str) -> Option<*mut c_void> {
    static CACHE: std::sync::OnceLock<Option<usize>> = std::sync::OnceLock::new();
    let p = CACHE.get_or_init(|| {
        let home = std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME"))?;
        let root = Path::new(&home).join(".rostrum").join("cache").join("2d-programs");
        // The build: the program file's size and time (every build differs); the GPU: its name.
        let exe = std::env::current_exe().ok()?.metadata().ok()?;
        let built = exe.modified().ok()?.duration_since(std::time::UNIX_EPOCH).ok()?.as_secs();
        let gpu = renderer.bytes().fold(0u32, |h, b| h.wrapping_mul(31).wrapping_add(b as u32));
        let dir = root.join(format!("{built:x}-{:x}-{gpu:08x}", exe.len()));
        std::fs::create_dir_all(&dir).ok()?;
        prune(&root, &dir);
        let bytes = std::fs::read_dir(&dir).ok()?.filter_map(|e| e.ok()?.metadata().ok()).map(|m| m.len() as usize).sum();
        let cache = Box::new(Cache { vtable: &VTABLE, dir, bytes: AtomicUsize::new(bytes) });
        Some(Box::into_raw(cache) as usize)
    });
    p.map(|p| p as *mut c_void)
}

/// Marks `keep` used now and deletes the folders of other builds not used for PRUNE_DAYS (never read again).
fn prune(root: &Path, keep: &Path) {
    const USED: &str = "used";
    let _ = std::fs::write(keep.join(USED), b"");
    let old = std::time::SystemTime::now() - std::time::Duration::from_secs(PRUNE_DAYS * 86400);
    for e in std::fs::read_dir(root).into_iter().flatten().flatten() {
        let used = std::fs::metadata(e.path().join(USED)).and_then(|m| m.modified()).or_else(|_| e.metadata().and_then(|m| m.modified()));
        if e.path() != keep && used.is_ok_and(|t| t < old) {
            let _ = std::fs::remove_dir_all(e.path());
        }
    }
}

/// Puts the cache into `opts` (before the context is made). skia-safe keeps the field private: it is written at its
/// place in the C++ struct, checked against the struct's size.
pub fn attach(opts: &mut skia_safe::gpu::ContextOptions, renderer: &str) {
    const SIZE: usize = 144; // sizeof(GrContextOptions) in this Skia
    const AT: usize = 24; // offsetof(GrContextOptions, fPersistentCache)
    // The vtable above is the Windows x64 (MSVC) layout; another ABI (the Mac) builds its programs each run until it has its own.
    if !cfg!(all(windows, target_arch = "x86_64")) {
        return;
    }
    assert_eq!(std::mem::size_of::<skia_safe::gpu::ContextOptions>(), SIZE, "GrContextOptions changed: check fPersistentCache's place");
    let Some(cache) = get(renderer) else { return };
    unsafe {
        let field = (opts as *mut _ as *mut u8).add(AT) as *mut *mut c_void;
        debug_assert!((*field).is_null());
        *field = cache;
    }
    opts.shader_cache_strategy = skia_safe::gpu::ganesh::context_options::ShaderCacheStrategy::BackendBinary;
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Skia calls the cache made here (its C++ layout is right): a program built in one context is stored, and a second
    /// context loads it instead of compiling it (a wrong layout would crash, or silently never cache).
    #[test]
    fn a_program_built_once_is_loaded_by_the_next_context() {
        let draw = || {
            let mut p = crate::painter::Painter::gpu(64, 64, None).expect("GPU");
            p.paint(false, |_| {}).unwrap();
            p.warm(skia_safe::M44::rotate(skia_safe::V3::new(0.0, 0.0, 1.0), 0.3), (64, 64), |_| {}).unwrap();
            p.read().unwrap();
        };
        let before = (LOADS.load(Ordering::Relaxed), STORES.load(Ordering::Relaxed));
        draw();
        let first = (LOADS.load(Ordering::Relaxed), STORES.load(Ordering::Relaxed));
        assert!(first.0 + first.1 > before.0 + before.1, "the first context neither loaded nor stored a program");
        draw();
        let second = LOADS.load(Ordering::Relaxed);
        assert!(second > first.0, "the second context loaded no program");
    }
}
