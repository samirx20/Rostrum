"""The audio-text model: load once, embed takes and texts, release.

Default weights: laion/larger_clap_general (Apache-2.0, see ../MODELS.md), through Hugging Face
transformers' ClapModel (Apache-2.0). Embeddings are L2-normalised, so a dot product is a cosine.
"""
import gc

import numpy as np
import torch
from transformers import ClapModel, ClapProcessor

from .audio import Take, load, windows

DEFAULT_MODEL = "laion/larger_clap_general"
WINDOW_S = 10.0  # CLAP hears 10 s per input
PAD = {"silence": "pad", "repeat": "repeatpad"}


def _tensor(out, *names):
    """transformers versions differ: get_*_features returns a tensor or an output object."""
    if isinstance(out, torch.Tensor):
        return out
    for n in names:
        v = getattr(out, n, None)
        if v is not None:
            return v
    raise TypeError(f"unexpected model output {type(out).__name__}")


class Matcher:
    def __init__(self, model=DEFAULT_MODEL, device="auto", pad="silence", keep=3, batch=8):
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("--device cuda asked for, but torch sees no CUDA GPU")
        if pad not in PAD:
            raise ValueError(f"--pad must be one of {sorted(PAD)}")
        self.device, self.pad, self.keep, self.batch, self.name = device, pad, keep, batch, model
        self.proc = ClapProcessor.from_pretrained(model)
        self.model = ClapModel.from_pretrained(model).to(device).eval()
        self.rate = int(self.proc.feature_extractor.sampling_rate)
        # The model's own audio->text temperature; turns cosines into a calibrated-ish softmax.
        self.scale = float(self.model.logit_scale_a.exp().item())

    @torch.inference_mode()
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        tok = self.proc.tokenizer(texts, padding=True, return_tensors="pt").to(self.device)
        e = _tensor(self.model.get_text_features(**tok), "text_embeds", "pooler_output")
        return torch.nn.functional.normalize(e.float(), dim=-1).cpu().numpy()

    @torch.inference_mode()
    def _embed_clips(self, clips: list[np.ndarray]) -> np.ndarray:
        out = []
        for i in range(0, len(clips), self.batch):
            f = self.proc.feature_extractor(
                clips[i:i + self.batch], sampling_rate=self.rate, padding=PAD[self.pad],
                return_tensors="pt")
            kw = {"input_features": f["input_features"].to(self.device)}
            if "is_longer" in f:
                kw["is_longer"] = f["is_longer"].to(self.device)
            e = _tensor(self.model.get_audio_features(**kw), "audio_embeds", "pooler_output")
            out.append(torch.nn.functional.normalize(e.float(), dim=-1).cpu().numpy())
        return np.concatenate(out)

    def embed_takes(self, takes: list[Take]) -> np.ndarray:
        """One embedding per take: the mean of its loudest windows' embeddings, renormalised."""
        clips, owner = [], []
        for t_i, t in enumerate(takes):
            for w in windows(load(t, self.rate), self.rate, WINDOW_S, self.keep):
                # Peak-normalise: a quiet recording of the right sound must score like a loud one.
                clips.append(w * (0.9 / max(float(np.abs(w).max()), 1e-6)))
                owner.append(t_i)
        e = self._embed_clips(clips)
        owner = np.array(owner)
        m = np.stack([e[owner == i].mean(axis=0) for i in range(len(takes))])
        return m / np.linalg.norm(m, axis=1, keepdims=True)

    def softmax(self, cos: np.ndarray) -> np.ndarray:
        z = cos * self.scale
        z = z - z.max(axis=-1, keepdims=True)
        p = np.exp(z)
        return p / p.sum(axis=-1, keepdims=True)

    def close(self):
        self.model = self.proc = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
