"""Generate one instrumental bed with ACE-Step 1.5 on a small GPU (4 GB): DiT only (no LM planner),
INT8 weights, everything offloaded to the CPU between uses. Run with ACE-Step's own venv, from its repo
folder, through the machine lock:

  heavy.ps1 run "priyam: ACE-Step bed" gpu <acestep venv python> gen_bed.py --out <dir> --seconds 30 ...

Prints one JSON line: output path, seconds, wall time, peak GPU memory.
"""
import argparse
import json
import os
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="ACE-Step-1.5 checkout (checkpoints download into <repo>/checkpoints)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--caption", required=True)
    ap.add_argument("--bpm", type=int, default=None)
    ap.add_argument("--key", default="")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--reference", default=None, help="optional reference audio (style); off by default")
    ap.add_argument("--compile", action="store_true")
    a = ap.parse_args()

    sys.path.insert(0, a.repo)
    import torch
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    import acestep.model_downloader as md

    # The 4 GB tier runs without the LM planner; don't let the "main model present" check fetch its 3.8 GB.
    if "acestep-5Hz-lm-1.7B" in md.MAIN_MODEL_COMPONENTS:
        md.MAIN_MODEL_COMPONENTS.remove("acestep-5Hz-lm-1.7B")

    t0 = time.time()
    dit = AceStepHandler()
    msg, ok = dit.initialize_service(
        project_root=a.repo, config_path="acestep-v15-turbo", device="cuda",
        compile_model=a.compile, offload_to_cpu=True, offload_dit_to_cpu=True,
        quantization="int8_weight_only",
    )
    if not ok:
        print(json.dumps({"ok": False, "stage": "init", "error": msg}))
        return 1
    t_init = time.time() - t0
    params = GenerationParams(
        caption=a.caption, lyrics="[Instrumental]", instrumental=True, duration=a.seconds,
        bpm=a.bpm, keyscale=a.key, inference_steps=a.steps, seed=a.seed, thinking=False,
        use_cot_metas=False, use_cot_caption=False, use_cot_language=False,
        reference_audio=a.reference,
    )
    os.makedirs(a.out, exist_ok=True)
    t1 = time.time()
    res = generate_music(dit, LLMHandler(), params, GenerationConfig(batch_size=1, audio_format="wav"), save_dir=a.out)
    t_gen = time.time() - t1
    peak = torch.cuda.max_memory_allocated() / 2**30 if torch.cuda.is_available() else None
    if not res.success:
        print(json.dumps({"ok": False, "stage": "generate", "error": str(res.error)}))
        return 1
    print(json.dumps({"ok": True, "path": res.audios[0]["path"], "initSeconds": round(t_init, 1),
                      "generateSeconds": round(t_gen, 1), "peakGpuGiB": round(peak, 2) if peak else None}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
