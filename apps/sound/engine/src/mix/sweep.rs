//! Scratch files left behind by an engine that died mid-render. Each file in the render's scratch folder is named
//! `<process id>-<n>.f32` (tape.rs): when its process is gone nobody will read it again, so the next engine to start
//! rendering removes it. A running process's files are never touched, and when the system cannot say whether a
//! process runs, it counts as running.

use std::path::Path;

/// Removes the scratch files in `dir` whose process has ended. A removal that fails is logged and left for next time.
pub fn dead_files(dir: &Path) {
    let Ok(entries) = std::fs::read_dir(dir) else { return };
    for entry in entries.flatten() {
        let path = entry.path();
        let pid = path.file_name().and_then(|n| n.to_str()).filter(|n| n.ends_with(".f32")).and_then(|n| n.split('-').next()).and_then(|p| p.parse::<u32>().ok());
        let Some(pid) = pid else { continue };
        if pid == std::process::id() || running(pid) {
            continue;
        }
        match std::fs::remove_file(&path) {
            Ok(()) => eprintln!("rostrum-sound: removed {}, left by process {pid}, which has ended", path.display()),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => eprintln!("rostrum-sound: could not remove {} (left by ended process {pid}): {e}", path.display()),
        }
    }
}

#[cfg(windows)]
fn running(pid: u32) -> bool {
    use windows::Win32::Foundation::{CloseHandle, ERROR_INVALID_PARAMETER, WAIT_TIMEOUT};
    use windows::Win32::System::Threading::{OpenProcess, WaitForSingleObject, PROCESS_SYNCHRONIZE};
    // SAFETY: the handle comes from OpenProcess, is only waited on with a zero timeout, and is closed here.
    unsafe {
        match OpenProcess(PROCESS_SYNCHRONIZE, false, pid) {
            Ok(h) => {
                let alive = WaitForSingleObject(h, 0) == WAIT_TIMEOUT;
                let _ = CloseHandle(h);
                alive
            }
            Err(e) => e.code() != ERROR_INVALID_PARAMETER.to_hresult(),   // no such process: gone; anything else (access denied): assume it runs
        }
    }
}

#[cfg(unix)]
fn running(pid: u32) -> bool {
    // SAFETY: signal 0 only asks whether the process exists.
    unsafe { libc::kill(pid as libc::pid_t, 0) == 0 || std::io::Error::last_os_error().raw_os_error() != Some(libc::ESRCH) }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn removes_only_files_of_ended_processes() {
        let dir = std::env::temp_dir().join(format!("rostrum-sweep-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let mine = dir.join(format!("{}-0.f32", std::process::id()));
        let other = dir.join("notes.txt");
        // A process that has ended: start a short one, wait for it, use its id.
        let mut child = std::process::Command::new(std::env::current_exe().unwrap()).arg("--list").stdout(std::process::Stdio::null()).spawn().unwrap();
        let gone = child.id();
        child.wait().unwrap();
        let dead = dir.join(format!("{gone}-3.f32"));
        for f in [&mine, &other, &dead] {
            std::fs::write(f, b"x").unwrap();
        }
        dead_files(&dir);
        assert!(mine.exists() && other.exists() && !dead.exists());
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
