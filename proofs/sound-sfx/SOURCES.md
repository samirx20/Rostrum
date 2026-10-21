# P-SFX — close-foley sources (Team Hem, H4, member "sources")

*Written 2026-10-21. Nobody has listened to these takes yet: "what it is" comes only from titles, descriptions and the pack folder names. Nothing here is verified as close-mic or dry — that needs an audition (the lead's job).*

All files are in `C:\Users\Sam\.rostrum\assets\sounds\foley-h4\` (originals, untouched). Machine-readable list: `C:\Users\Sam\.rostrum\assets\sounds\foley-h4\takes.json` (`path, label, source_url, author, licence, seconds`). **261 takes**: 230 CC0, 31 CC-BY. Size: 35.6 MB of takes (51 MB folder, because it also keeps the two OpenGameArt zips as downloaded).

## Licence verdicts

| Source | Verdict | Redistribution inside the app's sound library? |
|---|---|---|
| **Freesound, CC0 sounds** (81 of the 112 Freesound takes) | **Clean.** Each sound page was fetched and its licence link read (`creativecommons.org/publicdomain/zero/1.0/`). | Yes. No credit needed. |
| **Freesound, CC-BY 3.0 / 4.0 sounds** (31) | **Usable with credit.** Page licence link checked: `.../licenses/by/3.0/` or `.../by/4.0/` (no NC, no SA). | Yes, if the credit line travels with the file (credit line column below). Needs an `ATTRIBUTIONS.md` row each. |
| **BigSoundBank** (40) — https://bigsoundbank.com/licenses.html, read 2026-10-21 | **Clean.** Terms quoted: "Use, including for commercial purposes", "Share, copy, distribute and communicate the material by all means and in all formats", "Adapt, remix, transform…", "Without asking permission", "Without any restrictions"; credit "not mandatory, but definitely appreciated" (`Additional sounds: Joseph SARDIN - BigSoundBank.com`). Each sound page says "License CC0 (public domain)". | Yes (CC0). |
| **OpenGameArt "100 CC0 metal and wood SFX"** (rubberduck, 51 of 100 files kept) — https://opengameart.org/content/100-cc0-metal-and-wood-sfx, read 2026-10-21 | **Clean**, page says CC0. These are game-style hits (small 15–30 KB ogg), probably not close-mic foley — low priority. | Yes (CC0). |
| **OpenGameArt "202 more sound effects"** (OwlishMedia, 58 of 202 kept: all Keys/Locks/Door and Cloth) — https://opengameart.org/content/202-more-sound-effects, read 2026-10-21 | **Clean**, page says CC0. WAV, appear to be close household foley (filenames only; not listened). Our existing `owlish` library folder is probably from the same author — not compared. | Yes (CC0). |
| **Sonniss GDC bundles** — https://sonniss.com/gdc-bundle-license/ and https://sonniss.com/gameaudiogdc, read 2026-10-21 | **Rejected for the app library; nothing downloaded.** Quote: "Licensee may not distribute, publish, sub-license or otherwise supply the sound effects as sound effects" (also covers "packs, libraries, SDKs, or templates"), and the licence forbids using them to train AI. Royalty-free "for personal and commercial projects" and sellable "as part of your finished … project". | **No.** At most usable inside a finished film for the proof; not shippable in the app. |
| **Pixabay sound effects** — https://pixabay.com/service/license-summary/, read 2026-10-21 | **Rejected for the library.** Quote: "You cannot sell or distribute Content … on a Standalone basis" ("no creative effort applied"). Redistributing it as app library content is that. Not downloaded. | **No.** |
| **Kenney** (CC0) | Clean, but already in our library (`kenney-impact`, `kenney-ui`…); nothing close-foley to add. | Yes. |
| **The Designer's Choice – Foley** (itch.io, Nicholas Judy; cloth, hands, props, 168 MB) — https://nicholasjudy567.itch.io/the-designers-choice-foley, read 2026-10-21 | **Not downloaded.** Page: "All sound effects are available to you on a complete royalty-free basis", "You can credit me or not"; the full terms are in a `License.txt` I could not read (itch download needs the site's download flow). Redistribution inside an app is **not stated**. | Unknown — **flag**. Worth a manual download + reading License.txt: it is a pro-style cloth/hands/props set. |
| Freesound HQ originals | Not used. Previews only (128 kbps mp3, fetched from `cdn.freesound.org/previews/…-hq.mp3`, no key). The full-quality WAVs need a login — good enough for the proof, but the app library should use originals. | — |

Every Freesound row's source URL is the sound's own page.

## What we got per target (counts of takes, see tables below)

- **Iron ring / door knocker**: 10 Freesound takes found by "door knocker" search (incl. `427111` buzzatsea "door knocker.WAV", `136544` jmdh "DoorKnockerVarious", `83240`, `610987` "old door knocker", `639658` "Knock on door metal"), plus 8 "metal ring / metal on metal" takes. None is described as ring-lift/drop-on-plate in close-mic; best guesses are `427111`, `136544`, `610987`.
- **Padlock**: 16 takes (`531519`, `445779`, `553258`, `632488` shackle/key turn, `536414` "Small Padlock Opening", `874473` "Padlock and Key Handling", `190035`, `391704` tiny padlock, `164670` "Lock rattle 5", `445900`, `718103`, `445596` "Padlock Clang"...), plus the Owlish and BigSoundBank key/lock sets.
- **Keys / small metal handling**: 15 Freesound + 7 `100 CC0` keys + 51 Owlish "Keys, Locks, Door" + BigSoundBank keys.
- **Wristwatch**: 3 (`388458` "Putting hand watch on table", `439639` "Watch Clasp Snap Closed", `810010` "Wristwatch Box, Shake"); bracelet/clink: `491749`, `682153`, `96134`, `96136`, `536780`, `738634`.
- **Hand on wood**: 28 (fingertip taps `567862`, palm/hand slide `560349`, `552615`, knocks `541492`, `233795`, `485167`, `697789` "3 soft door knocks", door push/wood `450350`, `870663`...) plus BigSoundBank door/knock/light-door and `100 CC0` wood_hit / wood_misc.
- **Fabric / sleeve**: 15 Freesound (jacket/cloth/coat; e.g. `555307` "Foley_Cloth_Movement_Jacket", `493505` "Clothes Rustling Movement", `163164` "heavy cloth rustle", `494797`, `641387`) + 7 Owlish "Cloth" + BigSoundBank `cloth`, `floor-cloth`.
- **Room tone**: 4 (`454166` "room tone medium quiet", `108400` "quiet room", `751709` klankbeeld "room-tone apartment", `716439` "Room Tone for Bedroom") — hum/noise not measured.

## What is still missing

- A real **close-mic ring knocker** take (ring lifted, ring dropped on its plate, ring rattle against iron). The "door knocker" hits are recordings of someone using a knocker on a door, mostly with room and street sound, not isolated ring-on-plate. This is the biggest gap.
- **Brass padlock hanging and swaying** (slow rattle, shackle brushing the body) — most padlock takes are open/close/key actions.
- **Tiny wood stress when a hand pushes a panelled door** (not a creak): only door close/open/creak takes were found.
- **Palm landing flat / palm slide on a panelled door**: only table/surface takes.
- **Sleeve rustle against a hard surface** (beige cotton jacket on a door, arm sliding): only generic cloth and jacket takes.
- Nothing has been auditioned. Expect that several takes carry room tone, other noise, or are not "dry"; the Freesound previews are lossy.
- Not tried / blocked: itch.io Designer's Choice (licence unread), Freesound HQ originals (login), Pixabay and Sonniss (licence forbids library use), sites such as Zapsplat (not checked). Possible next steps: one manual look at the Designer's Choice `License.txt`, and recording the five gaps ourselves.

## Attribution rows (for the manager to add to `ATTRIBUTIONS.md`)

Freesound CC-BY takes need one row each (title, author, URL, licence): they are the rows in the tables below with a credit line. CC0 sources need no attribution; courtesy credit "Sounds by Joseph Sardin, bigsoundbank.com" is already used for the existing BigSoundBank library. Not added to the repo's root file, per rules.

## Every downloaded take

### BigSoundBank (CC0) (40)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| bigsoundbank\0013_cloth.ogg | cloth | 10.08 | https://bigsoundbank.com/cloth-s0013.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0015_door.ogg | door | 4.36 | https://bigsoundbank.com/door-s0015.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0037_interior-door-lock.ogg | interior door lock | 2.77 | https://bigsoundbank.com/interior-door-lock-s0037.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0053_metal-box-lid.ogg | metal box lid | 5.46 | https://bigsoundbank.com/metal-box-lid-s0053.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0083_keys-thrown-on-wood-floors-1.ogg | keys thrown on wood floors 1 | 11.81 | https://bigsoundbank.com/keys-thrown-on-wood-floors-1-s0083.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0087_key-placed-on-wooden-table.ogg | key placed on wooden table | 18.55 | https://bigsoundbank.com/key-placed-on-wooden-table-s0087.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0095_door-knock.ogg | door knock | 10.3 | https://bigsoundbank.com/door-knock-s0095.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0176_mobile-key.ogg | mobile key | 12.8 | https://bigsoundbank.com/mobile-key-s0176.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0191_lock.ogg | lock | 9.46 | https://bigsoundbank.com/lock-s0191.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0224_light-door.ogg | light door | 17.71 | https://bigsoundbank.com/light-door-s0224.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0355_small-chain-1.ogg | small chain 1 | 1.88 | https://bigsoundbank.com/small-chain-1-s0355.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0356_small-chain-2.ogg | small chain 2 | 1.04 | https://bigsoundbank.com/small-chain-2-s0356.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0357_small-chain-3.ogg | small chain 3 | 1.75 | https://bigsoundbank.com/small-chain-3-s0357.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0358_small-metal-chain-4.ogg | small metal chain 4 | 0.81 | https://bigsoundbank.com/small-metal-chain-4-s0358.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0359_heavy-chain.ogg | heavy chain | 4.26 | https://bigsoundbank.com/heavy-chain-s0359.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0360_medium-chain-1.ogg | medium chain 1 | 1.83 | https://bigsoundbank.com/medium-chain-1-s0360.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0361_medium-chain-2.ogg | medium chain 2 | 2.04 | https://bigsoundbank.com/medium-chain-2-s0361.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0374_knock-on-a-light-door.ogg | knock on a light door | 6.79 | https://bigsoundbank.com/knock-on-a-light-door-s0374.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0377_opening-and-closing-light-door.ogg | opening and closing light door | 14.76 | https://bigsoundbank.com/opening-and-closing-light-door-s0377.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0378_lock-and-big-key.ogg | lock and big key | 17.45 | https://bigsoundbank.com/lock-and-big-key-s0378.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0445_keys-in-a-hand.ogg | keys in a hand | 27.79 | https://bigsoundbank.com/keys-in-a-hand-s0445.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0538_wooden-barn-door.ogg | wooden barn door | 36.65 | https://bigsoundbank.com/wooden-barn-door-s0538.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0615_small-chain-5.ogg | small chain 5 | 32.24 | https://bigsoundbank.com/small-chain-5-s0615.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0619_medium-chain.ogg | medium chain | 43.6 | https://bigsoundbank.com/medium-chain-s0619.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0663_rubbing-hands.ogg | rubbing hands | 26.75 | https://bigsoundbank.com/rubbing-hands-s0663.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\0668_floor-cloth.ogg | floor cloth | 48.2 | https://bigsoundbank.com/floor-cloth-s0668.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\1316_devil-handling-1.ogg | devil handling 1 | 18.37 | https://bigsoundbank.com/devil-handling-1-s1316.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\1317_devil-handling-2.ogg | devil handling 2 | 14.54 | https://bigsoundbank.com/devil-handling-2-s1317.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\1320_open-a-entrance-door-with-a-key.ogg | open a entrance door with a key | 5.52 | https://bigsoundbank.com/open-a-entrance-door-with-a-key-s1320.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\1495_door-window-key-and-opening.ogg | door window key and opening | 3.6 | https://bigsoundbank.com/door-window-key-and-opening-s1495.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\1496_door-window-key-and-opening.ogg | door window key and opening | 6.19 | https://bigsoundbank.com/door-window-key-and-opening-s1496.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\1539_barn-lock-unlocking.ogg | barn lock unlocking | 3.13 | https://bigsoundbank.com/barn-lock-unlocking-s1539.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\1540_barn-lock-locking.ogg | barn lock locking | 2.76 | https://bigsoundbank.com/barn-lock-locking-s1540.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\2414_keys-and-lock-1.ogg | keys and lock 1 | 4.71 | https://bigsoundbank.com/keys-and-lock-1-s2414.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\2415_keys-and-lock-2.ogg | keys and lock 2 | 4.5 | https://bigsoundbank.com/keys-and-lock-2-s2415.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\2416_keys-and-lock-3.ogg | keys and lock 3 | 3.81 | https://bigsoundbank.com/keys-and-lock-3-s2416.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\2417_keys-and-lock-4.ogg | keys and lock 4 | 4.79 | https://bigsoundbank.com/keys-and-lock-4-s2417.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\2425_keys-and-lock-5.ogg | keys and lock 5 | 3.74 | https://bigsoundbank.com/keys-and-lock-5-s2425.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\2426_keys-and-lock-6.ogg | keys and lock 6 | 3.59 | https://bigsoundbank.com/keys-and-lock-6-s2426.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |
| bigsoundbank\2427_keys-and-lock-7.ogg | keys and lock 7 | 3.56 | https://bigsoundbank.com/keys-and-lock-7-s2427.html | Joseph Sardin | CC0-1.0 | courtesy: Sounds by Joseph Sardin, bigsoundbank.com |

### Freesound — Chains, metal clink, bracelet (9)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| freesound\491749_Bracelets_jingling.wav.mp3 | Bracelets jingling.wav | 13.5 | https://freesound.org/people/_lourii/sounds/491749/ | _lourii | CC0-1.0 | — |
| freesound\536780_Clink.ogg.mp3 | Clink.ogg | 0.32 | https://freesound.org/people/egomassive/sounds/536780/ | egomassive | CC0-1.0 | — |
| freesound\561756_chain_links_heavy.wav.mp3 | chain links heavy.wav | 1.45 | https://freesound.org/people/har2h/sounds/561756/ | har2h | CC0-1.0 | — |
| freesound\622098_iron_chain_1.wav.mp3 | iron chain 1.wav | 3.69 | https://freesound.org/people/klankbeeld/sounds/622098/ | klankbeeld | CC-BY-4.0 | "iron chain 1.wav" by klankbeeld (Freesound 622098), CC BY 4.0, https://freesound.org/people/klankbeeld/sounds/622098/ |
| freesound\682153_Metallic_Clink_2.wav.mp3 | Metallic Clink 2.wav | 2.25 | https://freesound.org/people/HenKonen/sounds/682153/ | HenKonen | CC0-1.0 | — |
| freesound\690174_DoorKeys.wav.mp3 | DoorKeys.wav | 17.77 | https://freesound.org/people/callmethefoo/sounds/690174/ | callmethefoo | CC0-1.0 | — |
| freesound\738634_metal_clink.mp3 | metal clink | 1.0 | https://freesound.org/people/waheegle/sounds/738634/ | waheegle | CC0-1.0 | — |
| freesound\96134_Clink1.wav.mp3 | Clink1.wav | 0.31 | https://freesound.org/people/BMacZero/sounds/96134/ | BMacZero | CC0-1.0 | — |
| freesound\96136_Clink3.wav.mp3 | Clink3.wav | 0.29 | https://freesound.org/people/BMacZero/sounds/96136/ | BMacZero | CC0-1.0 | — |

### Freesound — Fabric / sleeve (15)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| freesound\163164_heavy_cloth_rustle.wav.mp3 | heavy cloth rustle.wav | 1.68 | https://freesound.org/people/jacobzeier/sounds/163164/ | jacobzeier | CC0-1.0 | — |
| freesound\235252_Jacket_Rustle_Aggressive_2.wav.mp3 | Jacket Rustle_Aggressive 2.wav | 15.21 | https://freesound.org/people/jaredpass24/sounds/235252/ | jaredpass24 | CC0-1.0 | — |
| freesound\28297_StiffClothRubbing.wav.mp3 | StiffClothRubbing.wav | 6.27 | https://freesound.org/people/HerbertBoland/sounds/28297/ | HerbertBoland | CC-BY-4.0 | "StiffClothRubbing.wav" by HerbertBoland (Freesound 28297), CC BY 4.0, https://freesound.org/people/HerbertBoland/sounds/28297/ |
| freesound\371676_247_-_Acoustic_Memory_-_FabricFoley_08.wav.mp3 | 247 - Acoustic Memory - FabricFoley_08.wav | 4.0 | https://freesound.org/people/AcousticMemory/sounds/371676/ | AcousticMemory | CC-BY-3.0 | "247 - Acoustic Memory - FabricFoley_08.wav" by AcousticMemory (Freesound 371676), CC BY 3.0, https://freesound.org/people/AcousticMemory/sounds/371676/ |
| freesound\389688_Clothes_Shuffling_Near.wav.mp3 | Clothes Shuffling; Near.wav | 9.69 | https://freesound.org/people/Shamewap/sounds/389688/ | Shamewap | CC0-1.0 | — |
| freesound\447584_Cloth_Moves_03_24bit_48KHz_D.A.T.wav.mp3 | Cloth_Moves_03_24bit_48KHz_D.A.T.wav | 6.42 | https://freesound.org/people/davie1960/sounds/447584/ | davie1960 | CC0-1.0 | — |
| freesound\469529_3_Desliz.wav.mp3 | 3_Desliz.wav | 1.64 | https://freesound.org/people/Pocosebas/sounds/469529/ | Pocosebas | CC-BY-3.0 | "3_Desliz.wav" by Pocosebas (Freesound 469529), CC BY 3.0, https://freesound.org/people/Pocosebas/sounds/469529/ |
| freesound\493505_Clothes_Rustling_Movement_13_22.mp3 | Clothes Rustling Movement 13_22 | 0.73 | https://freesound.org/people/Joao_Janz/sounds/493505/ | Joao_Janz | CC0-1.0 | — |
| freesound\494797_Jacket_Cloth_Rustle_9.mp3 | Jacket/Cloth Rustle 9 | 0.33 | https://freesound.org/people/brandondelehoy/sounds/494797/ | brandondelehoy | CC0-1.0 | — |
| freesound\495468_Clothing_rustling1.mp3.mp3 | Clothing rustling1.mp3 | 5.08 | https://freesound.org/people/toiledejouy84/sounds/495468/ | toiledejouy84 | CC-BY-4.0 | "Clothing rustling1.mp3" by toiledejouy84 (Freesound 495468), CC BY 4.0, https://freesound.org/people/toiledejouy84/sounds/495468/ |
| freesound\538930_Coat_Rustle.mp3 | Coat Rustle | 16.28 | https://freesound.org/people/Federico_Casazza/sounds/538930/ | Federico_Casazza | CC0-1.0 | — |
| freesound\555307_Foley_Cloth_Movement_Jacket_96khz.wav.mp3 | Foley_Cloth_Movement_Jacket_96khz.wav | 18.63 | https://freesound.org/people/Nox_Sound/sounds/555307/ | Nox_Sound | CC0-1.0 | — |
| freesound\624478_Cloth_-_heavy_-_shake_-_run_-_trouser.wav.mp3 | Cloth - heavy - shake - run - trouser.wav | 7.61 | https://freesound.org/people/ValentinPetiteau/sounds/624478/ | ValentinPetiteau | CC0-1.0 | — |
| freesound\641387_Clothing_Ruffle_04.wav.mp3 | Clothing Ruffle 04.wav | 4.7 | https://freesound.org/people/WhiteFire43/sounds/641387/ | WhiteFire43 | CC0-1.0 | — |
| freesound\683483_Subtle_Cothing_Movement_SFX.wav.mp3 | Subtle Cothing Movement SFX.wav | 3.93 | https://freesound.org/people/Twigy233/sounds/683483/ | Twigy233 | CC-BY-4.0 | "Subtle Cothing Movement SFX.wav" by Twigy233 (Freesound 683483), CC BY 4.0, https://freesound.org/people/Twigy233/sounds/683483/ |

### Freesound — Hand on wood (28)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| freesound\138332_Hand_Squeezing_on_Wooden_Surface.wav.mp3 | Hand_Squeezing_on_Wooden_Surface.wav | 2.59 | https://freesound.org/people/Tdude9000/sounds/138332/ | Tdude9000 | CC-BY-3.0 | "Hand_Squeezing_on_Wooden_Surface.wav" by Tdude9000 (Freesound 138332), CC BY 3.0, https://freesound.org/people/Tdude9000/sounds/138332/ |
| freesound\219933_FingerTapsWoodLongLoop01.wav.mp3 | FingerTapsWoodLongLoop01.wav | 8.44 | https://freesound.org/people/Otakua/sounds/219933/ | Otakua | CC-BY-3.0 | "FingerTapsWoodLongLoop01.wav" by Otakua (Freesound 219933), CC BY 3.0, https://freesound.org/people/Otakua/sounds/219933/ |
| freesound\233795_Light_Knocking_on_door.wav.mp3 | Light Knocking on door.wav | 15.77 | https://freesound.org/people/Dlam1991/sounds/233795/ | Dlam1991 | CC0-1.0 | — |
| freesound\267426_Impatient_Finger_Tap.mp3 | Impatient Finger Tap | 5.2 | https://freesound.org/people/jsburgh/sounds/267426/ | jsburgh | CC-BY-4.0 | "Impatient Finger Tap" by jsburgh (Freesound 267426), CC BY 4.0, https://freesound.org/people/jsburgh/sounds/267426/ |
| freesound\369710_Wood_Knock.mp3 | Wood Knock | 0.93 | https://freesound.org/people/Mrguff/sounds/369710/ | Mrguff | CC0-1.0 | — |
| freesound\399663_Knock_on_door_1.MP3.mp3 | Knock on door #1.MP3 | 3.12 | https://freesound.org/people/SoundsForHim/sounds/399663/ | SoundsForHim | CC0-1.0 | — |
| freesound\412376_medium_soft_knock_01.wav.mp3 | medium_soft_knock_01.wav | 0.69 | https://freesound.org/people/smokevhstapes/sounds/412376/ | smokevhstapes | CC-BY-4.0 | "medium_soft_knock_01.wav" by smokevhstapes (Freesound 412376), CC BY 4.0, https://freesound.org/people/smokevhstapes/sounds/412376/ |
| freesound\445777_Metal_knocking.WAV.mp3 | Metal knocking.WAV | 1.85 | https://freesound.org/people/DDT197/sounds/445777/ | DDT197 | CC0-1.0 | — |
| freesound\450350_folding_wood_door_with_inlaid_glass_bolt_latch_pus.mp3 | folding wood door with inlaid glass bolt latch push up to lock metal click various on offmic3.flac | 17.35 | https://freesound.org/people/kyles/sounds/450350/ | kyles | CC0-1.0 | — |
| freesound\485167_Knock_On_Door_1_2.mp3 | Knock On Door 1_2 | 2.03 | https://freesound.org/people/Joao_Janz/sounds/485167/ | Joao_Janz | CC0-1.0 | — |
| freesound\485238_Wooden_Desk_Hit_3_11.mp3 | Wooden Desk Hit 3_11 | 0.79 | https://freesound.org/people/Joao_Janz/sounds/485238/ | Joao_Janz | CC0-1.0 | — |
| freesound\485324_Wood_Surface_Scratching_1_2.mp3 | Wood Surface Scratching 1_2 | 7.59 | https://freesound.org/people/Joao_Janz/sounds/485324/ | Joao_Janz | CC0-1.0 | — |
| freesound\522146_Knocking_01_with_knuckle.mp3 | Knocking 01 with knuckle | 9.46 | https://freesound.org/people/CaKon/sounds/522146/ | CaKon | CC-BY-4.0 | "Knocking 01 with knuckle" by CaKon (Freesound 522146), CC BY 4.0, https://freesound.org/people/CaKon/sounds/522146/ |
| freesound\541492_Knocking_Wooden_Door.wav.mp3 | Knocking_Wooden_Door.wav | 1.59 | https://freesound.org/people/Islabonita/sounds/541492/ | Islabonita | CC0-1.0 | — |
| freesound\547332_Woodecho_Tap.mp3 | Woodecho Tap | 1.69 | https://freesound.org/people/DylanSmithSound/sounds/547332/ | DylanSmithSound | CC-BY-4.0 | "Woodecho Tap" by DylanSmithSound (Freesound 547332), CC BY 4.0, https://freesound.org/people/DylanSmithSound/sounds/547332/ |
| freesound\552615_Small_Hard_Lay_Down_Wood_Table_01.wav.mp3 | Small_Hard_Lay_Down_Wood_Table_01.wav | 0.85 | https://freesound.org/people/Joao_Janz/sounds/552615/ | Joao_Janz | CC0-1.0 | — |
| freesound\556709_Knock_on_Door.mp3 | Knock on Door | 3.96 | https://freesound.org/people/NachtmahrTV/sounds/556709/ | NachtmahrTV | CC0-1.0 | — |
| freesound\560349_Hand_and_wood_sliding_.wav.mp3 | Hand and wood (sliding).wav | 1.0 | https://freesound.org/people/Pipelenisf/sounds/560349/ | Pipelenisf | CC0-1.0 | — |
| freesound\567862_Finger_-_slide_-_wood_-_tap_3.wav.mp3 | Finger - slide - wood - tap 3.wav | 9.08 | https://freesound.org/people/ValentinPetiteau/sounds/567862/ | ValentinPetiteau | CC0-1.0 | — |
| freesound\636442_wood_knock.wav.mp3 | wood_knock.wav | 0.15 | https://freesound.org/people/iancsc/sounds/636442/ | iancsc | CC0-1.0 | — |
| freesound\669615_fingers_tapping_on_wood.mp3 | fingers tapping on wood | 11.2 | https://freesound.org/people/laboratoriosonoridades2022/sounds/669615/ | laboratoriosonoridades2022 | CC0-1.0 | — |
| freesound\697789_3_soft_door_knocks_modern_apartment_wooden_16.mp3 | 3 soft door knocks, modern apartment, wooden #16 | 0.65 | https://freesound.org/people/JapanYoshiTheGamer/sounds/697789/ | JapanYoshiTheGamer | CC0-1.0 | — |
| freesound\720070_Light_Knock_1.mp3 | Light Knock 1 | 9.73 | https://freesound.org/people/yehdawgo/sounds/720070/ | yehdawgo | CC0-1.0 | — |
| freesound\812363_Knocking_once_on_wood_single_footstep.mp3 | Knocking once on wood, single footstep | 1.11 | https://freesound.org/people/CuboRodante/sounds/812363/ | CuboRodante | CC0-1.0 | — |
| freesound\863059_Knuckles_Hitting_a_Metal_Box.mp3 | Knuckles Hitting a Metal Box | 11.74 | https://freesound.org/people/bassimat/sounds/863059/ | bassimat | CC0-1.0 | — |
| freesound\863267_Fingers_on_table_SoundAction_289_.mp3 | Fingers on table (SoundAction 289) | 2.99 | https://freesound.org/people/alexarje/sounds/863267/ | alexarje | CC-BY-4.0 | "Fingers on table (SoundAction 289)" by alexarje (Freesound 863267), CC BY 4.0, https://freesound.org/people/alexarje/sounds/863267/ |
| freesound\865052_hollow_hit.mp3 | hollow hit | 0.57 | https://freesound.org/people/ImATaco/sounds/865052/ | ImATaco | CC0-1.0 | — |
| freesound\870663_Door_Closing_Light_Wooden.mp3 | Door Closing, Light, Wooden | 1.26 | https://freesound.org/people/CHallSmith/sounds/870663/ | CHallSmith | CC0-1.0 | — |

### Freesound — Iron ring / door knocker (10)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| freesound\136544_DoorKnockerVarious.wav.mp3 | DoorKnockerVarious.wav | 11.03 | https://freesound.org/people/jmdh/sounds/136544/ | jmdh | CC0-1.0 | — |
| freesound\207554_Haunting_Knock_with_Knocker_Squeak.mp3 | Haunting Knock with Knocker Squeak | 3.52 | https://freesound.org/people/bone666138/sounds/207554/ | bone666138 | CC-BY-4.0 | "Haunting Knock with Knocker Squeak" by bone666138 (Freesound 207554), CC BY 4.0, https://freesound.org/people/bone666138/sounds/207554/ |
| freesound\427111_door_knocker.WAV.mp3 | door knocker.WAV | 10.6 | https://freesound.org/people/buzzatsea/sounds/427111/ | buzzatsea | CC0-1.0 | — |
| freesound\52255_DoorClosing-WithKnocker.wav.mp3 | DoorClosing-WithKnocker.wav | 1.32 | https://freesound.org/people/elankford/sounds/52255/ | elankford | CC-BY-3.0 | "DoorClosing-WithKnocker.wav" by elankford (Freesound 52255), CC BY 3.0, https://freesound.org/people/elankford/sounds/52255/ |
| freesound\52256_DoorOpeningWithKnocker.wav.mp3 | DoorOpeningWithKnocker.wav | 3.24 | https://freesound.org/people/elankford/sounds/52256/ | elankford | CC-BY-3.0 | "DoorOpeningWithKnocker.wav" by elankford (Freesound 52256), CC BY 3.0, https://freesound.org/people/elankford/sounds/52256/ |
| freesound\610987_old_door_knocker.mp3 | old door knocker | 8.01 | https://freesound.org/people/thulitt/sounds/610987/ | thulitt | CC0-1.0 | — |
| freesound\639658_Knock_on_door_metal.mp3 | Knock on door metal | 2.9 | https://freesound.org/people/MarcelWagner/sounds/639658/ | MarcelWagner | CC0-1.0 | — |
| freesound\83240_doorknocker.wav.mp3 | doorknocker.wav | 1.46 | https://freesound.org/people/mlestn1/sounds/83240/ | mlestn1 | CC0-1.0 | — |
| freesound\83910_Bussare_04_vecchia.mp3.mp3 | Bussare_04_vecchia.mp3 | 6.24 | https://freesound.org/people/cormi/sounds/83910/ | cormi | CC0-1.0 | — |
| freesound\83911_Porta_04_vecchia.mp3.mp3 | Porta_04_vecchia.mp3 | 4.78 | https://freesound.org/people/cormi/sounds/83911/ | cormi | CC0-1.0 | — |

### Freesound — Keys / small metal (15)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| freesound\150492_Key_Jangle.mp3 | Key Jangle | 3.71 | https://freesound.org/people/davdud101/sounds/150492/ | davdud101 | CC0-1.0 | — |
| freesound\156188_keys_8-single.wav.mp3 | keys_8-single.wav | 0.35 | https://freesound.org/people/JL_barrett/sounds/156188/ | JL_barrett | CC0-1.0 | — |
| freesound\321476_Keys_Jangle_Close_.mp3 | Keys Jangle (Close) | 7.0 | https://freesound.org/people/dslrguide/sounds/321476/ | dslrguide | CC0-1.0 | — |
| freesound\401629_Cl_es.wav.mp3 | Clées.wav | 5.9 | https://freesound.org/people/studiomandragore/sounds/401629/ | studiomandragore | CC0-1.0 | — |
| freesound\443957_keys-ring-catch.wav.mp3 | keys-ring-catch.wav | 0.97 | https://freesound.org/people/anational/sounds/443957/ | anational | CC0-1.0 | — |
| freesound\51446_keys_rattle6.wav.mp3 | keys_rattle6.wav | 1.7 | https://freesound.org/people/vibe_crc/sounds/51446/ | vibe_crc | CC0-1.0 | — |
| freesound\686177_Light_key_jingling.mp3 | Light key jingling | 2.86 | https://freesound.org/people/redpanda69/sounds/686177/ | redpanda69 | CC0-1.0 | — |
| freesound\705760_OBJKey_KeyMovement02_InMotionAudio_FREESampleSunda.mp3 | OBJKey_KeyMovement02_InMotionAudio_FREESampleSunday.wav | 5.08 | https://freesound.org/people/InMotionAudio/sounds/705760/ | InMotionAudio | CC0-1.0 | — |
| freesound\73090_Keys_03.wav.mp3 | Keys 03.wav | 1.11 | https://freesound.org/people/LG/sounds/73090/ | LG | CC-BY-4.0 | "Keys 03.wav" by LG (Freesound 73090), CC BY 4.0, https://freesound.org/people/LG/sounds/73090/ |
| freesound\73091_Keys_04.wav.mp3 | Keys 04.wav | 0.48 | https://freesound.org/people/LG/sounds/73091/ | LG | CC-BY-4.0 | "Keys 04.wav" by LG (Freesound 73091), CC BY 4.0, https://freesound.org/people/LG/sounds/73091/ |
| freesound\73092_Keys_05.wav.mp3 | Keys 05.wav | 0.98 | https://freesound.org/people/LG/sounds/73092/ | LG | CC-BY-4.0 | "Keys 05.wav" by LG (Freesound 73092), CC BY 4.0, https://freesound.org/people/LG/sounds/73092/ |
| freesound\73093_Keys_06.wav.mp3 | Keys 06.wav | 1.83 | https://freesound.org/people/LG/sounds/73093/ | LG | CC-BY-4.0 | "Keys 06.wav" by LG (Freesound 73093), CC BY 4.0, https://freesound.org/people/LG/sounds/73093/ |
| freesound\740408_grabbing_keys_off_of_a_wood_counter_1.mp3 | grabbing keys off of a wood counter 1 | 2.21 | https://freesound.org/people/FOSSarts/sounds/740408/ | FOSSarts | CC0-1.0 | — |
| freesound\757950_Keys_falling_on_wooden_table_3.mp3 | Keys falling on wooden table 3 | 0.81 | https://freesound.org/people/Bardenschule/sounds/757950/ | Bardenschule | CC0-1.0 | — |
| freesound\788310_Key_Pickup.mp3 | Key Pickup | 1.17 | https://freesound.org/people/RealSquink/sounds/788310/ | RealSquink | CC0-1.0 | — |

### Freesound — Latches, door hardware (4)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| freesound\126041_Gate_Latch.mp3 | Gate Latch | 1.55 | https://freesound.org/people/mhtaylor67/sounds/126041/ | mhtaylor67 | CC0-1.0 | — |
| freesound\710871_Metal_Gate_Latch_02.mp3 | Metal Gate Latch 02 | 13.31 | https://freesound.org/people/NapierFreesound/sounds/710871/ | NapierFreesound | CC0-1.0 | — |
| freesound\839782_Gate_latch.mp3 | Gate_latch | 0.36 | https://freesound.org/people/BenParamoreAudio/sounds/839782/ | BenParamoreAudio | CC0-1.0 | — |
| freesound\853482_EarlyFiles-TSR-Iron_Latch_1.mp3 | EarlyFiles-TSR-Iron Latch 1 | 2.14 | https://freesound.org/people/CAT-FOX_ALEX/sounds/853482/ | CAT-FOX_ALEX | CC0-1.0 | — |

### Freesound — Metal ring on metal (8)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| freesound\144093_Metal_Key_Falling_on_Wood.mp3 | Metal Key Falling on Wood | 1.51 | https://freesound.org/people/bendodge/sounds/144093/ | bendodge | CC-BY-3.0 | "Metal Key Falling on Wood" by bendodge (Freesound 144093), CC BY 3.0, https://freesound.org/people/bendodge/sounds/144093/ |
| freesound\182713_Keychain_Movement.flac.mp3 | Keychain Movement.flac | 19.72 | https://freesound.org/people/qubodup/sounds/182713/ | qubodup | CC0-1.0 | — |
| freesound\399368_Dropping_ring_on_table.mp3 | Dropping ring on table | 5.25 | https://freesound.org/people/afamiliarletter/sounds/399368/ | afamiliarletter | CC0-1.0 | — |
| freesound\754319_metal_on_metal.mp3 | metal_on_metal | 9.66 | https://freesound.org/people/KenneysGarage/sounds/754319/ | KenneysGarage | CC0-1.0 | — |
| freesound\783000_Metal_Ring_Falling_to_the_Floor.mp3 | Metal Ring Falling to the Floor | 2.57 | https://freesound.org/people/Iceofdoom/sounds/783000/ | Iceofdoom | CC-BY-4.0 | "Metal Ring Falling to the Floor" by Iceofdoom (Freesound 783000), CC BY 4.0, https://freesound.org/people/Iceofdoom/sounds/783000/ |
| freesound\843095_Drop_Placed_Ring.mp3 | Drop & Placed Ring | 18.13 | https://freesound.org/people/Detective_Lemons/sounds/843095/ | Detective_Lemons | CC0-1.0 | — |
| freesound\84444_anneau-metal-3.wav.mp3 | anneau-metal-3.wav | 1.51 | https://freesound.org/people/jeff25/sounds/84444/ | jeff25 | CC0-1.0 | — |
| freesound\95275_metal_rings_04.wav.mp3 | metal_rings_04.wav | 3.67 | https://freesound.org/people/Department64/sounds/95275/ | Department64 | CC0-1.0 | — |

### Freesound — Padlock (16)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| freesound\111318_padlock.wav.mp3 | padlock.wav | 0.13 | https://freesound.org/people/NoiseCollector/sounds/111318/ | NoiseCollector | CC-BY-3.0 | "padlock.wav" by NoiseCollector (Freesound 111318), CC BY 3.0, https://freesound.org/people/NoiseCollector/sounds/111318/ |
| freesound\164670_Lock_rattle_5.wav.mp3 | Lock rattle 5.wav | 3.16 | https://freesound.org/people/deleted_user_2104797/sounds/164670/ | deleted_user_2104797 | CC0-1.0 | — |
| freesound\190035_Padlock_locking_and_unlocking.mp3 | Padlock locking and unlocking | 11.05 | https://freesound.org/people/eizzof/sounds/190035/ | eizzof | CC0-1.0 | — |
| freesound\391704_jp_tinypadlock01.flac.mp3 | jp_tinypadlock01.flac | 0.48 | https://freesound.org/people/JPolito/sounds/391704/ | JPolito | CC0-1.0 | — |
| freesound\445596_Padlock_Clang.wav.mp3 | Padlock Clang.wav | 6.87 | https://freesound.org/people/Student023/sounds/445596/ | Student023 | CC-BY-3.0 | "Padlock Clang.wav" by Student023 (Freesound 445596), CC BY 3.0, https://freesound.org/people/Student023/sounds/445596/ |
| freesound\445779_Padlock_.WAV.mp3 | Padlock .WAV | 16.93 | https://freesound.org/people/DDT197/sounds/445779/ | DDT197 | CC0-1.0 | — |
| freesound\445900_OWI_Padlock.WAV.mp3 | OWI_Padlock.WAV | 12.78 | https://freesound.org/people/SkullkSound/sounds/445900/ | SkullkSound | CC-BY-4.0 | "OWI_Padlock.WAV" by SkullkSound (Freesound 445900), CC BY 4.0, https://freesound.org/people/SkullkSound/sounds/445900/ |
| freesound\483605_Mechanical_Key.mp3 | Mechanical Key | 0.23 | https://freesound.org/people/Raclure/sounds/483605/ | Raclure | CC0-1.0 | — |
| freesound\531519_padlock.wav.mp3 | padlock.wav | 7.0 | https://freesound.org/people/Melilaura/sounds/531519/ | Melilaura | CC0-1.0 | — |
| freesound\536414_Small_Padlock_Opening.mp3 | Small Padlock Opening | 0.25 | https://freesound.org/people/Rudmer_Rotteveel/sounds/536414/ | Rudmer_Rotteveel | CC0-1.0 | — |
| freesound\553258_opening_Padlock.mp3 | opening Padlock | 5.04 | https://freesound.org/people/NachtmahrTV/sounds/553258/ | NachtmahrTV | CC0-1.0 | — |
| freesound\583916_Safe_Misc_-_7.wav.mp3 | Safe Misc - 7.wav | 0.37 | https://freesound.org/people/SpaceJoe/sounds/583916/ | SpaceJoe | CC-BY-4.0 | "Safe Misc - 7.wav" by SpaceJoe (Freesound 583916), CC BY 4.0, https://freesound.org/people/SpaceJoe/sounds/583916/ |
| freesound\632488_Opening_a_steel_padlock_shackle_with_key_turning_n.mp3 | Opening a steel padlock shackle with key turning noise | 0.32 | https://freesound.org/people/ani_music/sounds/632488/ | ani_music | CC0-1.0 | — |
| freesound\718103_Padlock_SoundAction_005_.mp3 | Padlock (SoundAction 005) | 7.02 | https://freesound.org/people/alexarje/sounds/718103/ | alexarje | CC-BY-4.0 | "Padlock (SoundAction 005)" by alexarje (Freesound 718103), CC BY 4.0, https://freesound.org/people/alexarje/sounds/718103/ |
| freesound\85130_unlocking_keyed_padlock.wav.mp3 | unlocking keyed padlock.wav | 5.17 | https://freesound.org/people/Wrylytucker/sounds/85130/ | Wrylytucker | CC-BY-3.0 | "unlocking keyed padlock.wav" by Wrylytucker (Freesound 85130), CC BY 3.0, https://freesound.org/people/Wrylytucker/sounds/85130/ |
| freesound\874473_Padlock_and_Key_Handling.mp3 | Padlock and Key Handling | 11.23 | https://freesound.org/people/loganzsound/sounds/874473/ | loganzsound | CC0-1.0 | — |

### Freesound — Room tone (4)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| freesound\108400_quiet_room.wav.mp3 | quiet room.wav | 13.27 | https://freesound.org/people/filmfan87/sounds/108400/ | filmfan87 | CC0-1.0 | — |
| freesound\454166_room_tone_medium_quiet_Pablo_s_condo.flac.mp3 | room tone medium quiet Pablo's condo.flac | 18.18 | https://freesound.org/people/kyles/sounds/454166/ | kyles | CC0-1.0 | — |
| freesound\716439_Room_Tone_for_Bedroom.mp3 | Room Tone for Bedroom | 16.13 | https://freesound.org/people/wildestshockt/sounds/716439/ | wildestshockt | CC-BY-4.0 | "Room Tone for Bedroom" by wildestshockt (Freesound 716439), CC BY 4.0, https://freesound.org/people/wildestshockt/sounds/716439/ |
| freesound\751709_room-tone_apartment_619_PM_240215_0662.mp3 | room-tone apartment 619 PM 240215_0662 | 15.0 | https://freesound.org/people/klankbeeld/sounds/751709/ | klankbeeld | CC-BY-4.0 | "room-tone apartment 619 PM 240215_0662" by klankbeeld (Freesound 751709), CC BY 4.0, https://freesound.org/people/klankbeeld/sounds/751709/ |

### Freesound — Wristwatch (3)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| freesound\388458_Putting_hand_watch_on_table.wav.mp3 | Putting hand watch on table.wav | 1.85 | https://freesound.org/people/vovere/sounds/388458/ | vovere | CC0-1.0 | — |
| freesound\439639_Watch_Clasp_Snap_Closed.mp3 | Watch Clasp Snap Closed | 1.96 | https://freesound.org/people/jzielke011/sounds/439639/ | jzielke011 | CC0-1.0 | — |
| freesound\810010_OBJCont-Blue_Snowball_Microphone_MCU_Wristwatch_Bo.mp3 | OBJCont-Blue Snowball Microphone, MCU_Wristwatch Box, Shake_Nicholas Judy_TDC | 1.98 | https://freesound.org/people/designerschoice/sounds/810010/ | designerschoice | CC-BY-4.0 | "OBJCont-Blue Snowball Microphone, MCU_Wristwatch Box, Shake_Nicholas Judy_TDC" by designerschoice (Freesound 810010), CC BY 4.0, https://freesound.org/people/designerschoice/sounds/810010/ |

### OpenGameArt — 100 CC0 metal and wood SFX (rubberduck) (51)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| oga-100-cc0-metal-wood\files\keys_01.ogg | keys_01 | 0.41 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\keys_02.ogg | keys_02 | 0.46 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\keys_03.ogg | keys_03 | 0.48 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\keys_04.ogg | keys_04 | 0.38 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\keys_05.ogg | keys_05 | 0.57 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\keys_06.ogg | keys_06 | 0.64 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\keys_07.ogg | keys_07 | 0.57 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\lock_open_01.ogg | lock_open_01 | 0.74 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\metal_close_01.ogg | metal_close_01 | 0.87 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\metal_hit_01.ogg | metal_hit_01 | 0.27 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\metal_hit_02.ogg | metal_hit_02 | 0.43 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\metal_hit_03.ogg | metal_hit_03 | 0.4 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\metal_hit_04.ogg | metal_hit_04 | 0.37 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\metal_hit_05.ogg | metal_hit_05 | 0.33 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_01.ogg | misc_01 | 0.96 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_02.ogg | misc_02 | 0.31 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_03.ogg | misc_03 | 0.62 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_04.ogg | misc_04 | 0.59 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_05.ogg | misc_05 | 0.68 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_06.ogg | misc_06 | 0.91 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_07.ogg | misc_07 | 0.95 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_08.ogg | misc_08 | 0.38 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_09.ogg | misc_09 | 0.74 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_10.ogg | misc_10 | 0.53 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_11.ogg | misc_11 | 0.56 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_12.ogg | misc_12 | 0.32 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_13.ogg | misc_13 | 0.37 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_14.ogg | misc_14 | 0.51 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_15.ogg | misc_15 | 0.49 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_16.ogg | misc_16 | 0.42 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\misc_17.ogg | misc_17 | 0.29 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_close_01.ogg | wood_close_01 | 0.4 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_close_02.ogg | wood_close_02 | 0.44 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_hit_01.ogg | wood_hit_01 | 0.34 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_hit_02.ogg | wood_hit_02 | 0.39 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_hit_03.ogg | wood_hit_03 | 0.41 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_hit_04.ogg | wood_hit_04 | 0.3 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_hit_05.ogg | wood_hit_05 | 0.31 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_hit_06.ogg | wood_hit_06 | 0.28 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_hit_07.ogg | wood_hit_07 | 0.29 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_hit_08.ogg | wood_hit_08 | 0.37 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_hit_09.ogg | wood_hit_09 | 0.26 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_misc_01.ogg | wood_misc_01 | 0.42 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_misc_02.ogg | wood_misc_02 | 0.34 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_misc_03.ogg | wood_misc_03 | 0.45 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_misc_04.ogg | wood_misc_04 | 0.47 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_misc_05.ogg | wood_misc_05 | 0.3 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_misc_06.ogg | wood_misc_06 | 0.43 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_misc_07.ogg | wood_misc_07 | 0.44 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_misc_08.ogg | wood_misc_08 | 0.29 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |
| oga-100-cc0-metal-wood\files\wood_misc_09.ogg | wood_misc_09 | 0.74 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx | rubberduck | CC0-1.0 | — |

### OpenGameArt — 202 more sound effects, Keys/Locks/Door + Cloth (OwlishMedia) (58)

| local file (under foley-h4\) | what it is (from title) | s | source | author | licence | credit line |
|---|---|---|---|---|---|---|
| oga-202-more-owlish\files\Cloth_01.wav | Cloth_01 (pack folder: Cloth) | 1.73 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Cloth_02.wav | Cloth_02 (pack folder: Cloth) | 1.5 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Cloth_03.wav | Cloth_03 (pack folder: Cloth) | 1.75 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Cloth_04.wav | Cloth_04 (pack folder: Cloth) | 0.57 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Cloth_05.wav | Cloth_05 (pack folder: Cloth) | 0.4 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Cloth_06.wav | Cloth_06 (pack folder: Cloth) | 1.32 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Cloth_07.wav | Cloth_07 (pack folder: Cloth) | 1.01 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_01.wav | Key_Lock_Door_01 (pack folder: Keys, Locks, Door) | 2.64 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_02.wav | Key_Lock_Door_02 (pack folder: Keys, Locks, Door) | 0.95 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_03.wav | Key_Lock_Door_03 (pack folder: Keys, Locks, Door) | 0.98 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_04.wav | Key_Lock_Door_04 (pack folder: Keys, Locks, Door) | 0.6 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_05.wav | Key_Lock_Door_05 (pack folder: Keys, Locks, Door) | 0.98 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_06.wav | Key_Lock_Door_06 (pack folder: Keys, Locks, Door) | 0.66 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_07.wav | Key_Lock_Door_07 (pack folder: Keys, Locks, Door) | 1.19 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_08.wav | Key_Lock_Door_08 (pack folder: Keys, Locks, Door) | 1.21 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_09.wav | Key_Lock_Door_09 (pack folder: Keys, Locks, Door) | 1.18 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_10.wav | Key_Lock_Door_10 (pack folder: Keys, Locks, Door) | 1.15 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_11.wav | Key_Lock_Door_11 (pack folder: Keys, Locks, Door) | 0.61 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_12.wav | Key_Lock_Door_12 (pack folder: Keys, Locks, Door) | 1.19 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_13.wav | Key_Lock_Door_13 (pack folder: Keys, Locks, Door) | 0.78 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_14.wav | Key_Lock_Door_14 (pack folder: Keys, Locks, Door) | 1.87 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_15.wav | Key_Lock_Door_15 (pack folder: Keys, Locks, Door) | 1.72 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_16.wav | Key_Lock_Door_16 (pack folder: Keys, Locks, Door) | 0.75 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_17.wav | Key_Lock_Door_17 (pack folder: Keys, Locks, Door) | 1.27 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_18.wav | Key_Lock_Door_18 (pack folder: Keys, Locks, Door) | 0.83 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_19.wav | Key_Lock_Door_19 (pack folder: Keys, Locks, Door) | 2.24 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_20.wav | Key_Lock_Door_20 (pack folder: Keys, Locks, Door) | 1.48 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_21.wav | Key_Lock_Door_21 (pack folder: Keys, Locks, Door) | 1.15 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_22.wav | Key_Lock_Door_22 (pack folder: Keys, Locks, Door) | 0.91 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_23.wav | Key_Lock_Door_23 (pack folder: Keys, Locks, Door) | 0.75 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_24.wav | Key_Lock_Door_24 (pack folder: Keys, Locks, Door) | 3.47 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_25.wav | Key_Lock_Door_25 (pack folder: Keys, Locks, Door) | 0.76 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_26.wav | Key_Lock_Door_26 (pack folder: Keys, Locks, Door) | 1.03 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_27.wav | Key_Lock_Door_27 (pack folder: Keys, Locks, Door) | 2.27 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_28.wav | Key_Lock_Door_28 (pack folder: Keys, Locks, Door) | 2.23 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_29.wav | Key_Lock_Door_29 (pack folder: Keys, Locks, Door) | 1.39 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_30.wav | Key_Lock_Door_30 (pack folder: Keys, Locks, Door) | 0.25 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_31.wav | Key_Lock_Door_31 (pack folder: Keys, Locks, Door) | 0.9 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_32.wav | Key_Lock_Door_32 (pack folder: Keys, Locks, Door) | 0.51 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_33.wav | Key_Lock_Door_33 (pack folder: Keys, Locks, Door) | 1.08 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_34.wav | Key_Lock_Door_34 (pack folder: Keys, Locks, Door) | 0.7 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_35.wav | Key_Lock_Door_35 (pack folder: Keys, Locks, Door) | 0.62 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_36.wav | Key_Lock_Door_36 (pack folder: Keys, Locks, Door) | 0.78 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_37.wav | Key_Lock_Door_37 (pack folder: Keys, Locks, Door) | 1.4 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_38.wav | Key_Lock_Door_38 (pack folder: Keys, Locks, Door) | 1.03 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_39.wav | Key_Lock_Door_39 (pack folder: Keys, Locks, Door) | 0.44 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_40.wav | Key_Lock_Door_40 (pack folder: Keys, Locks, Door) | 1.03 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_41.wav | Key_Lock_Door_41 (pack folder: Keys, Locks, Door) | 1.4 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_42.wav | Key_Lock_Door_42 (pack folder: Keys, Locks, Door) | 1.61 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_43.wav | Key_Lock_Door_43 (pack folder: Keys, Locks, Door) | 0.82 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_44.wav | Key_Lock_Door_44 (pack folder: Keys, Locks, Door) | 5.48 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_45.wav | Key_Lock_Door_45 (pack folder: Keys, Locks, Door) | 1.99 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_46.wav | Key_Lock_Door_46 (pack folder: Keys, Locks, Door) | 9.22 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_47.wav | Key_Lock_Door_47 (pack folder: Keys, Locks, Door) | 1.69 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_48.wav | Key_Lock_Door_48 (pack folder: Keys, Locks, Door) | 1.55 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_49.wav | Key_Lock_Door_49 (pack folder: Keys, Locks, Door) | 2.66 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_50.wav | Key_Lock_Door_50 (pack folder: Keys, Locks, Door) | 0.7 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |
| oga-202-more-owlish\files\Key_Lock_Door_51.wav | Key_Lock_Door_51 (pack folder: Keys, Locks, Door) | 0.49 | https://opengameart.org/content/202-more-sound-effects | OwlishMedia | CC0-1.0 | — |