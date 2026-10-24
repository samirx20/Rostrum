"""The voice model's files in the same download registry as the clean-up models (cleanup/models.py, fetch.py): a line
whose model is missing gets the same question (size, licence) and the same checked download. Three files in `qwentts`
(the folder `voice.model_dir()` reads): the talker, the codec and the program that runs them. Sizes and fingerprints
are those of the files the voice was measured with (VOICE.md).

TO DO BEFORE RELEASE (needs Sam's OK to publish): none of the three has a pinned download address yet. The talker is our
own Q6_K quantisation of the official Apache-2.0 weights and the program our own build of qwentts.cpp (MIT), neither hosted; the
codec is upstream's Q8_0 (Serveurperso/Qwen3-TTS-GGUF, Apache-2.0), downloaded from there (pinned). Until the talker's
and the program's `url` is set the download says so, loudly (`fetch._fail`), instead of pretending. They go on the
Rostrum page on Hugging Face (Sam, 2026-10-23: NEEDS_DECISIONS, "Music-splitting model file") next to umxhq.onnx.
"""
from __future__ import annotations

from .cleanup.models import Model

_ENGINE = "qwen3-tts-1.7b-customvoice-q6k@qwentts-01b6127"      # voice.ENGINE: the files decide the audio
TALKER = Model("qwentts", "qwen-talker-1.7b-customvoice-Q6_K.gguf", 1578673536,
               "7933c18c352a6a69aeffa68277b31cc9cd3fdd8a9d93a27577aaacdad82c7d1d",
               "Apache-2.0 (Qwen3-TTS 1.7B CustomVoice, Qwen team; our Q6_K quantisation)", _ENGINE, 2.5)
CODEC = Model("qwentts", "qwen-tokenizer-12hz-Q8_0.gguf", 291150624,
              "1883beeed99348fc35e23dd225e9082f93f6f8c109330a33d935baa8acdbfd94",
              "Apache-2.0 (Qwen3-TTS tokenizer 12 Hz, Qwen team; Q8_0)", _ENGINE, 0.5,
              "https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF/resolve/b7ee2e8c7459c3bea99da23e3d178125a7d1713c/"
              "qwen-tokenizer-12hz-Q8_0.gguf")
PROGRAM = Model("qwentts", "qwen-tts.exe", 47329792,
                "5e69b1988e819036294c72186b1b0ec839fc08dab41529cb79b200396f9a4bd7",
                "MIT (qwentts.cpp, ServeurpersoCom; our build)", _ENGINE, 0.0)
FILES = (TALKER, CODEC, PROGRAM)
