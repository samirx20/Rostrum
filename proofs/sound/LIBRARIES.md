# P-SND — Libraries research (instrument packs, effects packs, ACE-Step 1.5, test clip)

*Team Priyam, member report, 2026-10-21. Research only: nothing was run on the GPU, nothing committed. Licences were read in the pack folders and again on the source pages (dates below). Scratch files (inventory CSV, frames, motion data) are in `C:\Users\Sam\.rostrum\waves\scratch\priyam-p1\libraries\`.*

**Verdict words used below:** **Shippable** = we may put it inside the app installer. **Usable, not shippable** = fine for the proof / for a user to download themselves, but we should not bundle it (or only with strings attached). **Rejected** = do not use.

---

## 1. Instrument libraries (SFZ)

Installed at `C:\Users\Sam\.rostrum\assets\sounds\`. Record of origin: the experiment's `instrumentPacks.json`, `soundPacks.ts`, `C:\Users\Sam\.rostrum\assets\assets.json`, and each pack's own LICENSE / readme (read today).

### 1.1 Licence table

| Pack (folder) | Source | Licence (as read) | Ship inside the app? | Credit text | Size on disk |
|---|---|---|---|---|---|
| `vsco2-strings` | https://github.com/sgossner/VSCO-2-CE | **CC0 1.0** (LICENSE file + repo label). The readme *asks* for credit to "Versilian Studios / Sam Gossner" and a link, and asks that you "do not sell the samples directly". | **Shippable** (CC0 means credit is a courtesy; we will give it anyway, and must not sell the samples on their own) | "VSCO 2 Community Edition by Versilian Studios (Sam Gossner) — https://github.com/sgossner/VSCO-2-CE (CC0)" | 723 MB |
| `vsco2-brass` | same | CC0 1.0 | Shippable | same | 298 MB |
| `vsco2-woodwinds` | same | CC0 1.0 | Shippable | same | 286 MB |
| `vsco2-percussion` | same | CC0 1.0 | Shippable | same | 72 MB (**timpani only**, see gaps) |
| `salamander-piano` | https://freepats.zenvoid.org/Piano/acoustic-grand-piano.html | **CC BY 3.0** (page, 2026-10-21) | Shippable **with credit shown** | "Salamander Grand Piano by Alexander Holm (CC-BY 3.0)" | 1.2 GB (44.1k/16-bit folder; upstream FLAC is 707 MiB) |
| `bigcat-cello` | https://github.com/sfzinstruments/karoryfer-bigcat.cello | CC0-1.0 (LICENSE + repo label); readme: "open source, do whatever you want" | Shippable | none needed; courtesy "Karoryfer Samples x bigcat, solo cello by Kamila Borowiak" | 108 MB |
| `dsmolken-bass` | https://github.com/sfzinstruments/dsmolken.double-bass | CC0-1.0; readme "Royalty-free for all commercial and non-commercial use" | Shippable | none needed | 131 MB |
| `growlybass` | https://github.com/sfzinstruments/karoryfer.growlybass | CC0-1.0; readme "Royalty-free…" | Shippable | none needed | 176 MB |
| `shinyguitar` | https://github.com/sfzinstruments/karoryfer.shinyguitar | CC0-1.0; readme "Royalty-free…" | Shippable | none needed | 217 MB |
| `muldjord-kit` | https://freepats.zenvoid.org/Percussion/acoustic-drum-kit.html (DrumGizmo MuldjordKit) | **CC BY 4.0** (LICENSE.txt + page) | Shippable **with credit** | "Drum samples provided by DrumGizmo.org (MuldjordKit by Lars Muldjord, CC-BY 4.0)" | 162 MB |
| `studio-kit` | Karoryfer Big Rusty Drums + VCSL claps/shaker (https://github.com/sfzinstruments/karoryfer.big-rusty-drums) | CC0 (both LICENSE files) | Shippable | none needed | 104 MB (a trimmed copy; the full Big Rusty repo is 589 MB) |
| `vcsl-mallets` | https://github.com/sgossner/VCSL | **CC0 1.0** (README: "Essentially public domain… no credit, no special terms") | Shippable | none | 168 MB |
| `vcsl-organ` | same | CC0 | Shippable | none | 68 MB |
| `vcsl-sax` | same | CC0 | Shippable | none | 135 MB |
| `drawbar-organ` | https://freepats.zenvoid.org/Organ/electric-organ.html | CC0 (readme) | Shippable | none | 6.3 MB |
| `freepats-guitar` | https://freepats.zenvoid.org/Guitar/acoustic-guitar.html | CC0 (`cc0.txt`) | Shippable (SF2 file) | none | 19 MB |
| `fsbs-clean-guitar` | https://freepats.zenvoid.org/ElectricGuitar/clean-electric-guitar.html | CC0 (LICENSE.txt) | Shippable | none | 124 MB |
| `wurlitzer` | https://github.com/sfzinstruments/GregSullivan.E-Pianos | **CC BY 3.0** (README; the GitHub licence label says "NOASSERTION" but the README is clear). Author gave permission "with the request for attribution". | Shippable **with credit** | "Wurlitzer EP200 samples by Greg Sullivan (CC-BY 3.0)" | 2.5 MB |
| `musescore-general` | https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/ | **MIT** (FluidR3 by Frank Wen, FluidR3Mono, S. Christian Collins), "acknowledgements and copyright notices above must be included in any derivative work" | Shippable **with the licence file travelling alongside** (`MuseScore_General_License.md`). Quality is General-MIDI level, so it is a fallback, not a score instrument. | Keep the licence file with the SF2 | 206 MB |

**Net result: all 19 packs are shippable.** Four need a visible credit line (Salamander, MuldjordKit, Wurlitzer = CC BY; MuseScore General = keep its MIT notice). None is GPL, non-commercial, or no-derivatives. Rows for the app's `ATTRIBUTIONS.md` are the credit texts above.

One small catch: the VSCO readme's "do not sell the samples directly" is a request on top of CC0 (a public-domain dedication cannot legally be restricted). We are not selling the samples on their own (MIT app that bundles them), so there is no conflict, but the app should never present the library as a paid add-on.

### 1.2 What each pack gives an orchestral cinematic cue

| Need | What we have now | Notes |
|---|---|---|
| **Strings, sections** | `vsco2-strings`: Violin / Viola / Cello **section** (`…EnsSusVib`, `…EnsSusVib-Quiet`, `…EnsSpic`, `…EnsTrem`, `…EnsPizz`), Contrabass solo (`ContrabassSusVB`, `SusNV`, `SusVB-Quiet`, `Spic`, `Trem`, `Pizz`), Solo Violin (`SViolinVib`, `Vib-Quiet`, `Spic`, `Trem`, `Pizz`), Harp | Sustain with vibrato, soft sustain, spiccato, tremolo, pizzicato. **No sul pont, no col legno, no legato, no harmonics.** Violas/cellos are "Ens" (8-ish player section recordings), so the section feel is real. Basses are a *solo* bass, not a section. |
| **Solo cello / bass** | `bigcat-cello` (bowed sustain + staccato + marcato script, plucked), `dsmolken-bass` (arco + pizz, key-switched), `growlybass` (bass guitar) | Cello is a good solo voice for an intimate moment; double bass pizz adds weight. |
| **Horns / trumpet / trombone / tuba** | `vsco2-brass`: F Horn (sus, stac, **muted**), Trumpet (sus, sus vibrato, stac, straight mute), Tenor Trombone (sus, vib, stac), Tuba (sus, stac) | Single players, not sections. Good for fanfare, stabs, a tuba pedal. **No bass trombone, no sforzando/fp swells, no cluster "wall of brass".** |
| **Woodwinds** | `vsco2-woodwinds`: flute, piccolo, oboe, clarinet, bassoon (sus / non-vibrato / vib / stac); `vcsl-sax` tenor sax | Plenty for colour. |
| **Timpani** | `vsco2-percussion`: Timpani hits (round-robin) + **rolls** | The only orchestral drum installed. |
| **Bells / mallets** | `vcsl-mallets`: marimba, vibraphone, xylophone, glockenspiel, tubular bells | Good for the metallic accents of a score. |
| **Keys / organ** | `salamander-piano` (Yamaha C5, 16 velocity layers), `vcsl-organ` (pipe organ, loud registration), `drawbar-organ`, `wurlitzer` | Pipe organ + low strings is a cheap way to get weight. |
| **Drums / kits** | `muldjord-kit` (rock kit), `studio-kit` (Big Rusty kit + claps + shaker) | Modern-kit, not orchestral. |
| **Guitars / bass guitar** | `shinyguitar`, `freepats-guitar` (nylon), `fsbs-clean-guitar`, `growlybass` | Not for an orchestral cue; useful for a hybrid score. |
| **Harp** | `vsco2-strings/Harp.sfz` | Present. |

### 1.3 Gaps for a modern Arcane-style cinematic score

Arcane-style cues lean on: huge low brass, big taiko / ethnic and cinematic drums (hits, rolls, ostinati), synth bass and evolving pads, choir (often a wordless female or a stacked chorus), and processed/hybrid textures.

| Gap | Status today | What fills it (all listed only, nothing downloaded) |
|---|---|---|
| **Big low brass** (bass trombone, horn section, braams) | Single-player horn/trombone/tuba only | **Karoryfer War Tuba** (CC0, 103 MB repo; solo, duo and trio tuba, staccatissimo/staccato/sustain with breath and "yell" control — https://github.com/sfzinstruments/karoryfer.war-tuba). Stack a horn + trombone + tuba from VSCO2 with layering (the `Brass braam` already exists in the Freesound effects: `freesound/856173.ogg`). Virtual Playing Orchestra has a full brass section (see below) but is not clean to ship. |
| **Orchestral percussion beyond timpani** (bass drum, cymbals, gong, snare, toms) | Only timpani is installed (`vsco2-percussion`) | **Already inside the repos we use, just not installed.** Full VSCO 2 CE (CC0) has `bassdrum`, `BDrumNewhit` (7 velocity layers × 2 round robins, ~8 MB), `cymbal`, `susCymb1`, `gongHit` (21 MB), `gongscrape`, snare, triangle, and a 108 MB "VSCO 1 Percussion/drums" folder. **VCSL** (CC0) has Bass Drum 1/2/3, Clash Cymbals 1 & 2, Suspended Cymbal 1 & 2 (~50 MB each), Gong 1 (31 MB), Tom 1 & 2, Frame Drum, Snare sets, Anvil, Brake Drum, Tubular Bells, Timpani 1 & 2 (82 / 292 MB). Pulling bass drum + cymbals + gong + toms from VCSL costs roughly 150–250 MB. |
| **Taiko / ethnic drums** | None | **No clean CC0 taiko library found.** FreePats "World percussion" is CC0 but only has cajón, bongos, conga, darbuka, claves, tambourine, castanets, shaker, maracas, hand clap (6.6 MiB FLAC, https://freepats.zenvoid.org/Percussion/world-and-rare-percussion.html). VCSL has Frame Drum, Slit Drum, Darbuka, Conga, Bongos, Cajon, Ocean Drum. Karoryfer `body_percussion` (CC0, 37 MB) and `virtuosity_drums` (CC0, 1.2 GB — too big) exist. Taiko search turned up only paid libraries or unlicensed free ones. **Plan:** fake a taiko from VCSL Bass Drum 2 + low tom (pitched down, long reverb tail) or from big Freesound CC0 impacts; flag as a known gap. |
| **Synth bass / synth pads** | Only the guitar-family and organs | **FreePats Synthesizer #1/#2** (https://freepats.zenvoid.org/Synthesizer/synth-pad.html, **CC0 1.0**): Synth Pad Choir (6.5 MiB FLAC), Sweep Pad (2.9), New Age (4.3), Synth Pad Bowed (11), plus Synth Bass, Synth Strings, Synth Brass pages on the same site. **Karoryfer Caveman Cosmonaut** (virtual-analogue organ-synth, 92 MB repo, CC0 label; readme says "royalty-free", LICENSE file present) and **Cowsynth** (13 MB, CC0). **VCSL TX81Z** FM sounds (Clavisynth, FM Piano, Piano 1; CC0, ~30–70 MB each). All small. |
| **Choir** | None | **FreePats "Synth Pad Choir"** (CC0, 6.5 MiB) is a synthetic choir pad, not a real choir. **Karoryfer 272 Merry Orks** (female vocal library, CC0, 38 MB repo). **VPO "Vocals" folder** and **Sonatina Symphonic Orchestra** chorus (3 instruments) exist but their licences are not clean (below). No clean real-choir SFZ confirmed. A wordless choir from ACE-Step or a stacked, pitched vocal pad is the realistic route. |
| **Orchestral strings sections: basses, legato, sul pont, col legno** | Solo bass only; no legato | **Karoryfer String Cyborgs** (CC0, 60 MB repo) — sampled strings turned into playable synth-like instruments. VPO has the full string section set but see licence. Honest answer: legato and special bowing are a real gap. |
| **Hybrid/cinematic textures (braams, risers, drones, sub drops)** | Not instruments | **Already in the effects library** (`freesound/` CC0 files, Section 2). |

### 1.4 Other orchestral libraries we looked at (not for the installer)

| Library | Licence (from its own page / README) | Size | Verdict |
|---|---|---|---|
| **Virtual Playing Orchestra 3.3** — https://virtualplaying.com/virtual-playing-orchestra/ | Mixed per sample source: Sonatina Symphonic Orchestra = *CC Sampling Plus 1.0*; Mattias Westlund additions = **CC BY-SA 3.0**; No Budget Orchestra = **CC BY-SA 4.0**; VSCO 2 CE = CC0; Univ. of Iowa = free use; stamperadam = CC0. Author: no restrictions on *making music*, but "do not repackage and sell the library"; redistribution needs credit and derivatives must stay free. | WAV set 603 MB (+0.5 MB scripts) | **Usable, not shippable.** The Share-Alike (CC BY-SA) parts would drag our installer's sample set into SA terms. Fine for a user to download for themselves; never bundle. 603 MB is also over the 300 MB limit set for this brief. |
| **Sonatina Symphonic Orchestra** (Mattias Westlund) | CC Sampling Plus 1.0 (not CC0; "Sampling Plus" restricts using the samples in advertising and requires credit) | ~440 MB torrent | **Usable, not shippable.** 57 SFZ instruments incl. 12 brass, 3 chorus, 10 percussion, 16 strings — the most complete free set. Over the size limit. |
| **No Budget Orchestra** | CC BY-SA 4.0 (per VPO's page) | not checked | **Usable, not shippable** (Share-Alike). |
| **G-Town Church Sampling Project** | CC Sampling Plus | 435 MB | Usable, not shippable. |
| `DrumGizmo.DRSKit` / `SamsSonor` / `WilkinsonAudio.NakedDrums` (sfzinstruments org) | CC BY 4.0 / **CC BY-SA 4.0** / CC BY 4.0 | 718 MB / 34 MB / 1.2 GB | SamsSonor SA = not shippable; the rest too big. Not needed. |

*Source for the sfzinstruments table (licence label + repo size per repository): GitHub API, https://api.github.com/orgs/sfzinstruments/repos, read 2026-10-21. VCSL contents: https://github.com/sgossner/VCSL (tree via API). VSCO 2 CE contents: https://github.com/sgossner/VSCO-2-CE (tree via API).*

### 1.5 Recommendation for the next brief

1. Install, from repos we already trust (all CC0): VCSL **Bass Drum 1+2, Clash Cymbals 1, Suspended Cymbal 1, Gong 1, Tom 1+2, Frame Drum** (~200 MB), VSCO 2 CE `bassdrum` / `cymbal` / `gongHit` (small), **War Tuba** (103 MB), FreePats **Synth Pad Choir + Sweep Pad + Synth Pad Bowed** (~20 MiB).
2. Treat **taiko and real choir as known gaps** until someone finds a CC0 source (or we record/synthesise). Do not substitute a Share-Alike library.
3. The installed `studio-kit` is a trimmed copy; keep it as is.

---

## 2. Effects libraries

### 2.1 Licence re-check (pages read 2026-10-21)

| Pack | Source page | What the page says | Ship? |
|---|---|---|---|
| `kenney-interface` (100 files, 1.2 MB) | https://kenney.nl/assets/interface-sounds | "Creative Commons CC0" (links to CC0 1.0). No credit asked. | **Shippable** |
| `kenney-ui` (52 files) | https://kenney.nl/assets/ui-audio | "Creative Commons CC0" | **Shippable** |
| `kenney-impact` (130 files) | https://kenney.nl/assets/impact-sounds | "Creative Commons CC0" | **Shippable** |
| `kenney-digital` (63 files) | https://kenney.nl/assets/digital-audio | "Creative Commons CC0" | **Shippable** |
| `owlish` (161 files, 203 MB) | https://opengameart.org/content/sound-effects-pack — author OwlishMedia | "CC0", no attribution instructions | **Shippable** |
| `bigsoundbank` (210 files, 256 MB) | https://bigsoundbank.com/licence.html — Joseph Sardin | Offers **CC0 1.0**, WTFPL, or Public Domain (our choice); "Use, including for commercial purposes", redistribution allowed "by all means and in all formats", no permission needed; credit "not mandatory, but definitely appreciated". **We pick CC0.** | **Shippable** (courtesy credit "Sounds by Joseph Sardin, bigsoundbank.com") |
| `freesound` (54 files, 21 MB) | https://freesound.org (each file's own page; I re-read `syntheffects/sounds/685256`: "Creative Commons 0") | Per file CC0, listed with author and page in the experiment's `picks.json` (copied to the scratch folder) | **Shippable.** Caveat that still stands from the experiment: Freesound's *API* terms forbid commercial use of the API itself, so installs must use the public pages / our own mirror, not the API. |

Re-confirmed: nothing changed from the experiment's findings in `docs/SOUND_LIBRARY.md`. (Rejected back then and still rejected: Sonniss GDC bundles, BBC RemArc, Pixabay, Mixkit audio, ZapSplat, Soundly, 99Sounds.)

### 2.2 Candidates for a 20-second cinematic effects pass

Paths are under `C:\Users\Sam\.rostrum\assets\sounds\`. Length is the file's real length (ffprobe). "Feel" comes from the name / title / the experiment's catalogue tags — **I did not listen to them** (research only), so treat the last column as a label, not a verdict. Full inventory of all 768 files with lengths: `C:\Users\Sam\.rostrum\waves\scratch\priyam-p1\libraries\effects_inventory.csv`.

| # | File | Sec | What it is |
|---|---|---:|---|
| **Whooshes** |||
| 1 | `bigsoundbank\1797.ogg` | 0.54 | Whoosh #6, short air pass |
| 2 | `bigsoundbank\1800.ogg` | 0.89 | Whoosh #7 |
| 3 | `bigsoundbank\1796.ogg` | 1.04 | Whoosh #4 |
| 4 | `freesound\171321.ogg` | 1.85 | Fast swoosh |
| 5 | `freesound\683101.ogg` | 2.05 | Quick woosh |
| 6 | `freesound\27281.ogg` | 5.07 | "Epic whoosh", long |
| 7 | `freesound\649445.ogg` | 5.27 | Cinematic woosh |
| 8 | `bigsoundbank\0128.ogg` | 0.55 | Sword through the air |
| **Cloth / foley** |||
| 9 | `freesound\495390.ogg` | 6.93 | Foley whoosh, clothes |
| 10 | `freesound\391448.ogg` | 11.56 | Shirt whoosh |
| 11 | `owlish\Cloth, Rustle\320138__owlstorm__blanket-movement-2.wav` | 2.05 | Blanket movement |
| 12 | `owlish\Cloth, Rustle\320142__owlstorm__blanket-movement-4.wav` | 2.17 | Blanket movement |
| 13 | `owlish\Cloth, Rustle\320144__owlstorm__blanket-movement-6.wav` | 1.16 | Short cloth rustle |
| 14 | `bigsoundbank\1104.ogg` | 8.39 | Synthetic coat rubbed |
| 15 | `bigsoundbank\1787.ogg` | 1.15 | Flag flap (fabric snap) |
| 16 | `owlish\Impacts\shouldergrab.wav` | 4.37 | Grab / body movement |
| **Impacts / booms** |||
| 17 | `freesound\430977.ogg` | 5.43 | Big impact |
| 18 | `freesound\408141.ogg` | 6.98 | Cinematic low-pitch impact |
| 19 | `freesound\222517.ogg` | 7.04 | Dramatic hit |
| 20 | `freesound\165109.ogg` | 11.86 | Low movie boom |
| 21 | `freesound\671306.ogg` | 7.50 | Cinematic hit, bass (title) |
| 22 | `freesound\431316.ogg` | 7.75 | Braam hit |
| 23 | `freesound\856173.ogg` | 4.00 | Brass braam impact |
| **Sub drops / risers** |||
| 24 | `freesound\428073.ogg` | 3.76 | Sub drop, smooth |
| 25 | `freesound\212768.ogg` | 4.80 | Bass drop |
| 26 | `freesound\475005.ogg` | 2.79 | Synth bass drop impact |
| 27 | `freesound\683667.ogg` | 4.01 | Dark riser build-up |
| 28 | `freesound\244249.ogg` | 14.58 | Impact riser |
| 29 | `freesound\503818.ogg` | 19.91 | Long riser |
| 30 | `freesound\110218.ogg` | 3.07 | Reverse crash |
| **Metal / glass / wood / doors** |||
| 31 | `kenney-impact\Audio\impactMetal_heavy_000.ogg` | 0.17 | Metal hit, heavy |
| 32 | `kenney-impact\Audio\impactPlate_heavy_000.ogg` | 0.49 | Plate hit, heavy |
| 33 | `kenney-impact\Audio\impactBell_heavy_000.ogg` | 1.48 | Bell hit, heavy |
| 34 | `kenney-impact\Audio\impactWood_heavy_000.ogg` | 0.31 | Wood hit, heavy |
| 35 | `bigsoundbank\1483.ogg` | 14.75 | Gong, strong |
| 36 | `bigsoundbank\0148.ogg` | 1.91 | Glass burst |
| 37 | `bigsoundbank\1339.ogg` | 0.76 | Door slam |
| 38 | `bigsoundbank\3205.ogg` | 3.16 | Creaking door |
| 39 | `bigsoundbank\1320.ogg` | 5.52 | Key in an entrance door |
| **Footsteps / water** |||
| 40 | `owlish\Footsteps\hard-footstep1.wav` | 0.58 | Hard-floor step (also `-2` 0.49, `-3` 0.58, `-4` 0.71) |
| 41 | `kenney-impact\Audio\footstep_wood_000.ogg` | 0.25 | Wood step (five takes `_000`–`_004`) |
| 42 | `owlish\Footsteps\stumble.wav` | 0.84 | Stumble |
| 43 | `bigsoundbank\1519.ogg` | 3.27 | Big splash #1 (also `1520` 7.41, `1521` 4.10) |
| 44 | `bigsoundbank\1529.ogg` | 2.62 | Small splash |
| **Ambience beds / drones** |||
| 45 | `freesound\203119.ogg` | 34.94 | Tense surreal drone |
| 46 | `freesound\371194.ogg` | 43.00 | Cinematic monster drone in C |
| 47 | `freesound\617518.ogg` | 233.52 | Tension ambience (long bed) |
| 48 | `bigsoundbank\0146.ogg` | 78.65 | Strong wind |
| 49 | `bigsoundbank\0124.ogg` | 42.89 | Rain and thunder |
| 50 | `owlish\Ambience\earthquake.wav` | 71.00 | Earthquake rumble |

**What is thin:** real *footsteps with cloth* movement together, convincing *water flow* (we have splashes, bubbles, pours, sea), and *metal scrapes / chains* (only the Kenney metal hits and the BigSoundBank gong / cymbal). For the padlocked-door test clip below, the metal ring + padlock clank is the hardest event to cover; best bets are `kenney-impact\impactMetal_*` and `impactPlate_*` (short, bright) layered with `bigsoundbank\1320.ogg` (key in door) and a gong tail trimmed short.

---

## 3. ACE-Step 1.5 — licence and requirements (research only)

Sources: https://github.com/ACE-Step/ACE-Step-1.5 (README, `pyproject.toml`, `docs/en/INFERENCE.md`, `docs/en/GPU_COMPATIBILITY.md`, `acestep/core/generation/handler/init_service_orchestrator.py`), https://huggingface.co/ACE-Step/Ace-Step1.5 (model card + file tree via the HF API). Read 2026-10-21. Paper: arXiv 2602.00744.

### 3.1 Licences

| Part | Licence | Notes |
|---|---|---|
| **Code** | **MIT** (GitHub `LICENSE`: "Copyright (c) 2026 ACEStep"; `pyproject.toml` `license = {text = "MIT"}`) | Clean. |
| **Weights** | **MIT** (HF repo tag `license:mit`; model card line "License: [MIT]") | The card says generated music may be used "strictly for commercial purposes" and lists no other restrictions. **Weak spot:** the HF repo has no separate LICENSE *file*, so the tag and card line are the only statement. A community comment on the HF discussions (https://huggingface.co/ACE-Step/Ace-Step1.5/discussions/27) asks the authors to add one. For a shipping product, ask the authors or keep a screenshot of the card; for the proof it is fine. |
| **Training data** | Model card: "legally compliant" mix of licensed tracks, royalty-free / public-domain music, and MIDI-to-audio synthetic data | We have no way to audit this. Record it as "per the authors". |
| **Qwen text/LM bases** | The LM planner is built from Qwen3 (0.6B / 1.7B / 4B); the text encoder is `Qwen3-Embedding-0.6B` | Qwen3 and Qwen3-Embedding are Apache-2.0 as far as I know, but **I did not confirm this on their model cards** in this pass. Check before shipping. |
| **Captioner / transcriber (optional)** | Same HF discussion says the 7B Qwen2.5-Omni is Apache-2.0 but the **3B variant is under the Qwen research (non-commercial) licence**, and the tech report does not say which size was used | Only matters if we use the optional caption/transcribe features, which the proof does not. Do not install those parts. |

**GPL / copyleft check of the direct dependencies** (from `pyproject.toml`): torch, torchvision, torchaudio, torchao, torchcodec, transformers, diffusers, accelerate, gradio, fastapi, uvicorn, scipy, soundfile, loguru, einops, numba, vector-quantize-pytorch, diskcache, toml, modelscope, pytorch-wavelets, pywavelets, peft, lycoris-lora, lightning, tensorboard (training only), nano-vllm (bundled at `acestep/third_parts/nano-vllm`). **I found no GPL / AGPL package among them.** Two things to watch: (a) `torchcodec` needs a system FFmpeg, and a GPL-built FFmpeg would be GPL (use an LGPL build — we already plan FFmpeg LGPL); (b) I did **not** audit the *transitive* dependencies or `nano-vllm`'s own licence. Since ACE-Step would run as a separate helper process (never linked into our app), copyleft dependencies could not infect the app anyway, but a full `pip-licenses` run should go in the proof report.

### 3.2 Models and sizes

From the HF API file tree (main branch of `ACE-Step/Ace-Step1.5`, measured today):

| Component | What it is | Size |
|---|---|---:|
| `acestep-v15-turbo` | **DiT** (music generator), 2B-class, 8 steps, no CFG, "very high quality" per the card | **4.79 GB** |
| `vae` | Audio autoencoder (48 kHz stereo output) | 0.34 GB |
| `Qwen3-Embedding-0.6B` | Text encoder for the prompt | 1.21 GB |
| `acestep-5Hz-lm-1.7B` | **LM planner** ("thinking", writes song structure / metadata) | 3.76 GB |
| Other DiTs and LMs (separate repos): `acestep-v15-sft` (50 steps, higher quality / less diversity), `acestep-v15-base` (50 steps), `acestep-5Hz-lm-0.6B` (weak), `acestep-5Hz-lm-4B` (strong), XL (4B) DiTs (~9 GB bf16) | — | not downloaded |

Main-repo total is about **10.1 GB**. With the LM off (what a 4 GB card uses) you only need turbo + VAE + text encoder ≈ **6.3 GB** on disk.

### 3.3 Memory and speed

- **Official minimum:** the README says it "runs locally with less than 4 GB of VRAM".
- `docs/en/GPU_COMPATIBILITY.md`: ≤4 GB tier = **no LM, 2B turbo DiT, backend `pt`, CPU offload of DiT + VAE + text encoder, INT8 quantization (mandatory ≤6 GB), batch 1, max duration 6 min (no LM)**. 4–6 GB tier: same, max 10 min.
- XL (4B) DiTs: ≥12 GB with offload + quantization — **not for the RTX 3050 4 GB**.
- **Quantization:** `quantization="int8_weight_only"` (uses `torchao`). **CPU offload:** `offload_to_cpu=True`. Both are keyword arguments of `AceStepHandler.initialize_service(...)`, along with `use_flash_attention` and `compile_model` (checked in the source).
- **Speed:** only data-centre numbers are published ("under 2 s per full song on an A100, under 10 s on an RTX 3090"). **There is no published time for a 4 GB laptop GPU.** My *guess*, not a measurement: with INT8 + full offload on a 3050 Laptop, 8-step turbo for a 30–60 s clip should land somewhere between about 30 s and 3 minutes, dominated by moving weights between RAM and the GPU. **The lead must time it** — that is a proof output. The Windows PyTorch pin is `torch 2.7.1+cu128`, which does support the RTX 30-series.
- Duration limits: 10 s to 10 min per call. Output default 48 kHz, FLAC.

### 3.4 Install steps (Windows, run as the lead, one `gpu` heavy job each for the download and the first generation)

Do this **outside the repo**, so no 10 GB of weights land in the worktree:

```powershell
# 0. uv must exist (it is the team's Python tool). Python 3.11 or 3.12 only (pyproject: >=3.11,<3.13).
$ACE = "C:\Users\Sam\.rostrum\models\ace-step"
New-Item -ItemType Directory -Force $ACE | Out-Null
git clone https://github.com/ACE-Step/ACE-Step-1.5.git "$ACE\repo"
Set-Location "$ACE\repo"
uv sync                      # makes .venv, installs torch 2.7.1+cu128 from download.pytorch.org/whl/cu128, torchao, etc.
```

Weights download automatically on first run into `checkpoints\` of the repo (`acestep/model_downloader.py`); to fetch only what a 4 GB card needs, ask for the turbo DiT and leave the LM out. First launch of the UI (`uv run acestep`, http://localhost:7860) or the API (`uv run acestep-api`, port 8001) also downloads. For a scripted run, use the Python call below. Hold the heavy-job lock for the download and for every generation:

```powershell
pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "priyam: ace-step first run" gpu `
  "$ACE\repo\.venv\Scripts\python.exe" "$ACE\gen_instrumental.py" 30 "C:\Users\Sam\.rostrum\waves\results\p-snd\priyam\acestep"
```

