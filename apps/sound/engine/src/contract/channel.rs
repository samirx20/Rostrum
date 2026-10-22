//! The answer channel. Answers go out on stdout, one JSON line each; anything else a loaded library prints there
//! (a plug-in's warning: Surge XT prints one when Windows can't name the Documents folder) would break the line
//! protocol. So `serve`, `request` and `render` first keep a private copy of stdout for their answers and point the
//! process's own stdout (the Windows handle and the C runtime's fd 1) at stderr, where the caller keeps the last
//! lines for its error messages.

use std::io::Write;

/// Where answers go: a private copy of the original stdout. Call once, before any plug-in or library is loaded.
pub fn answers() -> Box<dyn Write> {
    match private_stdout() {
        Ok(w) => w,
        Err(e) => {
            eprintln!("rostrum-sound: answers share stdout with plug-ins ({e})");
            Box::new(std::io::stdout())
        }
    }
}

#[cfg(windows)]
fn private_stdout() -> Result<Box<dyn Write>, String> {
    use std::os::windows::io::{AsHandle, AsRawHandle};
    use windows::Win32::Foundation::HANDLE;
    use windows::Win32::System::Console::{SetStdHandle, STD_OUTPUT_HANDLE};
    unsafe extern "C" {
        fn _dup2(from: i32, to: i32) -> i32; // the C runtime's own stdout (fd 1), which C/C++ plug-ins print to
    }
    let own = std::io::stdout().as_handle().try_clone_to_owned().map_err(|e| format!("copy of stdout: {e}"))?;
    let err = std::io::stderr().as_raw_handle();
    unsafe { SetStdHandle(STD_OUTPUT_HANDLE, HANDLE(err)) }.map_err(|e| format!("stdout to stderr: {e}"))?;
    if unsafe { _dup2(2, 1) } != 0 {
        eprintln!("rostrum-sound: the C runtime's stdout still goes to the answer channel");
    }
    Ok(Box::new(std::io::LineWriter::new(std::fs::File::from(own))))
}

#[cfg(not(windows))]
fn private_stdout() -> Result<Box<dyn Write>, String> {
    Err("not done on this system yet (Mac: dup / dup2)".into()) // KNOWN OPEN: Mac
}
