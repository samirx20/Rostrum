//! Pictures as the page draws them (assets.rs: loaded and converted into the working space), kept for the process
//! between frames and page shells: a serve session's next frame, a still and a playing frame of the same time, a
//! picture both an `<img>` and an `feImage` read, and every picture again after a `page` swap (a new document has
//! an empty image store) are not read and converted again. Keyed by the URL and, for a local file, its size and
//! modification time (a file written again is a new entry); bounded by bytes (ROSTRUM_MOTION_ASSET_MB, default
//! 512; 0 keeps nothing), the least recently used going first. Pictures may be decoded on several threads at once (a frame's
//! pictures in parallel, the next frames' ahead: serve.rs); one being decoded is not decoded again beside it — a fetch waits
//! for it, a decode ahead skips it.

use std::collections::{HashMap, HashSet};
use std::hash::{Hash, Hasher};
use std::sync::{Condvar, Mutex, OnceLock};

use blitz_traits::net::{Bytes, Url};

/// What an entry is known by: a hash of the URL and the colour it converts into (the session's working space, view and target), its length, and the file's size and modification time (0 for no file).
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Key {
    url: u64,
    len: usize,
    size: u64,
    mtime: u128,
}

struct Kept {
    bytes: Bytes,
    used: u64,
}

pub struct Cache {
    map: HashMap<Key, Kept>,
    total: usize,
    budget: usize,
    clock: u64,
    /// Entries being decoded now (on any thread).
    busy: HashSet<Key>,
}

impl Cache {
    pub fn new(budget: usize) -> Cache {
        Cache { map: HashMap::new(), total: 0, budget, clock: 0, busy: HashSet::new() }
    }

    pub fn get(&mut self, k: &Key) -> Option<Bytes> {
        self.clock += 1;
        let now = self.clock;
        self.map.get_mut(k).map(|e| {
            e.used = now;
            e.bytes.clone()
        })
    }

    /// Keeps `bytes` under `k` (nothing bigger than the whole budget), then drops the least recently used past the budget.
    pub fn put(&mut self, k: Key, bytes: Bytes) {
        if bytes.len() > self.budget {
            return;
        }
        self.clock += 1;
        if let Some(old) = self.map.insert(k, Kept { bytes: bytes.clone(), used: self.clock }) {
            self.total -= old.bytes.len();
        }
        self.total += bytes.len();
        if self.total <= self.budget {
            return;
        }
        let mut order: Vec<(u64, Key)> = self.map.iter().map(|(k, e)| (e.used, *k)).collect();
        order.sort_unstable_by_key(|(used, _)| *used);
        for (_, old) in order {
            if self.total <= self.budget {
                break;
            }
            if let Some(e) = self.map.remove(&old) {
                self.total -= e.bytes.len();
            }
        }
    }

    #[cfg(test)]
    pub fn total(&self) -> usize {
        self.total
    }

    #[cfg(test)]
    pub fn len(&self) -> usize {
        self.map.len()
    }
}

/// The key of `url`: its local file's size and modification time when it names one (`/__local_asset?p=` or file:);
/// None when that file cannot be read (the load then fails and says why).
pub fn key_of(url: &Url, colour: &str) -> Option<Key> {
    let s = url.as_str();
    let mut h = std::collections::hash_map::DefaultHasher::new();
    s.hash(&mut h);
    colour.hash(&mut h);
    let path: Option<std::path::PathBuf> = match url.scheme() {
        "file" => url.to_file_path().ok(),
        "http" | "https" if url.path() == "/__local_asset" => url.query_pairs().find(|(k, _)| k == "p").map(|(_, v)| v.into_owned().into()),
        _ => None,
    };
    let (size, mtime) = match path {
        Some(p) => {
            let m = std::fs::metadata(p).ok()?;
            let t = m.modified().ok().and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok()).map_or(0, |d| d.as_nanos());
            (m.len(), t)
        }
        None => (0, 0),
    };
    Some(Key { url: h.finish(), len: s.len(), size, mtime })
}

fn budget() -> usize {
    std::env::var("ROSTRUM_MOTION_ASSET_MB").ok().and_then(|v| v.trim().parse::<usize>().ok()).unwrap_or(512) << 20
}

/// The cache, and the signal that an entry stopped being decoded.
fn shared() -> &'static (Mutex<Cache>, Condvar) {
    static C: OnceLock<(Mutex<Cache>, Condvar)> = OnceLock::new();
    C.get_or_init(|| (Mutex::new(Cache::new(budget())), Condvar::new()))
}

fn lock() -> std::sync::MutexGuard<'static, Cache> {
    shared().0.lock().unwrap_or_else(|e| e.into_inner())
}

/// An entry being decoded: no longer busy when dropped (made, failed or panicked), and the waiters told.
struct Busy(Key);

impl Drop for Busy {
    fn drop(&mut self) {
        lock().busy.remove(&self.0);
        shared().1.notify_all();
    }
}

/// The picture `url` draws as under `colour` (what its conversion depends on): kept, or made by `make` (and kept when it
/// succeeds). One being made on another thread is waited for, not made again.
pub fn kept(url: &Url, colour: &str, make: impl FnOnce() -> Result<Vec<u8>, String>) -> Result<Bytes, String> {
    let Some(k) = key_of(url, colour) else { return make().map(Bytes::from) };
    let mut c = lock();
    loop {
        if let Some(b) = c.get(&k) {
            return Ok(b);
        }
        if !c.busy.contains(&k) {
            break;
        }
        c = shared().1.wait(c).unwrap_or_else(|e| e.into_inner());
    }
    c.busy.insert(k);
    drop(c);
    let _busy = Busy(k);
    let b = Bytes::from(make()?);
    lock().put(k, b.clone());
    Ok(b)
}

