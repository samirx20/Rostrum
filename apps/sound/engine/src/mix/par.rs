//! Independent jobs on all cores, results in input order: the offline mix's clips, tracks and measures
//! (render/). Each job computes alone and the caller combines the results in a fixed order, so a mix
//! is bit-identical whatever the thread count or timing.

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;

/// `f` over every item on up to all cores (`threads` caps it, e.g. to bound memory); results in item order.
pub fn map_n<T: Send, R: Send>(items: Vec<T>, threads: usize, f: impl Fn(T) -> R + Sync) -> Vec<R> {
    let n = items.len();
    if n <= 1 || threads <= 1 {
        return items.into_iter().map(f).collect();
    }
    let cores = std::thread::available_parallelism().map(|c| c.get()).unwrap_or(4);
    let slots: Vec<Mutex<Option<T>>> = items.into_iter().map(|t| Mutex::new(Some(t))).collect();
    let out: Vec<Mutex<Option<R>>> = (0..n).map(|_| Mutex::new(None)).collect();
    let next = AtomicUsize::new(0);
    std::thread::scope(|s| {
        for _ in 0..threads.min(cores).min(n) {
            s.spawn(|| loop {
                let k = next.fetch_add(1, Ordering::Relaxed);
                let Some(slot) = slots.get(k) else { break };
                let item = slot.lock().unwrap().take().expect("each job runs once");
                let r = f(item);
                *out[k].lock().unwrap() = Some(r);
            });
        }
    });
    out.into_iter().map(|m| m.into_inner().unwrap().expect("every job ran")).collect()
}

/// What the mix's jobs may hold at once (render/): each job holds about one track, so a long song runs fewer
/// at a time and its peak stays near this, whatever its length or track count.
const BUDGET_BYTES: usize = 2 << 30;

/// How many jobs of `bytes` each to run at once within the budget (at least one).
pub fn threads_for(bytes: usize) -> usize {
    (BUDGET_BYTES / bytes.max(1)).max(1)
}

/// `f` over every item on all cores; results in item order.
pub fn map<T: Send, R: Send>(items: Vec<T>, f: impl Fn(T) -> R + Sync) -> Vec<R> {
    map_n(items, usize::MAX, f)
}

#[cfg(test)]
mod tests {
    #[test]
    fn results_keep_the_input_order() {
        let v: Vec<u64> = (0..200).collect();
        assert_eq!(super::map(v.clone(), |x| x * x), v.iter().map(|x| x * x).collect::<Vec<_>>());
        assert_eq!(super::map_n(v.clone(), 1, |x| x + 1), v.iter().map(|x| x + 1).collect::<Vec<_>>());
    }
}
