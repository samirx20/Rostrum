# HANDOFF.md

*The single handoff file. Overwrite it in place at the end of a session; never create variants.*

## Where things stand (2026-10-21)

- **This repo was created today.** It holds only docs: the rules (`AGENTS.md`), the plan (`docs/PLAN.md`), what to take from the experiment (`docs/CARRY_OVER.md`), where to look things up (`docs/REFERENCES.md`) and the Stage 1 proof briefs (`docs/PROOFS.md`). No code yet.
- **GitHub:** `origin` = https://github.com/samirx20/Rostrum.git (linked; pushing needs Sam's OK).
- **The experiment is archived:** `C:\Users\Sam\Documents\CODE\MOTION-STUDIO`, tag `experiment-final` (`da3f2118`), pushed to https://github.com/samirx20/choreo. Its team worktrees and branches were removed. Its build folder keeps only the five engine programs, because the `rostrum` MCP tools still run from them. Free disk afterwards: ~135 GB.
- **Decided with Sam (2026-10-21):** four separate apps plus a shared layer. Rostrum3D in C++ on USD + Hydra + Cycles, scripted in Python. MIT. Windows + Mac. Proofs before building. Two tracks after the proofs. 3D builds product tools first, then painterly ones. Agents paint for real. One installer. Full list in `docs/PLAN.md` › Decided.

## Next

1. **Before launching anyone:** update the manager tooling in `C:\Users\Sam\.rostrum\waves\` (RULES.md, lead-brief.md, heartbeat) for this repo, and create the team worktrees `C:\Users\Sam\.t3\worktrees\Rostrum\team-{hem,priyam,sam}` on branches `team/<name>`.
2. **Sam:** edit the reference set (`docs/PLAN.md` › Reference set) and put the media in `C:\Users\Sam\.rostrum\references\`.
3. **Stage 1 proofs** (`docs/PROOFS.md`): Hem — P-3D-1 → P-3D-2 → P-3D-3; Priyam — P-SND, then P-PAINT; Sam — P-REPO, P-GUI, P-2D.
4. After each proof: the manager compares against the reference, Sam decides, and the verdict goes into `docs/PLAN.md` › Decided.

## Open decisions

See `NEEDS_DECISIONS.md`.