`gen_instrumental.py` (to be written by the lead; kept out of the repo until it works — this is the call from `docs/en/INFERENCE.md`, with the 4 GB settings from the source):

```python
import sys
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

seconds, out_dir = float(sys.argv[1]), sys.argv[2]
dit = AceStepHandler()
dit.initialize_service(
    project_root=r"C:\Users\Sam\.rostrum\models\ace-step\repo",
    config_path="acestep-v15-turbo",
    device="cuda",
    offload_to_cpu=True,              # 4 GB card
    quantization="int8_weight_only",  # mandatory <=6 GB
)
llm = LLMHandler()                    # never initialised: LM stays off on 4 GB

params = GenerationParams(
    caption="dark cinematic orchestral hybrid, low strings ostinato, deep brass swells, taiko-style drums, tense and rising, no vocals",
    lyrics="[Instrumental]",
    instrumental=True,
    duration=seconds,
    thinking=False,                   # no LM planner (documented way to switch it off)
    inference_steps=8,                # turbo
    shift=3.0,                        # recommended for turbo
    seed=1234,
)
cfg = GenerationConfig(batch_size=1, audio_format="wav")
result = generate_music(dit, llm, params, cfg, save_dir=out_dir)
for a in result.audios:
    print(a["path"])
```

Things I could **not** confirm from the docs, so the lead should check on the first run (and fix the script, not the docs): that `generate_music` accepts a never-initialised `LLMHandler` when `thinking=False` (the docs never show `None`/uninitialised); that `lyrics="[Instrumental]"` is the expected placeholder (the `instrumental=True` flag should already force it); that the `wav` value is accepted for `audio_format` (documented default is `"flac"`). If anything fails, read `acestep/inference.py`. The repo also has `python cli.py --configure` (a wizard that writes a `.toml`, then `python cli.py --config config.toml`) as a fallback.

