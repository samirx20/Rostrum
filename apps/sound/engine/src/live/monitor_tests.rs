//! monitor.rs: the channel map over fake devices (no multichannel hardware here), the choice per
//! device, and the transport feeding an offline 5.1 / 7.1 device through the stream's own placing rule.
use super::*;
use crate::bed::Layout;
use std::sync::mpsc::channel;
use std::sync::Arc;

fn dev(channels: usize, mask: u32, form_factor: u32) -> Device {
    Device { rate: 48000, channels, mask, form_factor, name: "fake".into() }
}

#[test]
fn stereo_plays_on_the_first_two_channels_of_any_device() {
    assert_eq!(channel_map(2, 0x3, 2, 0x3).unwrap(), vec![Some(0), Some(1)]);
    assert_eq!(channel_map(2, 0x3, 6, 0x3F).unwrap(), vec![Some(0), Some(1), None, None, None, None]);
    assert_eq!(channel_map(2, 0x3, 8, 0).unwrap()[..3], [Some(0), Some(1), None]);
}

#[test]
fn a_bed_goes_speaker_by_speaker() {
    // 5.1 back (0x3F) on itself; on a "5.1 side" device (FL FR FC LFE SL SR) the back pair lands on the sides.
    assert_eq!(channel_map(6, 0x3F, 6, 0x3F).unwrap(), (0..6).map(Some).collect::<Vec<_>>());
    assert_eq!(channel_map(6, 0x3F, 6, 0x60F).unwrap(), (0..6).map(Some).collect::<Vec<_>>());
    // 7.1 (FL FR FC LFE BL BR SL SR) on a 7.1 device; 5.1 on it leaves the sides silent.
    assert_eq!(channel_map(8, 0x63F, 8, 0x63F).unwrap(), (0..8).map(Some).collect::<Vec<_>>());
    assert_eq!(channel_map(6, 0x3F, 8, 0x63F).unwrap(), vec![Some(0), Some(1), Some(2), Some(3), Some(4), Some(5), None, None]);
    // A device whose channels come in another order: placed by bit, not position (LFE last).
    assert_eq!(channel_map(6, 0x3F, 6, 0x3F).unwrap()[3], Some(3));
}

#[test]
fn a_bed_that_cannot_be_placed_is_an_error_naming_the_device() {
    let e = channel_map(6, 0x3F, 2, 0x3).unwrap_err();
    assert!(e.contains("2 channels (FL FR)") && e.contains("FC"), "{e}");
    let e = channel_map(6, 0x3F, 6, 0).unwrap_err();
    assert!(e.contains("not known"), "{e}");
    // A quad device (FL FR BL BR) has no centre.
    assert!(channel_map(6, 0x3F, 4, 0x33).unwrap_err().contains("no FC"));
}

#[test]
fn the_monitor_follows_the_device_unless_asked() {
    let s51 = Layout::Surround51;
    assert_eq!(choose(None, s51, &dev(6, 0x3F, 1)).unwrap().0, Monitor::Surround);
    assert_eq!(choose(None, s51, &dev(2, 0x3, 3)).unwrap().0, Monitor::Binaural, "headphones");
    assert_eq!(choose(None, s51, &dev(2, 0x3, 5)).unwrap().0, Monitor::Binaural, "a headset");
    assert_eq!(choose(None, s51, &dev(2, 0x3, 1)).unwrap().0, Monitor::Stereo, "laptop speakers");
    assert_eq!(choose(Some(Monitor::Stereo), s51, &dev(6, 0x3F, 1)).unwrap().0, Monitor::Stereo);
    assert_eq!(choose(Some(Monitor::Binaural), s51, &dev(2, 0x3, 1)).unwrap().0, Monitor::Binaural);
    let e = choose(Some(Monitor::Surround), s51, &dev(2, 0x3, 3)).unwrap_err();
    assert!(e.contains("--monitor surround") && e.contains("FL FR"), "{e}");
    assert_eq!(choose(Some(Monitor::Surround), Layout::Stereo, &dev(2, 0x3, 1)).unwrap().0, Monitor::Stereo, "a stereo mix plays as it is");
    assert_eq!(Monitor::parse("auto").unwrap(), None);
    assert!(Monitor::parse("quad").is_err());
}

/// A 5.1 bed: a different tone level on each channel.
fn bed51(n: usize) -> Vec<Vec<f32>> {
    (0..6).map(|c| (0..n).map(|i| (0.1 * (c + 1) as f32) * ((i as f32) * 0.05 * (c + 1) as f32).sin()).collect()).collect()
}

#[test]
fn stereo_and_binaural_monitoring_are_the_deliverys_own_render() {
    let bed = bed51(4800);
    let st = prepare(&bed, Layout::Surround51, Monitor::Stereo, None, 48000.0).unwrap();
    let fold = crate::bed::fold::fold_bed(&bed, Layout::Surround51, "stereo", None, 48000.0, true).unwrap().channels;
    assert_eq!(st, crate::live::frames::Frames::from_channels(&fold, 0x3));
    let bin = prepare(&bed, Layout::Surround51, Monitor::Binaural, None, 48000.0).unwrap();
    assert_eq!((bin.channels, bin.len()), (2, 4800));
    let sur = prepare(&bed, Layout::Surround51, Monitor::Surround, None, 48000.0).unwrap();
    assert_eq!((sur.channels, sur.mask), (6, 0x3F));
}

#[cfg(windows)]
/// The transport rolling a 5.1 bed into an offline "5.1 side" device: every speaker gets its own channel.
#[test]
fn the_transport_plays_a_bed_onto_an_offline_device() {
    use crate::live::wasapi::Source;
    let bed = bed51(2000);
    let mix = Arc::new(prepare(&bed, Layout::Surround51, Monitor::Surround, None, 1000.0).unwrap());
    let (c, cr) = channel();
    let (_n, nr) = channel();
    let (o, _or) = channel();
    let mut t = crate::live::transport::Transport::new(mix, 1000, 120.0, 4, None, cr, nr, o);
    assert_eq!((t.channels(), t.mask()), (6, 0x3F));
    c.send(crate::live::transport::Cmd::Play(Some(0.0))).unwrap();
    let map = channel_map(t.channels(), t.mask(), 6, 0x60F).unwrap();
    let mut device = vec![vec![]; 6];
    for b in 0..50 {
        let mut block = vec![0f32; 16 * 6];
        t.fill(&mut block, b * 16);
        for i in 0..16 {
            for (ch, d) in device.iter_mut().enumerate() {
                d.push(placed(&block, i, 6, &map, ch));
            }
        }
    }
    for ch in 0..6 {
        assert_eq!(device[ch][..800], bed[ch][..800], "device channel {ch}");
    }
}
