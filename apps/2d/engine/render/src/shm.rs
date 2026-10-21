//! Frames for the live canvas in shared memory (`frame` with `pixels: true`; ENGINE_CONTRACT.md § 1): the engine
//! writes each frame's output pixels straight into a named block of memory the canvas maps too, so nothing goes
//! through the pipe and the canvas reads the pixels where they are.
//!
//! The block has two slots of one frame each, used in turn: a frame goes into the slot the frame before it didn't
//! use, so the canvas can still read frame n while frame n + 1 is drawn. The canvas must be done with a slot before
//! it asks for the frame after next. The reply names the block, the slot's offset and the frame's sequence number.
//!
//! Windows: a named file mapping backed by the page file (`Local\rostrum2d-<pid>-<n>`); a reader opens it by name
//! (Python: `mmap.mmap(-1, size, tagname=name)`; Qt: `QSharedMemory` with a native key, or `OpenFileMappingW`).
//! Mac (to do): `shm_open` + `mmap` with the same layout, the name `/rostrum2d-<pid>-<n>`.

use serde_json::{json, Value};

/// The block and where the next frame goes.
pub struct Shm {
    map: Mapping,
    name: String,
    slot_bytes: usize,
    seq: u64,
}

impl Shm {
    /// A block holding two frames of `frame_bytes` each (a new name for every block the process makes).
    pub fn new(frame_bytes: usize) -> Result<Self, String> {
        static N: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);
        let n = N.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let name = format!("Local\\rostrum2d-{}-{n}", std::process::id());
        let map = Mapping::create(&name, frame_bytes * 2)?;
        Ok(Self { map, name, slot_bytes: frame_bytes, seq: 0 })
    }

    pub fn slot_bytes(&self) -> usize {
        self.slot_bytes
    }

    /// The next slot to write, and the reply that describes it once written.
    pub fn next(&mut self, width: u32, height: u32, deep: bool) -> (&mut [u8], Value) {
        self.seq += 1;
        let offset = (self.seq as usize % 2) * self.slot_bytes;
        let info = json!({ "name": self.name, "size": self.slot_bytes * 2, "offset": offset, "bytes": self.slot_bytes,
                           "stride": width as usize * if deep { 8 } else { 4 }, "format": if deep { "rgba64le" } else { "rgba8" },
                           "seq": self.seq, "width": width, "height": height });
        (&mut self.map.bytes()[offset..offset + self.slot_bytes], info)
    }
}

#[cfg(windows)]
struct Mapping {
    handle: windows_sys::Win32::Foundation::HANDLE,
    view: *mut u8,
    len: usize,
}

#[cfg(windows)]
impl Mapping {
    fn create(name: &str, len: usize) -> Result<Self, String> {
        use windows_sys::Win32::Foundation::{CloseHandle, GetLastError, ERROR_ALREADY_EXISTS, INVALID_HANDLE_VALUE};
        use windows_sys::Win32::System::Memory::{CreateFileMappingW, MapViewOfFile, FILE_MAP_ALL_ACCESS, PAGE_READWRITE};
        let wide: Vec<u16> = name.encode_utf16().chain(std::iter::once(0)).collect();
        let size = len as u64;
        unsafe {
            let handle = CreateFileMappingW(INVALID_HANDLE_VALUE, std::ptr::null(), PAGE_READWRITE, (size >> 32) as u32, size as u32, wide.as_ptr());
            if handle.is_null() {
                return Err(format!("shared memory {name} ({len} bytes): CreateFileMapping failed, error {}", GetLastError()));
            }
            if GetLastError() == ERROR_ALREADY_EXISTS {
                CloseHandle(handle);
                return Err(format!("shared memory {name} already exists"));
            }
            let view = MapViewOfFile(handle, FILE_MAP_ALL_ACCESS, 0, 0, len).Value as *mut u8;
            if view.is_null() {
                let e = GetLastError();
                CloseHandle(handle);
                return Err(format!("shared memory {name}: MapViewOfFile failed, error {e}"));
            }
            Ok(Self { handle, view, len })
        }
    }

    fn bytes(&mut self) -> &mut [u8] {
        unsafe { std::slice::from_raw_parts_mut(self.view, self.len) }
    }
}

#[cfg(windows)]
impl Drop for Mapping {
    fn drop(&mut self) {
        use windows_sys::Win32::System::Memory::{UnmapViewOfFile, MEMORY_MAPPED_VIEW_ADDRESS};
        unsafe {
            UnmapViewOfFile(MEMORY_MAPPED_VIEW_ADDRESS { Value: self.view as _ });
            windows_sys::Win32::Foundation::CloseHandle(self.handle);
        }
    }
}

#[cfg(not(windows))]
struct Mapping;

#[cfg(not(windows))]
impl Mapping {
    fn create(_name: &str, _len: usize) -> Result<Self, String> {
        Err("pixels: shared-memory frames are Windows-only for now (Mac: shm_open + mmap, to do); ask for rgba instead".into())
    }

    fn bytes(&mut self) -> &mut [u8] {
        &mut []
    }
}
