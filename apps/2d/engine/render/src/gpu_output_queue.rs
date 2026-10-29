//! Whole frames through the exact output step on their way to an encoder (painter.rs `start_read`): the GPU turns the
//! frame's halves into the encoder's bytes (8-bit RGBA, 16-bit when `deep`, or 8-bit NV12 when the encoder takes it:
//! two more passes turn the output codes into its Y and Cb Cr planes, 1.5 bytes a pixel) and copies them, with the marks of the
//! pixels the CPU redoes, into pixel buffers behind a fence; nothing waits. The frame is collected one frame later
//! (`finish`), when the copy has long finished: half the bytes of reading the halves back (a quarter when 8-bit is
//! compared with the halves' 8 bytes a pixel) and no output step on the CPU, the same bytes as color.rs `output` gives.
//! The CPU redoes only the marked pixels (a see-through edge), from a copy of the frame kept on the GPU, since the next
//! frame is painted over the surface before this one is collected (painter.rs patches NV12 with nv12.rs `patch`, the
//! same integer formula as the GPU's). Two slots take turns.

use std::collections::VecDeque;
use std::ffi::c_void;

use super::{cpu_rects, out_format, target, Done, GpuOutput, Target, BLOCK, FRAMEBUFFER, HALF_RGBA, PIXEL_PACK_BUFFER, R8UI, RED_INTEGER, RG8UI, RGBA_INTEGER, RG_INTEGER, TEXTURE_2D};

const READ_FRAMEBUFFER: u32 = 0x8CA8;
const DRAW_FRAMEBUFFER: u32 = 0x8CA9;
const COLOR_ATTACHMENT0: u32 = 0x8CE0;

/// One frame's GPU memory: its output, its marks, the copy of its halves, and the pixel buffers they are read into.
#[derive(Default)]
struct Slot {
    out: Option<Target>,
    flags: Option<Target>,
    held: Option<Target>,
    /// NV12's planes (an encoder taking NV12): Y, w × h, and Cb Cr, w/2 × h/2.
    luma: Option<Target>,
    chroma: Option<Target>,
    out_pbo: (u32, usize),
    flags_pbo: (u32, usize),
}

/// A frame started and not collected: its slot, the fence after its copies, its size and form.
struct Queued {
    slot: usize,
    fence: *const c_void,
    w: u32,
    h: u32,
    deep: bool,
    nv12: bool,
}

#[derive(Default)]
pub struct Queue {
    slots: [Slot; 2],
    next: usize,
    pending: VecDeque<Queued>,
}

impl GpuOutput {
    /// Queues the output of texture `src` (the frame, RGBA16F, w × h, top row first) with `codes` into the next slot, and
    /// its copy into pixel buffers; as NV12 when `nv12` (8-bit, w and h even). Nothing waits. At most two may be queued.
    /// The caller has flushed Skia's work and resets Skia's GL state afterwards.
    pub fn queue_start(&mut self, src: u32, (w, h): (u32, u32), codes: &std::sync::Arc<[u32]>, deep: bool, nv12: bool) -> Result<(), String> {
        if nv12 && (deep || w % 2 != 0 || h % 2 != 0) {
            return Err(format!("the GPU output step: NV12 is 8-bit at an even size, not {w}×{h}{}", if deep { " 16-bit" } else { "" }));
        }
        if self.queue.pending.len() >= 2 {
            return Err("the GPU output step: two frames already queued".into());
        }
        self.prepare();
        let k = self.queue.next;
        self.queue.next = 1 - k;
        let fw = w.div_ceil(BLOCK);
        let f = &self.f;
        (f.ActiveTexture)(0x84C2);
        let slot = &mut self.queue.slots[k];
        let out = target(f, &mut slot.out, (w, h, out_format(deep)))?;
        let flags = target(f, &mut slot.flags, (fw, h, R8UI))?;
        let held = target(f, &mut slot.held, (w, h, HALF_RGBA))?;
        self.passes(src, w, codes, deep, false, out, flags, None);
        let planes = if nv12 { Some(self.nv12_passes(k, out.3, (w, h))?) } else { None };
        let f = &self.f;
        // The halves kept for the pixels the CPU redoes.
        (f.BindFramebuffer)(READ_FRAMEBUFFER, self.src_fbo);
        (f.FramebufferTexture2D)(READ_FRAMEBUFFER, COLOR_ATTACHMENT0, TEXTURE_2D, src, 0);
        (f.BindFramebuffer)(DRAW_FRAMEBUFFER, held.0);
        (f.BlitFramebuffer)(0, 0, w as i32, h as i32, 0, 0, w as i32, h as i32, 0x4000, 0x2600); // COLOR_BUFFER_BIT, NEAREST
        (f.FramebufferTexture2D)(READ_FRAMEBUFFER, COLOR_ATTACHMENT0, TEXTURE_2D, 0, 0);
        // The marks and the output (or its NV12 planes, one after the other) into their pixel buffers.
        let slot = &mut self.queue.slots[k];
        let flags_read = [(flags.0, fw, h, RED_INTEGER, 0x1401, 1, 0)];
        let out_reads = match planes {
            None => vec![(out.0, w, h, RGBA_INTEGER, if deep { 0x1403 } else { 0x1401 }, if deep { 8 } else { 4 }, 0)],
            Some((y, c)) => vec![(y, w, h, RED_INTEGER, 0x1401, 1, 0), (c, w / 2, h / 2, RG_INTEGER, 0x1401, 2, (w * h) as usize)],
        };
        for (pbo, reads) in [(&mut slot.flags_pbo, &flags_read[..]), (&mut slot.out_pbo, &out_reads[..])] {
            if pbo.0 == 0 {
                (f.GenBuffers)(1, &mut pbo.0);
            }
            let bytes: usize = reads.iter().map(|r| (r.1 * r.2) as usize * r.5).sum();
            (f.BindBuffer)(PIXEL_PACK_BUFFER, pbo.0);
            if pbo.1 != bytes {
                (f.BufferData)(PIXEL_PACK_BUFFER, bytes as isize, std::ptr::null(), 0x88E1); // STREAM_READ
                pbo.1 = bytes;
            }
            for &(fbo, rw, rh, format, ty, _, at) in reads {
                (f.BindFramebuffer)(FRAMEBUFFER, fbo);
                (f.ReadPixels)(0, 0, rw as i32, rh as i32, format, ty, at as *mut c_void);
            }
        }
        (f.BindBuffer)(PIXEL_PACK_BUFFER, 0);
        (f.BindFramebuffer)(FRAMEBUFFER, 0);
        let fence = (f.FenceSync)(0x9117, 0); // SYNC_GPU_COMMANDS_COMPLETE
        match (f.GetError)() {
            0 => {
                self.queue.pending.push_back(Queued { slot: k, fence, w, h, deep, nv12 });
                Ok(())
            }
            e => {
                (f.DeleteSync)(fence);
                Err(format!("the GPU output step (export): GL error 0x{e:x}"))
            }
        }
    }

