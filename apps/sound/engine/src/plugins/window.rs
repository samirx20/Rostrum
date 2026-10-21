//! The window a plugin's own editor lives in (Win32): a plain top-level window the editor is
//! embedded in, sized to it, closed by the person; and the message pump that keeps both alive.
//! Used by the CLAP and VST3 sessions (session.rs, vst3/session.rs).

#![allow(unsafe_op_in_unsafe_fn)]

use std::sync::atomic::{AtomicBool, Ordering};

use windows::core::{w, HSTRING};
use windows::Win32::Foundation::{HWND, LPARAM, LRESULT, RECT, WPARAM};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::WindowsAndMessaging::*;

static CLOSED: AtomicBool = AtomicBool::new(false);

unsafe extern "system" fn proc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    match msg {
        // The editor goes first (the session destroys it), then this window.
        WM_CLOSE => {
            CLOSED.store(true, Ordering::Relaxed);
            LRESULT(0)
        }
        _ => DefWindowProcW(hwnd, msg, wp, lp),
    }
}

fn style(resizable: bool) -> WINDOW_STYLE {
    WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | if resizable { WS_THICKFRAME | WS_MAXIMIZEBOX } else { WINDOW_STYLE(0) }
}

pub struct Window {
    pub hwnd: HWND,
    resizable: bool,
}

impl Window {
    /// A window whose client area is `width` × `height` (physical pixels).
    pub fn new(title: &str, width: u32, height: u32, resizable: bool) -> Result<Window, String> {
        unsafe {
            let instance = GetModuleHandleW(None).map_err(|e| e.message())?;
            let class = WNDCLASSW { lpfnWndProc: Some(proc), hInstance: instance.into(), lpszClassName: w!("RostrumPluginEditor"), hCursor: LoadCursorW(None, IDC_ARROW).unwrap_or_default(), ..Default::default() };
            RegisterClassW(&class); // already registered by an earlier window: fine
            let (w, h) = outer(width, height, resizable);
            let hwnd = CreateWindowExW(WINDOW_EX_STYLE(0), w!("RostrumPluginEditor"), &HSTRING::from(title), style(resizable), CW_USEDEFAULT, CW_USEDEFAULT, w, h, None, None, Some(instance.into()), None).map_err(|e| format!("cannot open a window: {}", e.message()))?;
            CLOSED.store(false, Ordering::Relaxed);
            Ok(Window { hwnd, resizable })
        }
    }

    pub fn show(&self) {
        unsafe {
            let _ = ShowWindow(self.hwnd, SW_SHOW);
            let _ = SetForegroundWindow(self.hwnd);
        }
    }

    /// The client area resized to the editor's size.
    pub fn resize(&self, width: u32, height: u32) {
        let (w, h) = outer(width, height, self.resizable);
        unsafe {
            let _ = SetWindowPos(self.hwnd, None, 0, 0, w, h, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
        }
    }

    /// Handles the window messages waiting (the editor's too); false once the person has closed it.
    pub fn pump(&self) -> bool {
        unsafe {
            let mut msg = MSG::default();
            while PeekMessageW(&mut msg, None, 0, 0, PM_REMOVE).as_bool() {
                let _ = TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }
        }
        !CLOSED.load(Ordering::Relaxed)
    }
}

impl Drop for Window {
    fn drop(&mut self) {
        unsafe {
            let _ = DestroyWindow(self.hwnd);
        }
        self.pump();
    }
}

fn outer(width: u32, height: u32, resizable: bool) -> (i32, i32) {
    let mut r = RECT { left: 0, top: 0, right: width as i32, bottom: height as i32 };
    unsafe {
        let _ = AdjustWindowRectEx(&mut r, style(resizable), false, WINDOW_EX_STYLE(0));
    }
    (r.right - r.left, r.bottom - r.top)
}

/// Handles waiting messages without a window of ours (a plugin's own timers and floating windows).
pub fn pump_messages() {
    unsafe {
        let mut msg = MSG::default();
        while PeekMessageW(&mut msg, None, 0, 0, PM_REMOVE).as_bool() {
            let _ = TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
}
