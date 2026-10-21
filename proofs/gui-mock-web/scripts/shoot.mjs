// Builds the app, serves it, shoots the three demo moments (checking what is visible against expected.json),
// records the demo timeline in real time and converts it to mp4.  node scripts/shoot.mjs
import { spawn, execFileSync } from "node:child_process";
import { readFileSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const mockDir = resolve(root, "../gui-mock");
const OUT = "C:/Users/Sam/.rostrum/waves/results/stage1/p-gui-mock";
const SCRATCH = "C:/Users/Sam/.rostrum/waves/scratch/sam-S3-web";
// Playwright 1.64 wants chromium-1248; the machine already has 1243, so point at it (nothing is downloaded).
const CHROME = "C:/Users/Sam/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe";
const PORT = 4173, URL = `http://127.0.0.1:${PORT}/`;
const demo = JSON.parse(readFileSync(join(mockDir, "demo.json"), "utf8"));
const expected = JSON.parse(readFileSync(join(mockDir, "expected.json"), "utf8"));
const [W, H] = demo.size;
const { chromium } = await import("playwright");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
mkdirSync(SCRATCH, { recursive: true });

const vite = join(root, "node_modules/vite/bin/vite.js");
execFileSync(process.execPath, [vite, "build"], { cwd: root, stdio: "inherit" });
const server = spawn(process.execPath, [vite, "preview", "--host", "127.0.0.1", "--port", String(PORT), "--strictPort"], { cwd: root, stdio: "ignore" });
console.log(`preview server PID ${server.pid}`);

const apply = (page, step) =>
  page.evaluate((s) => (s.op === "select" ? window.mock.select(s.item) : window.mock.setValue(s.item, s.param, s.value)), step);
const failures = [];

async function waitForServer() {
  for (let i = 0; i < 50; i++) {
    try { if ((await fetch(URL)).ok) return; } catch { /* not up yet */ }
    await sleep(200);
  }
  throw new Error("preview server did not start");
}

try {
  await waitForServer();
  const browser = await chromium.launch({ executablePath: CHROME });

  // 1. Screenshot moments, each from a fresh page; check visible() and the DOM against expected.json.
  for (const [name, steps] of Object.entries(demo.moments)) {
    const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    await page.goto(URL);
    await page.evaluate(() => document.fonts.ready);
    for (const s of steps) await apply(page, s);
    await sleep(400);
    const visible = await page.evaluate(() => window.mock.visible());
    // DOM check: rows whose collapse wrapper chain is open (More is closed, so deep rows are not on screen).
    const dom = await page.evaluate(() =>
      [...document.querySelectorAll("[data-ctl]")].filter((el) => !el.closest("[inert]")).map((el) => el.dataset.ctl));
    const want = expected[name];
    const wantAll = [...want.shown, ...want.more];
    if (JSON.stringify(visible) !== JSON.stringify(wantAll)) failures.push(`${name}: visible() = ${visible} expected ${wantAll}`);
    if (JSON.stringify(dom) !== JSON.stringify(want.shown)) failures.push(`${name}: on-screen rows = ${dom} expected ${want.shown}`);
    await page.screenshot({ path: join(OUT, `web-${name}.png`) });
    console.log(`${name}: ${failures.length ? "CHECK FAILED" : "ok"}  (${visible.join(", ")})`);
    await ctx.close();
  }
  if (failures.length) throw new Error("expected.json mismatch:\n" + failures.join("\n"));

  // 2. Record the timeline in real time. Playwright's own recordVideo needs ffmpeg-1013 (a download; the machine
  //    has the older 1011, which it rejects), so use the same Chromium screencast it is built on: frames with
  //    timestamps, joined with the PATH ffmpeg at the real timing.
  const fdir = join(SCRATCH, "frames");
  rmSync(fdir, { recursive: true, force: true });
  mkdirSync(fdir, { recursive: true });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(URL);
  await page.evaluate(() => document.fonts.ready);
  const cdp = await ctx.newCDPSession(page);
  const frames = [];  // { ts (s), file }
  cdp.on("Page.screencastFrame", (f) => {
    const file = join(fdir, `f${String(frames.length).padStart(5, "0")}.jpg`);
    writeFileSync(file, Buffer.from(f.data, "base64"));
    frames.push({ ts: f.metadata.timestamp, file });
    cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 95, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
  await sleep(500);
  const start = Date.now();
  for (const step of demo.recording) {
    const wait = step.at * 1000 - (Date.now() - start);
    if (wait > 0) await sleep(wait);
    if (step.op === "end") break;
    await apply(page, step);
  }
  const t0 = start / 1000, t1 = t0 + demo.recording.at(-1).at;
  await sleep(200);
  await cdp.send("Page.stopScreencast");
  await ctx.close();
  // concat list: each frame is shown from its timestamp to the next one; the video runs t0..t1.
  const first = frames.findLastIndex((f) => f.ts <= t0);
  if (first < 0) throw new Error("no screencast frame before the recording start");
  const fwd = (p) => p.replaceAll("\\", "/");
  const n = Math.round((t1 - t0) * 30);  // one entry per 30 fps slot: the latest frame at or before that moment
  const list = [];
  for (let k = 0, j = first; k < n; k++) {
    while (j + 1 < frames.length && frames[j + 1].ts <= t0 + k / 30) j++;
    list.push(`file '${fwd(frames[j].file)}'`, "duration 0.033333");
  }
  list.push(list.at(-2));  // concat needs the last file repeated
  writeFileSync(join(fdir, "list.txt"), list.join("\n") + "\n");
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", join(fdir, "list.txt"),
    "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "18", join(OUT, "web-reveal.mp4")], { stdio: "inherit" });
  console.log(`recorded web-reveal.mp4 (${n} frames at 30 fps from ${frames.length} screencast frames)`);
  await browser.close();
} catch (e) {
  console.error("FAILED:", e.message);
  process.exitCode = 1;
} finally {
  process.kill(server.pid);
  console.log(`preview server PID ${server.pid} ended`);
}
