# HANDOFF.md

*The single handoff file: what has happened so far and what the next session does. Read it at the start of a session. At the end of a session, overwrite it in place (keep the structure; move finished items into "Progress"). Never create `HANDOFF_*.md` variants.*

**Last updated:** 2026-10-21, by the manager session that created this repo.

---

## 1. Progress so far

### Overall

| Stage | What | Status |
|---|---|---|
| 0 | Decide the plan, archive the experiment, set up this repo | **Done** (2026-10-21) |
| 1 | Proofs — test every foundation choice against a reference | **Not started** |
| 2 | Two tracks — A: 2D → Sound → Editor; B: 3D | Not started |

### Stage 1 proofs (briefs in [docs/PROOFS.md](docs/PROOFS.md))

| Proof | Team | Status | Verdict | Result folder |
|---|---|---|---|---|
| P-REPO · repo skeleton + shared-layer contracts | Sam | Not started | — | — |
| P-GUI · web UI vs Qt | Sam | Not started | — | — |
| P-2D · Blitz vs Chromium (finish) | Sam | Not started | — | — |
| P-3D-1 · product still (USD + Hydra + Cycles) | Hem | Not started | — | — |
| P-3D-2 · painterly still | Hem | Not started | — | — |
| P-3D-3 · stylized Hydra plug-in | Hem | Not started | — | — |
| P-SND · sound against the reference | Priyam | Not started | — | — |
| P-PAINT · agent painting (2D, then 3D) | Priyam | Not started | — | — |

### Done, with dates

**2026-10-21**
- **Decided with Sam:** four separate apps plus a shared layer; Rostrum3D in C++ on USD + Hydra + Cycles, scripted in Python; MIT; Windows + Mac; proofs before building; two tracks; 3D builds product tools first, then painterly ones; agents paint for real; one installer; team split. Everything is in [docs/PLAN.md](docs/PLAN.md) › Decided.
- **Experiment archived:** `C:\Users\Sam\Documents\CODE\MOTION-STUDIO`, tag `experiment-final` (`da3f2118`), pushed to https://github.com/samirx20/choreo. Team worktrees and branches removed. Render cache cleared. Build folder trimmed to the five engine programs, because the `rostrum` MCP tools still run from them. Free disk ~135 GB.
- **This repo created** at `C:\Users\Sam\Documents\CODE\Rostrum`, linked to https://github.com/samirx20/Rostrum.git, first commit `ebfc508` pushed. Docs only: AGENTS.md, docs/PLAN.md, docs/CARRY_OVER.md, docs/REFERENCES.md, docs/PROOFS.md, NEEDS_DECISIONS.md.

---

## 2. Next session

Goal: **get Stage 1 running.**

### Before launching any team (manager)
1. **Update the team tooling** in `C:\Users\Sam\.rostrum\waves\`: `RULES.md`, `lead-brief.md`, heartbeat. Point them at this repo, its rules (AGENTS.md) and the new worktree paths; drop the archive-only steps (old MCP sync, old build checks).
2. **Create the team worktrees:** `C:\Users\Sam\.t3\worktrees\Rostrum\team-hem`, `team-priyam`, `team-sam`, on branches `team/hem`, `team/priyam`, `team/sam` from `main`.
3. **Check quota** (`node C:\Users\Sam\.rostrum\waves\quota.mjs`) and place teams by it (team Sam keeps the 25 % manager reserve).

### Launch (all three teams can start; at most two are heavy)
| Team | First brief | Then |
|---|---|---|
| **Sam** (light) | P-REPO: create the folder layout, write the shared-layer and MCP contracts | P-GUI, then P-2D |
| **Hem** (heavy) | P-3D-1: product still through USD + Hydra + Cycles on this laptop | P-3D-2, then P-3D-3 |
| **Priyam** (heavy) | P-SND: one 60 s cue + one 20 s effects pass against the reference | P-PAINT (2D first; 3D once P-3D-1 renders) |

### Waiting on Sam
- **Reference set:** edit the draft in docs/PLAN.md › Reference set, and put the clips in `C:\Users\Sam\.rostrum\references\<app>\`. Proofs can start without it, but verdicts need it.
- See [NEEDS_DECISIONS.md](NEEDS_DECISIONS.md) for everything open.

### Done when
Every proof in the table above has a verdict that Sam has seen, recorded in docs/PLAN.md › Decided. Then Stage 2 starts.

---

## 3. Watch out for

- **The archive is read-only.** Read it at the tag (`git -C C:\Users\Sam\Documents\CODE\MOTION-STUDIO show experiment-final:<path>`); never commit there. Don't delete its five engine programs: the `rostrum` MCP tools in Claude sessions run from them.
- **The laptop is the limit:** 16 GB RAM, 4 GB GPU. At most two heavy teams; one heavy job per team. Building OpenUSD from source takes hours, so use prebuilt libraries (vcpkg).
- **Pushing to GitHub needs Sam's OK** each time.
- **Sam reads plain language:** full absolute paths, no jargon, results he can look at or listen to.