/// A local file written this recently may still be being written (rostrum-3d writes its frames in one `write`, not by rename):
/// a decode ahead waits for it to settle rather than read it half written.
const SETTLE_NS: u128 = 20_000_000;

/// What `warm` did with a picture.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Warmed {
    /// Kept now, or already kept or being made (or not a picture that can be kept).
    Done,
    /// Its local file is not there yet, or was written in the last SETTLE_NS: worth asking again soon (a 3D pass the host
    /// named ahead of its render).
    NotYet,
}

/// Makes and keeps the picture `url` draws as under `colour` ahead of its fetch, unless it is kept or being made; a failure is
/// dropped (the fetch makes it again and reports it).
pub fn warm(url: &Url, colour: &str, make: impl FnOnce() -> Result<Vec<u8>, String>) -> Warmed {
    let Some(k) = key_of(url, colour) else { return Warmed::NotYet };
    if k.mtime != 0 && std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(false, |now| now.as_nanos().saturating_sub(k.mtime) < SETTLE_NS) {
        return Warmed::NotYet;
    }
    {
        let mut c = lock();
        if c.get(&k).is_some() || c.busy.contains(&k) {
            return Warmed::Done;
        }
        c.busy.insert(k);
    }
    let _busy = Busy(k);
    if let Ok(b) = make() {
        lock().put(k, Bytes::from(b));
    }
    Warmed::Done
}

/// Whether `url` (under `colour`) is kept now: a frame's own fetch of it will not decode.
pub fn is_kept(url: &Url, colour: &str) -> bool {
    key_of(url, colour).is_some_and(|k| lock().map.contains_key(&k))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn key(n: u64) -> Key {
        Key { url: n, len: 1, size: 0, mtime: 0 }
    }

    #[test]
    fn keeps_within_its_budget_dropping_the_least_recently_used() {
        let mut c = Cache::new(10);
        c.put(key(1), Bytes::from(vec![0u8; 4]));
        c.put(key(2), Bytes::from(vec![0u8; 4]));
        assert!(c.get(&key(1)).is_some());
        c.put(key(3), Bytes::from(vec![0u8; 4]));
        assert!(c.get(&key(2)).is_none(), "2 was used least recently");
        assert!(c.get(&key(1)).is_some() && c.get(&key(3)).is_some());
        assert_eq!(c.total(), 8);
        c.put(key(4), Bytes::from(vec![0u8; 11]));
        assert_eq!(c.len(), 2, "bigger than the budget: not kept");
    }

    #[test]
    fn a_picture_made_ahead_is_a_hit_and_one_being_made_is_not_made_twice() {
        let dir = std::env::temp_dir().join(format!("rostrum-asset-warm-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let f = dir.join("w.png");
        std::fs::write(&f, b"w").unwrap();
        // Past SETTLE_NS: a file written this instant is not decoded ahead yet.
        std::thread::sleep(std::time::Duration::from_millis(40));
        let url = Url::parse(&format!("http://rostrum.local/__local_asset?p={}", f.display())).unwrap();
        let made = std::sync::atomic::AtomicUsize::new(0);
        let make = || {
            made.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            std::thread::sleep(std::time::Duration::from_millis(150));
            Ok(vec![7u8; 8])
        };
        std::thread::scope(|s| {
            s.spawn(|| warm(&url, "warm-test", make));
            std::thread::sleep(std::time::Duration::from_millis(30));
            s.spawn(|| warm(&url, "warm-test", make));
            assert_eq!(kept(&url, "warm-test", make).unwrap().to_vec(), vec![7u8; 8]);
        });
        assert_eq!(made.load(std::sync::atomic::Ordering::SeqCst), 1, "the fetch waited for the decode ahead; the second warm skipped it");
        warm(&url, "warm-test", || Err("not again".into()));
        assert_eq!(made.load(std::sync::atomic::Ordering::SeqCst), 1);
        assert!(is_kept(&url, "warm-test"));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_file_not_written_yet_or_just_written_is_not_yet() {
        let dir = std::env::temp_dir().join(format!("rostrum-asset-notyet-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let f = dir.join("pass.rhf");
        let url = Url::parse(&format!("http://rostrum.local/__local_asset?p={}", f.display())).unwrap();
        assert_eq!(warm(&url, "notyet", || Ok(vec![1])), Warmed::NotYet, "no file yet");
        std::fs::write(&f, b"x").unwrap();
        assert_eq!(warm(&url, "notyet", || Ok(vec![1])), Warmed::NotYet, "written this instant");
        assert!(!is_kept(&url, "notyet"));
        std::thread::sleep(std::time::Duration::from_millis(40));
        assert_eq!(warm(&url, "notyet", || Ok(vec![1])), Warmed::Done);
        assert!(is_kept(&url, "notyet"));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_rewritten_file_is_a_new_key() {
        let dir = std::env::temp_dir().join(format!("rostrum-asset-cache-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let f = dir.join("a.png");
        std::fs::write(&f, b"one").unwrap();
        let url = Url::parse(&format!("http://rostrum.local/__local_asset?p={}", f.display())).unwrap();
        let a = key_of(&url, "c").unwrap();
        assert_eq!(key_of(&url, "c"), Some(a));
        std::fs::write(&f, b"three").unwrap();
        assert_ne!(key_of(&url, "c"), Some(a));
        std::fs::remove_dir_all(&dir).ok();
        assert_eq!(key_of(&url, "c"), None, "a missing file has no key");
    }
}
