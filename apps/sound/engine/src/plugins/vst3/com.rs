//! The host side of VST3 as COM objects: the host application, the event list, parameter changes
//! (a queue per parameter), an in-memory stream (a plugin's state is read and written through it),
//! and for a session the component handler (editor edits) and the frame (editor resizes).

use std::cell::{Cell, RefCell};
use std::ffi::c_void;
use std::sync::{Arc, Mutex};

use vst3::Steinberg::Vst::*;
use vst3::Steinberg::*;
use vst3::{Class, ComWrapper};
pub(crate) struct HostApp;
impl Class for HostApp {
    type Interfaces = (IHostApplication,);
}
impl IHostApplicationTrait for HostApp {
    unsafe fn getName(&self, name: *mut String128) -> tresult {
        for (i, c) in "Rostrum".encode_utf16().chain(std::iter::once(0)).enumerate() {
            (*name)[i] = c;
        }
        kResultOk
    }
    unsafe fn createInstance(&self, _cid: *mut TUID, _iid: *mut TUID, obj: *mut *mut c_void) -> tresult {
        *obj = std::ptr::null_mut();
        kNotImplemented
    }
}

pub(crate) struct Events(pub(crate) RefCell<Vec<Event>>);
impl Class for Events {
    type Interfaces = (IEventList,);
}
impl IEventListTrait for Events {
    unsafe fn getEventCount(&self) -> int32 {
        self.0.borrow().len() as int32
    }
    unsafe fn getEvent(&self, index: int32, e: *mut Event) -> tresult {
        match self.0.borrow().get(index as usize) {
            Some(ev) => {
                *e = *ev;
                kResultOk
            }
            None => kInvalidArgument,
        }
    }
    unsafe fn addEvent(&self, e: *mut Event) -> tresult {
        self.0.borrow_mut().push(*e);
        kResultOk
    }
}

pub(crate) struct Queue {
    id: ParamID,
    points: RefCell<Vec<(int32, ParamValue)>>,
}
impl Class for Queue {
    type Interfaces = (IParamValueQueue,);
}
impl IParamValueQueueTrait for Queue {
    unsafe fn getParameterId(&self) -> ParamID {
        self.id
    }
    unsafe fn getPointCount(&self) -> int32 {
        self.points.borrow().len() as int32
    }
    unsafe fn getPoint(&self, index: int32, offset: *mut int32, value: *mut ParamValue) -> tresult {
        match self.points.borrow().get(index as usize) {
            Some(&(o, v)) => {
                *offset = o;
                *value = v;
                kResultOk
            }
            None => kInvalidArgument,
        }
    }
    unsafe fn addPoint(&self, offset: int32, value: ParamValue, index: *mut int32) -> tresult {
        let mut p = self.points.borrow_mut();
        p.push((offset, value));
        if !index.is_null() {
            *index = p.len() as int32 - 1;
        }
        kResultOk
    }
}

pub(crate) struct Changes(pub(crate) RefCell<Vec<ComWrapper<Queue>>>);
impl Class for Changes {
    type Interfaces = (IParameterChanges,);
}
impl IParameterChangesTrait for Changes {
    unsafe fn getParameterCount(&self) -> int32 {
        self.0.borrow().len() as int32
    }
    unsafe fn getParameterData(&self, index: int32) -> *mut IParamValueQueue {
        self.0.borrow().get(index as usize).and_then(|q| q.as_com_ref::<IParamValueQueue>()).map_or(std::ptr::null_mut(), |r| r.as_ptr())
    }
    unsafe fn addParameterData(&self, id: *const ParamID, index: *mut int32) -> *mut IParamValueQueue {
        let mut qs = self.0.borrow_mut();
        let i = match qs.iter().position(|q| q.id == *id) {
            Some(i) => i,
            None => {
                qs.push(ComWrapper::new(Queue { id: *id, points: RefCell::new(vec![]) }));
                qs.len() - 1
            }
        };
        if !index.is_null() {
            *index = i as int32;
        }
        qs[i].as_com_ref::<IParamValueQueue>().map_or(std::ptr::null_mut(), |r| r.as_ptr())
    }
}

