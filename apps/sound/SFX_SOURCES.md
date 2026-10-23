# Where better sound effects can come from

*Team Priyam, P7, 2026-10-21. For Sam to choose. All terms were read on 2026-10-21. This is not legal advice.*

Sam's verdict on P6 was that the designed sounds were "the same thing, just more metallic". Making the sounds from
scratch doesn't reach an Apple launch film. The tools that read the motion, sync each sound and glue them on one bus
are right. What's missing is better recordings to start from. This page lists every source we may use under our
rules (MIT app; nothing GPL or non-commercial).

**I can't hear.** Every "quality" note below is measured, not heard: the file format, how much hiss there is, how sharp
a click's start is, and how high its sound reaches. Those numbers show whether a recording is clean. Whether it sounds
good is for your ear.

## Listen first

*Old listening page (2026-10: before the no-whoosh rule, PURPOSE.md). Rostrum no longer makes or ships whooshes; the page stays as a record of how the recordings compare.*

The same 10-second slide deck from P6, scored four ways. The placement is identical in each: every sweep peaks when
its card moves fastest, the sound pans with the card, clicks land on the frame, and all of it goes through the same
glue bus. **Only the recordings change.** All are at −16 LUFS (the same loudness).

| File | Recordings used | Can we ship them? |
|---|---|---|
| `C:\Users\Sam\.rostrum\waves\results\stage2\sound-sources\slides-sonniss.mp4` | Sonniss GDC bundles (professional sound designers, 96–192 kHz) | **No.** The user must download them |
| `C:\Users\Sam\.rostrum\waves\results\stage2\sound-sources\slides-free-to-ship.mp4` | Freesound CC0 sweeps + Kenney CC0 clicks and ticks | **Yes** |
| `C:\Users\Sam\.rostrum\waves\results\stage2\sound-sources\slides-freesound.mp4` | Freesound CC0 only | Yes |
| `C:\Users\Sam\.rostrum\waves\results\stage2\sound-sources\slides-kenney.mp4` | Kenney CC0 only. its sweep slots use UI "sweep" sounds | Yes |
| `C:\Users\Sam\.rostrum\waves\results\stage2\sound-sources\slides-designed-p6.mp4` | P6's designed sounds, for comparison | (ours) |

The `.wav` file next to each video is the same sound without the picture.

What the measurements say:
- **Sonniss** is clean all the way up to 20 kHz. Its hiss sits 60 to 140 dB below the sound.
- **The Freesound files** are the site's MP3 previews, the only thing we can get without an account. Their sound stops
  near 14 kHz, which is the preview format's limit, not the recordings'. The originals behind them are WAV files.
  These were the first search hits, not hand-picked. A person choosing by ear for an hour or two would do much better.
- **Kenney** is small, clean game-UI clicks, fine for ticks and presses. Clean and small.
- **Sync** (checked with `proofs/p6-motion-sfx/check_sync.py`): the sweeps peak within 5 ms of their card's fastest
  moment, except Sonniss's snapping card at 43 ms (its take has two swells). Every click and tick is within one frame (under 33 ms). Two exceptions: the four exits overlap, so the
  checker can't measure them separately; and the landing click under the snapping card is measured 35 ms off because
  that card's sweep covers it.

## 1. Sound-effect libraries

"Ship" means it goes in our installer. "On demand" means our app downloads it into the user's cache when asked.
"User brings it" means the user downloads it and points Rostrum at the folder.

| Library | What it has | Measured quality | Licence in one line | Verdict |
|---|---|---|---|---|
| **Sonniss GDC bundles** (free, 2015–2026, about 200 GB in total) | Real recordings: UI, mechanical clicks, foley, trailer hits, risers, from many pro designers (we use the real sounds, never its whooshes or transition effects) | Best of all: 24-bit, 96–192 kHz, very low hiss | Free for the user's own projects. Not allowed to "supply the sound effects as sound effects … as part of a … software development kit or anything similar". No AI use at all | **User brings it** |
| **BOOM Library free packs** | Cinematic hits, foley, motion | (needs an account; not downloaded) 96 kHz / 24-bit by their description | Royalty-free in the user's work; "may not be resold or redistributed as audio assets"; no AI training | **User brings it** |
| **Freesound, CC0 sounds** | Anything, of very mixed quality | From phone recordings to studio grade; must be picked by ear | CC0 (public domain) per sound | **Ship** a hand-picked set (downloaded once, by a person with an account). Not on demand: Freesound's terms say commercial use of the API is "negotiated on a case by case basis" |
| **Freesound, CC-BY sounds** | Same | Same | Free with credit | **Ship with a credits list**. CC-BY-NC sounds are **not allowed** |
| **Kenney** (UI Audio, Interface, Digital, Impact) | Clicks, ticks, toggles, soft impacts | Clean but small, game-style | CC0 | **Ship** |
| **OpenGameArt** (CC0 items only) | A few UI sounds | Hobby level, noisy | Per item | Ship CC0 items; little value |
| Pro Sound Effects free packs, Soundly free library | Broad pro libraries | Not downloaded (account needed) | Their licence text wouldn't open | **User brings it** (the cautious reading) |
| Zapsplat, Mixkit, Pixabay, Uppbeat | Lots of UI sounds | Not downloaded | All forbid handing the files on as files ("standalone", "without altering") or need an account | **User brings it** |
| 99Sounds | Cinematic packs | — | "no right to sell or redistribute (even for free)" | User brings it; can't ship |
| BBC Sound Effects | Huge archive | — | Non-commercial only | **Not allowed** |

