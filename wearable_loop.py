import base64
import hashlib
import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass

import requests


# Phase 1 runtime config
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")
LOOP_INTERVAL_SEC = float(os.getenv("LOOP_INTERVAL_SEC", "4"))
CAPTURE_SCRIPT = os.path.join(os.path.dirname(__file__), "capture.sh")

# Lower output budget to reduce inference + TTS time.
NUM_PREDICT = int(os.getenv("NUM_PREDICT", "24"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
REQUEST_TIMEOUT_SEC = int(os.getenv("REQUEST_TIMEOUT_SEC", "60"))

# Scene-change gating
SCENE_MIN_CONFIDENCE = float(os.getenv("SCENE_MIN_CONFIDENCE", "0.20"))
FORCE_INFER_EVERY = int(os.getenv("FORCE_INFER_EVERY", "5"))


@dataclass
class LoopMetrics:
    capture_s: float = 0.0
    read_s: float = 0.0
    infer_s: float = 0.0
    total_s: float = 0.0


class TTSWorker:
    def __init__(self):
        self._queue: "queue.Queue[str]" = queue.Queue(maxsize=4)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._stop = threading.Event()

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        try:
            self._queue.put_nowait("")
        except queue.Full:
            pass
        self._thread.join(timeout=2)

    def speak_async(self, text: str):
        clean = (text or "").strip()
        if not clean:
            return
        try:
            self._queue.put_nowait(clean)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(clean)
            except queue.Empty:
                pass

    def _run(self):
        while not self._stop.is_set():
            try:
                text = self._queue.get(timeout=0.3)
            except queue.Empty:
                continue
            if self._stop.is_set():
                break
            if not text:
                continue

            print(f"[speech] {text}")
            subprocess.Popen(
                ["espeak-ng", "-a", "0", "wake"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["flite", "-voice", "slt", "-t", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def capture_scene_path() -> str | None:
    capture_start = time.time()
    result = subprocess.run([CAPTURE_SCRIPT], capture_output=True, text=True)
    elapsed = time.time() - capture_start

    if result.returncode != 0:
        print(f"[warn] capture failed in {elapsed:.3f}s: {result.stderr.strip()}")
        return None

    try:
        payload = json.loads(result.stdout.strip())
        image_path = payload.get("image_path")
        if image_path and os.path.exists(image_path):
            return image_path
        print(f"[warn] capture output missing path: {result.stdout.strip()}")
        return None
    except json.JSONDecodeError:
        print(f"[warn] capture output invalid json: {result.stdout.strip()}")
        return None


def read_image_bytes(image_path: str) -> bytes | None:
    try:
        with open(image_path, "rb") as image_file:
            return image_file.read()
    except OSError as exc:
        print(f"[warn] failed reading image: {exc}")
        return None


def scene_delta_score(prev_bytes: bytes | None, curr_bytes: bytes) -> float:
    if prev_bytes is None:
        return 1.0
    if not prev_bytes or not curr_bytes:
        return 1.0

    # Use sampled byte differences for a cheap change estimate.
    n = min(len(prev_bytes), len(curr_bytes))
    if n == 0:
        return 1.0
    step = max(1, n // 1024)
    diff = 0
    count = 0
    for i in range(0, n, step):
        diff += abs(prev_bytes[i] - curr_bytes[i])
        count += 1
    if count == 0:
        return 1.0
    return (diff / count) / 255.0


def infer_scene(image_bytes: bytes) -> str | None:
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Describe only what is visible in the image in one short sentence. "
                    "If uncertain, say 'image unclear'."
                ),
            },
            {
                "role": "user",
                "content": "Describe what is in front of me right now.",
                "images": [image_b64],
            },
        ],
        "stream": False,
        "options": {
            "num_predict": NUM_PREDICT,
            "temperature": TEMPERATURE,
        },
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT_SEC)
    except requests.RequestException as exc:
        print(f"[warn] request failed: {exc}")
        return None

    if response.status_code != 200:
        print(f"[warn] api error {response.status_code}: {response.text}")
        return None

    data = response.json()
    output_text = data.get("message", {}).get("content", "").strip()
    if not output_text:
        print("[warn] empty vision response")
        return None
    return output_text.replace("**", "")


def run_loop(tts: TTSWorker):
    prev_image_bytes: bytes | None = None
    prev_scene_hash = ""
    loop_count = 0
    skip_count = 0

    while True:
        loop_count += 1
        loop_start = time.time()
        metrics = LoopMetrics()

        print("\n[loop] capture + analyze")
        t0 = time.time()
        image_path = capture_scene_path()
        metrics.capture_s = time.time() - t0

        if not image_path:
            print("[warn] no fresh image")
            time.sleep(LOOP_INTERVAL_SEC)
            continue

        t1 = time.time()
        image_bytes = read_image_bytes(image_path)
        metrics.read_s = time.time() - t1
        if not image_bytes:
            time.sleep(LOOP_INTERVAL_SEC)
            continue

        scene_hash = hashlib.sha1(image_bytes).hexdigest()[:12]
        delta = scene_delta_score(prev_image_bytes, image_bytes)
        force_due = (loop_count % max(1, FORCE_INFER_EVERY)) == 0

        if scene_hash == prev_scene_hash or (delta < SCENE_MIN_CONFIDENCE and not force_due):
            skip_count += 1
            print(
                "[gate] skipped inference "
                f"(delta={delta:.3f}, force_due={force_due}, skipped={skip_count})"
            )
            prev_image_bytes = image_bytes
            prev_scene_hash = scene_hash
            metrics.total_s = time.time() - loop_start
            print(
                "[timing] "
                f"capture={metrics.capture_s:.3f}s read={metrics.read_s:.3f}s total={metrics.total_s:.3f}s"
            )
            time.sleep(LOOP_INTERVAL_SEC)
            continue

        t2 = time.time()
        text = infer_scene(image_bytes)
        metrics.infer_s = time.time() - t2

        if text:
            tts.speak_async(text)

        prev_image_bytes = image_bytes
        prev_scene_hash = scene_hash
        metrics.total_s = time.time() - loop_start
        print(
            "[timing] "
            f"capture={metrics.capture_s:.3f}s read={metrics.read_s:.3f}s "
            f"infer={metrics.infer_s:.3f}s total={metrics.total_s:.3f}s"
        )
        time.sleep(LOOP_INTERVAL_SEC)


if __name__ == "__main__":
    print("iVisAssist Phase 1 Loop ONLINE")
    print(f"model={OLLAMA_MODEL}")
    print(f"endpoint={OLLAMA_URL}")
    print(
        "config="
        f"interval={LOOP_INTERVAL_SEC}s, num_predict={NUM_PREDICT}, "
        f"scene_gate={SCENE_MIN_CONFIDENCE}, force_every={FORCE_INFER_EVERY}"
    )
    print("Press Ctrl+C to stop.")

    tts_worker = TTSWorker()
    tts_worker.start()

    try:
        run_loop(tts_worker)
    except KeyboardInterrupt:
        print("\nStopping phase 1 loop safely.")
    finally:
        tts_worker.stop()