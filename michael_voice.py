"""
QUEST — MICHAEL voice layer
===========================
Speech-to-text : Groq Whisper (multilingual — English, Hindi, Hinglish).
Voice notes    : Kokoro (open-source, runs locally on CPU) renders MICHAEL's replies
                 as audio files in his own voice — see michael_persona.VOICE. It runs
                 in a separate worker process so torch never loads into Streamlit.
Fallback voice : the browser's built-in Web Speech API, used for Hindi replies and
                 wherever Kokoro isn't installed.

Browser speech runs on the parent Streamlit window rather than inside the component
iframe, because browsers only allow speech after the user has interacted with
the page — and the user has always clicked or recorded in the parent window.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import queue
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import uuid

import streamlit as st

_GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_STT_MODELS = ("whisper-large-v3-turbo", "whisper-large-v3")


# ──────────────────────────────────────────────────────────────────────────────
# Speech-to-text
# ──────────────────────────────────────────────────────────────────────────────
def transcribe(audio_bytes: bytes, api_key: str, filename: str = "voice.wav") -> tuple[str, str]:
    """Transcribe recorded audio with Groq Whisper. Returns (text, error)."""
    if not audio_bytes:
        return "", "No audio recorded."
    if not api_key or not api_key.startswith("gsk_"):
        return "", "Voice input needs a Groq API key."

    last_error = ""
    for model in _STT_MODELS:
        boundary = uuid.uuid4().hex
        body = b"".join([
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{model}\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\njson\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"temperature\"\r\n\r\n0\r\n".encode(),
            (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
             f"Content-Type: audio/wav\r\n\r\n").encode(),
            audio_bytes,
            f"\r\n--{boundary}--\r\n".encode(),
        ])
        req = urllib.request.Request(
            _GROQ_STT_URL, data=body, method="POST",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": f"multipart/form-data; boundary={boundary}",
                     "User-Agent": "QUEST-App/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                text = (json.loads(r.read().decode()).get("text") or "").strip()
            return (text, "") if text else ("", "Couldn't hear anything — try again a little closer to the mic.")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")[:200]
            if e.code in (401, 403):
                return "", "The Groq API key was rejected."
            if e.code == 429:
                return "", "Voice rate limit hit — wait a moment and try again."
            last_error = f"HTTP {e.code}: {detail}"
        except Exception as ex:
            last_error = str(ex)
    return "", f"Transcription failed. {last_error}"


# ──────────────────────────────────────────────────────────────────────────────
# Text-to-speech
# ──────────────────────────────────────────────────────────────────────────────
def speech_text(raw: str, limit: int = 1500) -> str:
    """Turn a markdown-ish MICHAEL reply into something pleasant to hear."""
    t = raw or ""
    t = "\n".join(ln for ln in t.splitlines() if not ln.strip().startswith("|"))  # tables don't read well
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[*_`#>]+", "", t)
    t = re.sub(r"\bRs\.?\s*(?=[\d+\-])", "rupees ", t)
    t = t.replace("₹", "rupees ")
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]", "", t)  # emoji
    t = re.sub(r"^\s*[-•]\s*", "", t, flags=re.M)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > limit:
        cut = t[:limit]
        t = cut[: max(cut.rfind(". "), cut.rfind("। ")) + 1] or cut
    return t


def speak(text: str, autoplay: bool = False, key: str = "") -> None:
    """Render a compact play/stop control; optionally start speaking straight away."""
    spoken = speech_text(text)
    if not spoken:
        return
    lang = "hi-IN" if re.search(r"[ऀ-ॿ]", spoken) else "en-IN"
    payload = json.dumps({"text": spoken, "lang": lang, "autoplay": bool(autoplay), "key": key})
    st.iframe(f"""