    /// NV12's passes in slot `k` from the 8-bit output codes (texture `out`, w × h): its Y and Cb Cr planes' framebuffers.
    fn nv12_passes(&mut self, k: usize, out: u32, (w, h): (u32, u32)) -> Result<(u32, u32), String> {
        let slot = &mut self.queue.slots[k];
        let f = &self.f;
        (f.ActiveTexture)(0x84C2);
        let luma = target(f, &mut slot.luma, (w, h, R8UI))?;
        let chroma = target(f, &mut slot.chroma, (w / 2, h / 2, RG8UI))?;
        (f.ActiveTexture)(0x84C3);
        (f.BindSampler)(3, 0);
        (f.BindTexture)(TEXTURE_2D, out);
        (f.ActiveTexture)(0x84C0);
        for (prog, (fbo, tw, th, _)) in [(self.programs[2], luma), (self.programs[3], chroma)] {
            (f.UseProgram)(prog);
            (f.Uniform1i)((f.GetUniformLocation)(prog, c"cur".as_ptr() as *const u8), 3);
            (f.BindFramebuffer)(FRAMEBUFFER, fbo);
            (f.Viewport)(0, 0, tw as i32, th as i32);
            (f.DrawArrays)(0x0004, 0, 3);
        }
        Ok((luma.0, chroma.0))
    }

    /// Whether the oldest queued frame comes as NV12 (`queue_finish` then wants w × h × 3/2 bytes).
    pub fn queue_next_nv12(&self) -> Option<bool> {
        self.queue.pending.front().map(|q| q.nv12)
    }

    /// The oldest queued frame's bytes into `out` (exactly its size), waiting for the GPU if it has not finished it; the
    /// rectangles the CPU must redo, with the frame's halves there.
    pub fn queue_finish(&mut self, out: &mut [u8]) -> Result<Done, String> {
        let q = self.queue.pending.pop_front().ok_or("the GPU output step: no frame queued")?;
        let f = &self.f;
        let waited = (f.ClientWaitSync)(q.fence, 0x1, u64::MAX); // SYNC_FLUSH_COMMANDS_BIT
        (f.DeleteSync)(q.fence);
        if waited == 0x911D {
            return Err("the GPU output step: waiting for the GPU failed".into());
        }
        let (w, h) = (q.w as usize, q.h as usize);
        assert_eq!(out.len(), if q.nv12 { w * h * 3 / 2 } else { w * h * if q.deep { 8 } else { 4 } }, "output buffer size");
        let fw = q.w.div_ceil(BLOCK) as usize;
        let slot = &self.queue.slots[q.slot];
        // A pixel buffer's first `bytes`, mapped, to `read`.
        let mapped = |pbo: u32, bytes: usize, read: &mut dyn FnMut(&[u8])| -> Result<(), String> {
            (f.BindBuffer)(PIXEL_PACK_BUFFER, pbo);
            let ptr = (f.MapBufferRange)(PIXEL_PACK_BUFFER, 0, bytes as isize, 0x1); // MAP_READ_BIT
            if ptr.is_null() {
                (f.BindBuffer)(PIXEL_PACK_BUFFER, 0);
                return Err("the GPU output step: mapping a frame's pixel buffer failed".into());
            }
            read(unsafe { std::slice::from_raw_parts(ptr, bytes) });
            (f.UnmapBuffer)(PIXEL_PACK_BUFFER);
            Ok(())
        };
        let mut rects = vec![];
        mapped(slot.flags_pbo.0, fw * h, &mut |got| rects = cpu_rects(got, fw, q.w))?;
        mapped(slot.out_pbo.0, out.len(), &mut |got| out.copy_from_slice(got))?;
        (f.BindBuffer)(PIXEL_PACK_BUFFER, 0);
        let held = slot.held.as_ref().map(|t| t.tex).ok_or("the GPU output step: no copy of the frame")?;
        let cpu = self.halves_in(held, rects);
        match (self.f.GetError)() {
            0 => Ok(Done { cpu, rows_read: q.h }),
            e => Err(format!("the GPU output step (export): GL error 0x{e:x}")),
        }
    }
}