Full notes, licence quotes and links: `C:\Users\Sam\.rostrum\waves\results\stage2\sound-sources\research\libraries.md`.
The evaluation samples are in `C:\Users\Sam\.rostrum\assets\sounds\eval\`. They are for listening only and never go
in the repo.

## 2. Models that make sound effects from words

Most good open models are **non-commercial**, so we can't use them. The allowed ones:

| Model | Where it runs | Licence / terms | Verdict |
|---|---|---|---|
| **ElevenLabs Sound Effects** | Cloud, with the user's own key | The user owns the output on a **paid** plan (free plan: non-commercial). WAV needs the US$99/month plan; cheaper plans give MP3. Clips up to 30 s | **Cloud OK** (paid plan). One open question: a competitor says ElevenLabs needs an Enterprise plan for film/TV. I couldn't find that on ElevenLabs' own pages, so we'd ask them in writing |
| **Stable Audio 3 / 2.5 API** (Stability) | Cloud, with the user's own key | US$0.08 a sound; free under US$1M yearly revenue; trained on licensed sounds | **Cloud OK** (a cheap backup) |
| **Stable Audio 3 Small SFX** (May 2026) | On the laptop, downloaded when the user asks | Stability Community Licence: free under US$1M yearly revenue, the user registers, outputs must not train other AI. Its text part also falls under Google's Gemma terms | **Local OK**, but only downloaded by the user after a plain licence screen, **never in our installer**. Small (0.6B); probably fits the 4 GB card (an estimate, untested) |
| **MOSS-SoundEffect v2.0** | On the laptop | Apache-2.0: the only fully permissive one found. 48 kHz | **Local OK** on licence. Probably too big for 4 GB without tricks; training data not disclosed; no independent tests |
| MMAudio, AudioGen / MAGNeT / AudioCraft, AudioLDM 1 and 2, Tango and Tango 2, TangoFlux, AudioX, Auffusion / FoleyCrafter | — | Non-commercial weights | **Not allowed** |
| HunyuanVideo-Foley | — | Not licensed in the EU, UK or South Korea, and that covers the outputs too | **Not allowed** (a worldwide app can't promise it) |
| ThinkSound | — | Labelled Apache-2.0, but its own page says "Commercial use is NOT permitted" | **Not allowed** |

No allowed **video-to-sound** model exists yet: every good one is non-commercial. Full notes and links:
`C:\Users\Sam\.rostrum\waves\results\stage2\sound-sources\research\models.md`.

## 3. The user's own library

Soundly, Splice, BOOM, Pro Sound Effects, Sonniss downloads, or a folder of the user's own recordings. These are the
user's files on the user's machine, licensed to the user, so using them in their own videos is normal under every
licence we read.
- **What Rostrum may do:** read the folder, cut long recordings into single sounds (the cut pool, `sfx/pool.py`),
  measure them and keep a local search index.
- **What it must not do:** copy the files anywhere except into the user's rendered video, upload them to a cloud model
  without asking, or train or tune any model on them. BOOM and Sonniss forbid AI training outright.
- Soundly and Splice have no public API. We read the files the user has on disk; there's no live link to their
  catalogues.

## Recommendation

**Let the user bring a pro library, and ship a small hand-picked free starter set.** On the listening page, the Sonniss
version is the only one at the level of the reference, and Sonniss is free for the user to download. Our part is
making a folder of it quick to use:
1. **Bring your own library:** point Rostrum at a folder (a Sonniss bundle, BOOM, Soundly exports …). It indexes and
   cuts the sounds once, and the agent and the person search them by kind ("click, short, bright"), length and
   measured shape. The motion tools place real sounds from it only when asked.
2. **A starter set in the installer:** a person picks about 150–300 CC0 sounds by ear, from Freesound originals and
   Kenney. It covers real sounds the picture needs (clicks, ticks, pops, impacts, foley), never whooshes or swishes (PURPOSE.md), at "good", not "Apple", level. It needs
   one or two hours of listening by someone with ears.
3. **Later, optional:** a sound-from-words model, behind the user's own choice (Stable Audio 3 Small SFX downloaded on
   request, or ElevenLabs with their key), after a short proof on this laptop.

## Choose (DECISION for Sam)

1. **Your own library + a free starter set (recommended).** Rostrum learns to use a sound folder you download (Sonniss,
   BOOM …). We ship a small hand-picked CC0 set so it works on day one.
2. **Option 1 + a sound-from-words model on the laptop.** We also test Stable Audio 3 Small SFX (downloaded only when
   the user agrees to Stability's terms) against the libraries by ear.
3. **Option 1 + cloud sound-from-words with the user's own key.** ElevenLabs or Stability, paid plans; nothing to
   download.
4. **Only what we can ship.** The CC0 starter set, nothing the user has to fetch. The simplest, but it stays at the
   "free-to-ship" level on the listening page.