<style>
  body {{ margin:0; font-family: Inter, system-ui, sans-serif; background: transparent; }}
  button {{ border:1px solid rgba(127,127,127,.35); background:transparent; color:#5DCAA5; border-radius:999px;
           padding:3px 12px; font-size:12px; font-weight:600; cursor:pointer; }}
  button:hover {{ background:rgba(93,202,165,.12); }}
  span {{ font-size:11px; color:#8a8f98; margin-left:8px; }}
</style>
<button id="b">🔊 Listen</button><span id="s"></span>
<script>
const P = {payload};
let W = window;
try {{ if (window.parent && window.parent.speechSynthesis) W = window.parent; }} catch (e) {{}}
const synth = W.speechSynthesis, btn = document.getElementById("b"), st = document.getElementById("s");
if (!synth) {{ btn.disabled = true; st.textContent = "Voice not supported in this browser"; }}

function pickVoice() {{
  const vs = synth.getVoices(), want = P.lang.toLowerCase(), base = want.split("-")[0];
  const male = /(prabhat|ravi|hemant|madhur|male)/i;
  return vs.find(v => v.lang.toLowerCase() === want && male.test(v.name))
      || vs.find(v => v.lang.toLowerCase() === want)
      || vs.find(v => v.lang.toLowerCase().startsWith(base) && /india/i.test(v.name))
      || vs.find(v => v.lang.toLowerCase().startsWith(base)) || null;
}}
function chunks(t) {{  // Chrome stops long utterances (~15s), so speak sentence by sentence
  const parts = t.split(/(?<=[.!?।])\\s+/), out = []; let cur = "";  // keeps "0.49" intact
  for (const p of parts) {{ if ((cur + " " + p).length > 220 && cur) {{ out.push(cur); cur = p; }} else cur = cur ? cur + " " + p : p; }}
  if (cur.trim()) out.push(cur);
  return out;
}}
function setUI(on) {{ btn.textContent = on ? "■ Stop" : "🔊 Listen"; st.textContent = on ? "MICHAEL is speaking…" : ""; }}
function play() {{
  synth.cancel();
  const v = pickVoice(), list = chunks(P.text);
  W.__michaelSpeaking = P.key;
  list.forEach((c, i) => {{
    const u = new W.SpeechSynthesisUtterance(c.trim());
    u.lang = P.lang; if (v) u.voice = v; u.rate = 1.03; u.pitch = 0.95;
    if (i === list.length - 1) u.onend = () => {{ W.__michaelSpeaking = null; setUI(false); }};
    synth.speak(u);
  }});
  setUI(true);
}}
btn.onclick = () => {{ if (synth.speaking && W.__michaelSpeaking === P.key) {{ synth.cancel(); W.__michaelSpeaking = null; setUI(false); }} else play(); }};
if (synth && synth.speaking && W.__michaelSpeaking === P.key) setUI(true);
if (synth && P.autoplay) {{
  if (synth.getVoices().length) play();
  else synth.onvoiceschanged = () => {{ synth.onvoiceschanged = null; play(); }};
}}
</script>
""", height=34)


# ──────────────────────────────────────────────────────────────────────────────
# Voice notes (Kokoro, in a separate worker process — see michael_tts_worker.py)
# ──────────────────────────────────────────────────────────────────────────────
_WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "michael_tts_worker.py")


def kokoro_installed() -> bool:
    """True if Kokoro can be used — checked without importing it (that's the expensive part)."""
    return importlib.util.find_spec("kokoro") is not None


class _VoiceWorker:
    """One long-lived Kokoro process per server, fed one request at a time."""

    def __init__(self):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            [sys.executable, _WORKER_SCRIPT], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1, creationflags=flags,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.ready = False
        self.failed = ""
        self.lock = threading.Lock()
        self.replies: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue  # stray library output
            if "ready" in msg:
                self.ready, self.failed = bool(msg["ready"]), msg.get("error", "")
            else:
                self.replies.put(msg)

    def alive(self) -> bool:
        return self.proc.poll() is None and not self.failed

    def render(self, text: str, voice: str, out_base: str, timeout: float) -> str | None:
        with self.lock:
            req_id = uuid.uuid4().hex
            self.proc.stdin.write(json.dumps({"id": req_id, "text": text, "voice": voice, "out": out_base}) + "\n")
            self.proc.stdin.flush()
            while True:
                msg = self.replies.get(timeout=timeout)
                if msg.get("id") == req_id:
                    return msg.get("path") if msg.get("ok") else None


@st.cache_resource(show_spinner=False)
def _worker() -> _VoiceWorker:
    return _VoiceWorker()


def _live_worker() -> _VoiceWorker:
    """The current worker, restarted if it exited (it shuts down after 10 idle minutes)."""
    worker = _worker()
    if worker.proc.poll() is not None and not worker.failed:  # a failed load isn't retried
        _worker.clear()
        worker = _worker()
    return worker


def warm_up() -> None:
    """Start the worker early so the model load (~12s) happens before it's needed."""
    if kokoro_installed():
        _live_worker()


def voice_ready() -> bool:
    return kokoro_installed() and _live_worker().ready


def voice_note(text: str, folder: str, voice: str, timeout: float = 120) -> str | None:
    """Create (or reuse) a saved voice note for a reply. Returns the file path, or None."""
    spoken = speech_text(text, limit=2500)
    if not spoken or re.search(r"[\u0900-\u097F]", spoken):  # Hindi stays with the browser voice
        return None
    digest = hashlib.sha1(f"{voice}|{text}".encode("utf-8")).hexdigest()[:16]
    os.makedirs(folder, exist_ok=True)
    for ext in (".mp3", ".wav"):
        if os.path.exists(os.path.join(folder, digest + ext)):
            return os.path.join(folder, digest + ext)
    if not kokoro_installed():
        return None
    worker = _live_worker()
    if not worker.alive():  # the model failed to load — use the browser voice instead
        return None
    try:
        return worker.render(spoken, voice, os.path.join(folder, digest), timeout)
    except (queue.Empty, OSError, ValueError):
        return None