### 3.5 Other facts that matter for the proof

- Supports text-to-music, cover, repaint, extract, "lego", complete, vocal-to-BGM; prompts in 50+ languages; LoRA training exists (about 1 hour for 8 songs on a 12 GB RTX 3090, so not on our machine).
- Windows and macOS have **portable packages** with dependencies pre-installed (README) if `uv sync` is slow.
- Not a mixing tool: it returns a stereo bounce. Stems are not documented as an output, so for the Editor/Sound pipeline treat it as a *reference / draft generator*, not the final audio engine (consistent with AGENTS rule 9, one audio engine).

---

## 4. Test clip for the effects pass

**Chosen: "Man tries to open a padlocked wooden door" (Mixkit, clip 35896).**

| Field | Value |
|---|---|
| File | `C:\Users\Sam\.rostrum\waves\scratch\priyam-p1\libraries\clip\padlocked-door-35896-720.mp4` |
| Source page | https://mixkit.co/free-stock-video/man-tries-to-open-a-padlocked-wooden-door-35896/ |
| Direct file | https://assets.mixkit.co/videos/35896/35896-720.mp4 |
| Length / format | **20.40 s**, 1280×720, H.264, 25 fps, 7.4 MB |
| Audio | **None. The file has no audio stream at all** (ffprobe shows one video stream), so there is nothing to strip; the whole soundtrack will be ours. |
| Licence | **Mixkit "Stock Video Free License"** (https://mixkit.co/license/). Mixkit's page says the clips are free to download without watermark and usable in video projects under that licence. **I could not read the licence's full text** (it loads in a pop-up that the page fetch did not return), so I am relying on Mixkit's own summary. **It is not CC0.** |
| Author | Mixkit does not show the filmmaker's name on the page. |
| Use | **Private proof only.** Do not commit it to the repo, do not put it in a public demo, do not redistribute it. |

**Why not a CC0 clip:** Pexels and Pixabay block automated downloads (HTTP 403 / Cloudflare), and a Wikimedia Commons search for CC0 videos of falls, doors or splashes turned up only a few tiny clips with no clear events. Mixkit clips download straight from `assets.mixkit.co`. If Sam wants a CC0 clip, a human can grab one from Pexels in a browser (e.g. https://www.pexels.com/video/an-avocado-falling-into-water-8212411/ — Pexels licence, not CC0, but no attribution needed).

**What it is:** one fixed close-up of an old wooden panel door with a heavy iron ring and a brass padlock hanging from it. A man in a beige jacket pushes, pulls, shakes and rattles it. It is a quiet, tactile clip: wood, iron ring, brass padlock, sleeve cloth, hands on timber. There is no footstep and no water. It suits a **foley** pass (metal clank, wood knock, cloth movement) more than a big cinematic hit pass; the big impacts and risers would have to be *added* to the picture by the cue, not triggered by it.

### 4.1 On-screen events (I looked at frames every 0.52 s on four contact sheets, then checked the timing against frame-difference motion energy; ±0.1–0.2 s unless noted)

Motion peaks come from `ffmpeg … tblend=difference,signalstats` (data in `…\libraries\motion.txt`). Contact sheets: `…\libraries\frames\sheet0.jpg` – `sheet3.jpg`; single frames every 0.5 s: `…\frames\f_001.jpg` – `f_041.jpg`.

| # | Time (s) | Event | Sound it wants |
|---|---:|---|---|
| 1 | 0.0–0.3 | Static shot. Ring and padlock hanging still, lock turning slightly | room tone, tiny ring creak |
| 2 | 0.3–0.6 | Arm in beige sleeve enters from the left | cloth movement |
| 3 | 1.0–1.2 | Hand takes the iron ring, lock swings | metal ring + padlock clink |
| 4 | 1.2–1.9 | Ring and padlock yanked / rattled (strong motion) | metal rattle, brass clank |
| 5 | 2.0 | Hand lands flat on the door | soft palm on wood |
| 6 | 2.6–4.4 | Palm held and pressing the door; slow slide | wood creak, cloth rustle |
| 7 | 4.6 | Ring/padlock swings as the hand leaves it (peak) | single metal clink |
| 8 | 5.0–5.9 | Hand pushes hard on the door (peak ~5.6–5.8) | wood push, door flex |
| 9 | 6.0–7.4 | Arm held on the door, sleeve wrinkling | cloth, low wood groan |
| 10 | 7.6 | Hand sweeps past the ring, brushing it (largest early peak) | ring brush / short metal rattle |
| 11 | 8.3–8.8 | Hand takes the ring again | metal, ring scrape |
| 12 | 9.2–9.6 | Both hands: one slaps the door beside the ring, ring swings, watch seen | palm slap on wood + clink |
| 13 | 9.9–10.4 | Second palm lands on the door | wood tap |
| 14 | 10.8 | Hand pulls away; padlock swings (peak) | brass swing, small clink |
| 15 | 11.8–13.8 | Palm pushing the door with padlock dangling and swaying | steady wood creak, small clinks |
| 16 | 14.0 | Brief stillness (lowest motion) | beat / breath |
| 17 | 15.0 | Hand sweeps across the door (peak) | palm swipe on wood |
| 18 | 15.6–16.0 | Arm in, hand hits ring (strongest peak at **16.0**) | metal clank + padlock swing |
| 19 | 16.4–16.9 | Hand withdraws; lock swings out | swinging brass, fading clinks |
| 20 | 17.0–20.4 | **No one in shot.** Padlock slowly settles to rest, nothing else moves | long tail: room tone, last ring creaks |

Suggested hit points for a score: 1.2 (grab), 5.6 (push), 9.4 (slap), 16.0 (clank). The quiet last 3.4 s are a natural place for a riser tail or a held drone.

---

## Downloads made for this report

| Item | Licence | Size |
|---|---|---|
| `padlocked-door-35896-720.mp4` (Mixkit 35896), in `…\scratch\priyam-p1\libraries\clip\` | Mixkit Stock Video Free License (not CC0; private proof only) | 7.4 MB |
| Small text files used for research (`picks.json`, `effects_inventory.csv`, `motion.txt`, contact sheets and 41 frame JPGs) | n/a (ours / derived) | < 5 MB total |

Nothing else was downloaded; no model, no GPU, no installs. Temp files in `C:\Users\Sam\AppData\Local\Temp` and `/tmp` (JSON from the GitHub API, one HTML page) are small and can be ignored.
