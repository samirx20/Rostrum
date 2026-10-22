//! An insert that keeps its state between blocks (chain.rs): a track renders in blocks of `tape::BLOCK` frames
//! and each effect carries what it needs (filter memory, envelopes, delay lines, reverb tails) from one block to
//! the next, so the result is the one a whole-buffer run gives. `t0` is the block's first frame in the track
//! (automation is read at `t0 + i`).

use crate::bed::Layout;

pub trait Insert: Send {
    /// One block of every channel, in place; `t0`: the block's first frame.
    fn block(&mut self, chs: &mut [&mut [f32]], t0: usize) -> Result<(), String>;
}

/// Two channels of the bed, mutably (i < j).
pub(crate) fn two<'a>(chs: &'a mut [&mut [f32]], i: usize, j: usize) -> (&'a mut [f32], &'a mut [f32]) {
    let (a, b) = chs.split_at_mut(j);
    (&mut *a[i], &mut *b[0])
}

/// A pair effect over the bed: one state per left/right pair, then one per lone channel (with a scratch partner
/// it discards); the LFE only when `lfe`.
pub(crate) struct Pairwise<T> {
    pairs: Vec<(usize, usize)>,
    lone: Vec<usize>,
    states: Vec<T>,
}

impl<T> Pairwise<T> {
    pub fn new(layout: Layout, channels: usize, lfe: bool, mut make: impl FnMut() -> T) -> Self {
        let pairs = layout.pairs();
        let lone: Vec<usize> = (0..channels).filter(|&c| !pairs.iter().any(|&(i, j)| i == c || j == c) && (lfe || Some(c) != layout.lfe())).collect();
        let states = (0..pairs.len() + lone.len()).map(|_| make()).collect();
        Pairwise { pairs, lone, states }
    }

    pub fn run(&mut self, chs: &mut [&mut [f32]], mut f: impl FnMut(&mut T, &mut [f32], &mut [f32]) -> Result<(), String>) -> Result<(), String> {
        let mut st = self.states.iter_mut();
        for &(i, j) in &self.pairs {
            let (l, r) = two(chs, i, j);
            f(st.next().expect("a state per pair"), l, r)?;
        }
        for &c in &self.lone {
            let mut scratch = chs[c].to_vec();
            f(st.next().expect("a state per lone channel"), &mut *chs[c], &mut scratch)?;
        }
        Ok(())
    }
}
