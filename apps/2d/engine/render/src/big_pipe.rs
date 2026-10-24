//! The pipe a frame travels to the encoder child on. std's own pipe for a child's stdin holds 4 KB, so a 1080p frame
//! (8 MB) crossed it in two thousand hand-offs between the two processes; this one holds a whole frame, so the writer
//! hands it over at once and the encoder reads it while the next is being made. Windows only (other systems' pipes
//! grow on their own).

use std::io::Write;
use std::process::{Child, Command, Stdio};

/// Starts `cmd` with its stdin on a pipe, and returns the child with the writing end of that pipe.
pub fn spawn(cmd: &mut Command) -> Result<(Child, Box<dyn Write + Send>), String> {
    #[cfg(windows)]
    {
        use std::os::windows::io::{FromRawHandle, OwnedHandle};
        use windows_sys::Win32::System::Pipes::CreatePipe;
        // Room for a 1080p frame of 8-bit pixels (8 MB) and the start of the next; bigger frames take more turns.
        const SIZE: u32 = 16 << 20;
        let (mut read, mut write) = (std::ptr::null_mut(), std::ptr::null_mut());
        if unsafe { CreatePipe(&mut read, &mut write, std::ptr::null(), SIZE) } == 0 {
            return Err(format!("the encoder's pipe could not be made: {}", std::io::Error::last_os_error()));
        }
        // Neither end is inheritable as made; std hands the child its own inheritable copy of the reading end.
        let (read, write) = unsafe { (OwnedHandle::from_raw_handle(read), OwnedHandle::from_raw_handle(write)) };
        cmd.stdin(Stdio::from(read));
        let child = cmd.spawn().map_err(|e| e.to_string())?;
        Ok((child, Box::new(std::fs::File::from(write))))
    }
    #[cfg(not(windows))]
    {
        cmd.stdin(Stdio::piped());
        let mut child = cmd.spawn().map_err(|e| e.to_string())?;
        let stdin = child.stdin.take().expect("piped stdin");
        Ok((child, Box::new(stdin)))
    }
}
