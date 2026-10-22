"""
QUEST — MICHAEL's voice worker (separate process)
=================================================
Runs Kokoro outside Streamlit, so no voice library ever loads into the app itself
(the torch build pulls in ~3,700 modules, which made Streamlit's file watcher add
1-2s to every click).

Two engines, same Kokoro model and voices:
  • kokoro-onnx (preferred) — ONNX Runtime, no torch. Light enough for the hosted
    website. Model files (~350MB) download on first run into QUEST_VOICE_DIR.
  • kokoro (fallback)       — the original torch build, if that's what's installed.

Protocol — one JSON object per line:
  stdin : {"id": "...", "text": "<already cleaned>", "voice": "bm_george", "out": "<path without extension>"}
  stdout: {"ready": true, "engine": "..."} once the model is loaded, then
          {"id": "...", "ok": true, "path": "<file>"}  or  {"id": "...", "ok": false, "error": "..."}
The worker exits when stdin closes (i.e. when the Streamlit server stops), or after
IDLE_SECONDS without a request — it holds ~1GB of RAM, and the app restarts it on demand.
"""

import io
import json
import os
import sys
import threading
import time
import urllib.request
import warnings

warnings.filterwarnings("ignore")
RATE = 24000
IDLE_SECONDS = int(os.environ.get("MICHAEL_VOICE_IDLE", "600"))
MODEL_DIR = os.environ.get("QUEST_VOICE_DIR", os.path.join(os.path.expanduser("~"), ".cache", "quest_voice"))
_ONNX_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
_ONNX_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")

_engine = None  # ("onnx", Kokoro) or ("torch", {lang_code: KPipeline})
_last_used = time.monotonic()


def _idle_watchdog():
    while True:
        time.sleep(15)
        if time.monotonic() - _last_used > IDLE_SECONDS:
            os._exit(0)


def _send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _fetch_onnx_files():
    os.makedirs(MODEL_DIR, exist_ok=True)
    for name in _ONNX_FILES:
        path = os.path.join(MODEL_DIR, name)
        if not os.path.exists(path):
            urllib.request.urlretrieve(_ONNX_RELEASE + name, path + ".part")
            os.replace(path + ".part", path)
    return [os.path.join(MODEL_DIR, n) for n in _ONNX_FILES]


def _load_engine():
    global _engine
    try:
        from kokoro_onnx import Kokoro
        _engine = ("onnx", Kokoro(*_fetch_onnx_files()))
        return
    except ImportError:
        pass
    from kokoro import KPipeline
    # The model is cached after the first download — skip Hugging Face's online check
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        pipe = KPipeline(lang_code="b", repo_id="hexgrad/Kokoro-82M")
    except Exception:
        os.environ.pop("HF_HUB_OFFLINE", None)
        pipe = KPipeline(lang_code="b", repo_id="hexgrad/Kokoro-82M")
    _engine = ("torch", {"b": pipe})


def _render(text, voice):
    """Text → float32 waveform at RATE Hz, in the given Kokoro voice."""
    import numpy as np

    kind, engine = _engine
    accent = voice[0] if voice[:1] in ("a", "b") else "b"  # Kokoro voice ids: a=American, b=British
    if kind == "onnx":
        samples, _ = engine.create(text, voice=voice, speed=1.0, lang="en-gb" if accent == "b" else "en-us")
        return np.asarray(samples, dtype=np.float32)

    if accent not in engine:
        from kokoro import KPipeline
        engine[accent] = KPipeline(lang_code=accent, repo_id="hexgrad/Kokoro-82M")
    gap = np.zeros(int(RATE * 0.12), dtype=np.float32)
    pieces = []
    for result in engine[accent](text, voice=voice, speed=1.0):
        audio = result.audio if hasattr(result, "audio") else result[2]
        if audio is not None:
            audio = audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio)
            pieces += [audio.astype(np.float32), gap]
    if not pieces:
        raise RuntimeError("no audio produced")
    return np.concatenate(pieces)


def _synthesize(text, voice, out_base):
    import soundfile as sf

    wave = _render(text, voice)
    try:  # MP3 is ~10x smaller than WAV; needs libsndfile >= 1.1
        buf = io.BytesIO()
        sf.write(buf, wave, RATE, format="MP3")
        path = out_base + ".mp3"
    except Exception:
        buf = io.BytesIO()
        sf.write(buf, wave, RATE, format="WAV", subtype="PCM_16")
        path = out_base + ".wav"
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(buf.getvalue())
    os.replace(tmp, path)
    return path


def main():
    global _last_used
    try:
        _load_engine()  # warm up straight away (downloads the model on a fresh server)
        _send({"ready": True, "engine": _engine[0]})
    except Exception as e:
        _send({"ready": False, "error": str(e)[:300]})
        return
    _last_used = time.monotonic()
    threading.Thread(target=_idle_watchdog, daemon=True).start()
    for line in sys.stdin:
        _last_used = time.monotonic()
        if not line.strip():
            continue
        req = {}
        try:
            req = json.loads(line)
            path = _synthesize(req["text"], req["voice"], req["out"])
            _send({"id": req.get("id"), "ok": True, "path": path})
        except Exception as e:
            _send({"id": req.get("id"), "ok": False, "error": str(e)[:300]})
        _last_used = time.monotonic()  # idle time counts from the end of the last note


if __name__ == "__main__":
    main()