/// An in-memory IBStream: the bytes and the read / write position.
pub(crate) struct Stream(pub(crate) RefCell<(Vec<u8>, usize)>);
impl Class for Stream {
    type Interfaces = (IBStream,);
}
impl Stream {
    pub(crate) fn new(bytes: Vec<u8>) -> ComWrapper<Stream> {
        ComWrapper::new(Stream(RefCell::new((bytes, 0))))
    }
}
impl IBStreamTrait for Stream {
    unsafe fn read(&self, buffer: *mut c_void, n: int32, done: *mut int32) -> tresult {
        let (bytes, pos) = &mut *self.0.borrow_mut();
        let k = (n.max(0) as usize).min(bytes.len().saturating_sub(*pos));
        std::ptr::copy_nonoverlapping(bytes.as_ptr().add(*pos), buffer as *mut u8, k);
        *pos += k;
        if !done.is_null() {
            *done = k as int32;
        }
        kResultOk
    }
    unsafe fn write(&self, buffer: *mut c_void, n: int32, done: *mut int32) -> tresult {
        let (bytes, pos) = &mut *self.0.borrow_mut();
        let src = std::slice::from_raw_parts(buffer as *const u8, n.max(0) as usize);
        if bytes.len() < *pos + src.len() {
            bytes.resize(*pos + src.len(), 0);
        }
        bytes[*pos..*pos + src.len()].copy_from_slice(src);
        *pos += src.len();
        if !done.is_null() {
            *done = n;
        }
        kResultOk
    }
    unsafe fn seek(&self, to: int64, mode: int32, result: *mut int64) -> tresult {
        let (bytes, pos) = &mut *self.0.borrow_mut();
        let base = match mode {
            0 => 0,
            1 => *pos as i64,
            2 => bytes.len() as i64,
            _ => return kInvalidArgument,
        };
        *pos = (base + to).clamp(0, bytes.len() as i64) as usize;
        if !result.is_null() {
            *result = *pos as int64;
        }
        kResultOk
    }
    unsafe fn tell(&self, pos: *mut int64) -> tresult {
        if !pos.is_null() {
            *pos = self.0.borrow().1 as int64;
        }
        kResultOk
    }
}

/// Edits made in a plugin's editor, for its processor.
pub(crate) type Edits = Arc<Mutex<Vec<(u32, f64)>>>;

/// The host's side of the controller: edits made in the editor, queued for the processor.
pub(crate) struct Handler(pub(crate) Edits);
impl Class for Handler {
    type Interfaces = (IComponentHandler,);
}
impl IComponentHandlerTrait for Handler {
    unsafe fn beginEdit(&self, _id: ParamID) -> tresult {
        kResultOk
    }
    unsafe fn performEdit(&self, id: ParamID, value: ParamValue) -> tresult {
        self.0.lock().unwrap().push((id, value));
        kResultOk
    }
    unsafe fn endEdit(&self, _id: ParamID) -> tresult {
        kResultOk
    }
    unsafe fn restartComponent(&self, _flags: int32) -> tresult {
        kResultOk
    }
}

/// The editor asks to be resized: done on the next idle.
pub(crate) struct Frame(pub(crate) Cell<Option<(u32, u32)>>);
impl Class for Frame {
    type Interfaces = (IPlugFrame,);
}
impl IPlugFrameTrait for Frame {
    unsafe fn resizeView(&self, view: *mut IPlugView, size: *mut ViewRect) -> tresult {
        let r = *size;
        self.0.set(Some(((r.right - r.left).max(1) as u32, (r.bottom - r.top).max(1) as u32)));
        if let Some(v) = vst3::ComRef::from_raw(view) {
            v.onSize(size);
        }
        kResultTrue
    }
}
