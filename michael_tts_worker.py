"""
QUEST — MICHAEL's voice worker (separate process)
=================================================
Runs Kokoro outside Streamlit. Loading Kokoro pulls in torch + transformers
(~3,700 modules); inside the Streamlit process that makes the file watcher rescan
them on every rerun (+1-2s per click, app-wide) and costs ~500MB of RAM.

Protocol — one JSON object per line:
  stdin : {"id": "...", "text": "<already cleaned>", "voice": "bm_george", "out": "<path without extension>"}
  stdout: {"ready": true} once the model is loaded, then
          {"id": "...", "ok": true, "path": "<file>"}  or  {"id": "...", "ok": false, "error": "..."}
The worker exits when stdin closes (i.e. when the Streamlit server stops), or after
IDLE_SECONDS without a request — it holds ~1.3GB of RAM, and the app restarts it on demand.
"""

import io
import json
import os
import sys
import threading
import time
import warnings

warnings.filterwarnings("ignore")
RATE = 24000
IDLE_SECONDS = int(os.environ.get("MICHAEL_VOICE_IDLE", "600"))
_pipelines = {}
_last_used = time.monotonic()


def _idle_watchdog():
    while True:
        time.sleep(15)
        if time.monotonic() - _last_used > IDLE_SECONDS:
            os._exit(0)


def _send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _pipeline(lang_code):
    if lang_code not in _pipelines:
        from kokoro import KPipeline
        # The model is cached after the first download — skip Hugging Face's online check
        os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            _pipelines[lang_code] = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")
        except Exception:
            os.environ.pop("HF_HUB_OFFLINE", None)
            _pipelines[lang_code] = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")
    return _pipelines[lang_code]


def _synthesize(text, voice, out_base):
    import numpy as np
    import soundfile as sf

    pipe = _pipeline(voice[0] if voice[:1] in ("a", "b") else "b")  # a=American, b=British
    gap = np.zeros(int(RATE * 0.12), dtype=np.float32)
    pieces = []
    for result in pipe(text, voice=voice, speed=1.0):
        audio = result.audio if hasattr(result, "audio") else result[2]
        if audio is not None:
            audio = audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio)
            pieces += [audio.astype(np.float32), gap]
    if not pieces:
        raise RuntimeError("no audio produced")
    wave = np.concatenate(pieces)
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
        _pipeline("b")  # warm up MICHAEL's British voice straight away
        _send({"ready": True})
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
