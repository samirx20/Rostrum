//! Pipelined frame readback on the GPU (painter.rs `read_async`): a frame's pixels are copied into a GL pixel
//! buffer (PBO) by the GPU after it draws the frame, while the CPU goes on to the next frame's edits, layout
//! and recording; they are collected one frame later, when the copy has long finished. Two buffers take turns.
//! The bytes are the surface's own (premultiplied, top row first, as `Surface::read_pixels` gives them).

use std::ffi::{c_void, CString};

const PIXEL_PACK_BUFFER: u32 = 0x88EB;
const STREAM_READ: u32 = 0x88E1;
const READ_FRAMEBUFFER: u32 = 0x8CA8;
const RGBA: u32 = 0x1908;
const UNSIGNED_BYTE: u32 = 0x1401;
const HALF_FLOAT: u32 = 0x140B;
const SYNC_GPU_COMMANDS_COMPLETE: u32 = 0x9117;
const SYNC_FLUSH_COMMANDS_BIT: u32 = 0x1;
const MAP_READ_BIT: u32 = 0x1;
const PACK_ALIGNMENT: u32 = 0x0D05;
const WAIT_FAILED: u32 = 0x911D;

#[allow(non_snake_case)]
struct Fns {
    GenBuffers: extern "system" fn(i32, *mut u32),
    BindBuffer: extern "system" fn(u32, u32),
    BufferData: extern "system" fn(u32, isize, *const c_void, u32),
    BindFramebuffer: extern "system" fn(u32, u32),
    ReadPixels: extern "system" fn(i32, i32, i32, i32, u32, u32, *mut c_void),
    FenceSync: extern "system" fn(u32, u32) -> *const c_void,
    ClientWaitSync: extern "system" fn(*const c_void, u32, u64) -> u32,
    DeleteSync: extern "system" fn(*const c_void),
    MapBufferRange: extern "system" fn(u32, isize, isize, u32) -> *const u8,
    UnmapBuffer: extern "system" fn(u32) -> u8,
    PixelStorei: extern "system" fn(u32, i32),
}

/// One frame's copy in flight: its buffer, its fence, its byte count.
struct Pending {
    slot: usize,
    fence: *const c_void,
    bytes: usize,
    half: bool,
}

pub struct Readback {
    f: Fns,
    pbos: [u32; 2],
    sizes: [usize; 2],
    next: usize,
    pending: std::collections::VecDeque<Pending>,
}

impl Readback {
    /// Loads the GL entry points (all GL 3.2+); None when one is missing.
    pub fn new(load: impl Fn(&CString) -> *const c_void) -> Option<Readback> {
        let get = |name: &str| {
            let p = load(&CString::new(name).unwrap());
            (!p.is_null()).then_some(p)
        };
        unsafe {
            let f = Fns {
                GenBuffers: std::mem::transmute(get("glGenBuffers")?),
                BindBuffer: std::mem::transmute(get("glBindBuffer")?),
                BufferData: std::mem::transmute(get("glBufferData")?),
                BindFramebuffer: std::mem::transmute(get("glBindFramebuffer")?),
                ReadPixels: std::mem::transmute(get("glReadPixels")?),
                FenceSync: std::mem::transmute(get("glFenceSync")?),
                ClientWaitSync: std::mem::transmute(get("glClientWaitSync")?),
                DeleteSync: std::mem::transmute(get("glDeleteSync")?),
                MapBufferRange: std::mem::transmute(get("glMapBufferRange")?),
                UnmapBuffer: std::mem::transmute(get("glUnmapBuffer")?),
                PixelStorei: std::mem::transmute(get("glPixelStorei")?),
            };
            let mut pbos = [0u32; 2];
            (f.GenBuffers)(2, pbos.as_mut_ptr());
            Some(Readback { f, pbos, sizes: [0; 2], next: 0, pending: Default::default() })
        }
    }

    /// Queues the copy of framebuffer `fbo` (width × height, 8-bit or half-float RGBA) into the next buffer.
    /// The caller has submitted the frame's drawing and resets Skia's GL state afterwards.
    pub fn start(&mut self, fbo: u32, width: u32, height: u32, half: bool) {
        let slot = self.next;
        self.next = 1 - slot;
        let bytes = width as usize * height as usize * if half { 8 } else { 4 };
        let f = &self.f;
        (f.BindBuffer)(PIXEL_PACK_BUFFER, self.pbos[slot]);
        if self.sizes[slot] != bytes {
            (f.BufferData)(PIXEL_PACK_BUFFER, bytes as isize, std::ptr::null(), STREAM_READ);
            self.sizes[slot] = bytes;
        }
        (f.BindFramebuffer)(READ_FRAMEBUFFER, fbo);
        (f.PixelStorei)(PACK_ALIGNMENT, 4);
        (f.ReadPixels)(0, 0, width as i32, height as i32, RGBA, if half { HALF_FLOAT } else { UNSIGNED_BYTE }, std::ptr::null_mut());
        let fence = (f.FenceSync)(SYNC_GPU_COMMANDS_COMPLETE, 0);
        (f.BindBuffer)(PIXEL_PACK_BUFFER, 0);
        self.pending.push_back(Pending { slot, fence, bytes, half });
    }

    /// The oldest queued copy's bytes and whether they are half floats (waiting for the GPU if it has not
    /// finished it).
    pub fn finish_oldest(&mut self) -> Result<(Vec<u8>, bool), String> {
        let p = self.pending.pop_front().ok_or("no readback in flight")?;
        let f = &self.f;
        let waited = (f.ClientWaitSync)(p.fence, SYNC_FLUSH_COMMANDS_BIT, u64::MAX);
        (f.DeleteSync)(p.fence);
        if waited == WAIT_FAILED {
            return Err("frame readback: waiting for the GPU failed".into());
        }
        (f.BindBuffer)(PIXEL_PACK_BUFFER, self.pbos[p.slot]);
        let ptr = (f.MapBufferRange)(PIXEL_PACK_BUFFER, 0, p.bytes as isize, MAP_READ_BIT);
        if ptr.is_null() {
            (f.BindBuffer)(PIXEL_PACK_BUFFER, 0);
            return Err("frame readback: mapping the pixel buffer failed".into());
        }
        let out = unsafe { std::slice::from_raw_parts(ptr, p.bytes) }.to_vec();
        (f.UnmapBuffer)(PIXEL_PACK_BUFFER);
        (f.BindBuffer)(PIXEL_PACK_BUFFER, 0);
        Ok((out, p.half))
    }
}
