import base64
import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass

import requests

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


# Phase 2 runtime config
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "llama3.2:1b")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "gemma4:31b-cloud")
CAPTURE_SCRIPT = os.path.join(os.path.dirname(__file__), "capture.sh")

# Pi 4 tuned presets. Any explicit env var still overrides these defaults.
PI4_PRESET = os.getenv("PI4_PRESET", "balanced").strip().lower()
PI4_PRESETS = {
    "low_latency": {
        "LOOP_INTERVAL_SEC": 2.0,
        "REQUEST_TIMEOUT_SEC": 30,
        "YOLO_FRAME_SKIP": 4,
        "YOLO_CONFIDENCE": 0.45,
        "MAX_OBJECTS": 4,
        "FORCE_LOCAL_INFER_EVERY": 6,
        "NUM_PREDICT": 20,
        "TEMPERATURE": 0.10,
    },
    "balanced": {
        "LOOP_INTERVAL_SEC": 3.0,
        "REQUEST_TIMEOUT_SEC": 45,
        "YOLO_FRAME_SKIP": 3,
        "YOLO_CONFIDENCE": 0.35,
        "MAX_OBJECTS": 6,
        "FORCE_LOCAL_INFER_EVERY": 5,
        "NUM_PREDICT": 28,
        "TEMPERATURE": 0.15,
    },
    "quality": {
        "LOOP_INTERVAL_SEC": 4.0,
        "REQUEST_TIMEOUT_SEC": 60,
        "YOLO_FRAME_SKIP": 2,
        "YOLO_CONFIDENCE": 0.30,
        "MAX_OBJECTS": 8,
        "FORCE_LOCAL_INFER_EVERY": 4,
        "NUM_PREDICT": 40,
        "TEMPERATURE": 0.20,
    },
}

if PI4_PRESET not in PI4_PRESETS:
    print(f"[warn] unknown PI4_PRESET='{PI4_PRESET}', using balanced")
    PI4_PRESET = "balanced"

_PRESET = PI4_PRESETS[PI4_PRESET]
LOOP_INTERVAL_SEC = _env_float("LOOP_INTERVAL_SEC", _PRESET["LOOP_INTERVAL_SEC"])
REQUEST_TIMEOUT_SEC = _env_int("REQUEST_TIMEOUT_SEC", _PRESET["REQUEST_TIMEOUT_SEC"])

# YOLO control
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")
YOLO_FRAME_SKIP = _env_int("YOLO_FRAME_SKIP", _PRESET["YOLO_FRAME_SKIP"])
YOLO_CONFIDENCE = _env_float("YOLO_CONFIDENCE", _PRESET["YOLO_CONFIDENCE"])
MAX_OBJECTS = _env_int("MAX_OBJECTS", _PRESET["MAX_OBJECTS"])
FORCE_LOCAL_INFER_EVERY = _env_int("FORCE_LOCAL_INFER_EVERY", _PRESET["FORCE_LOCAL_INFER_EVERY"])
NUM_PREDICT = _env_int("NUM_PREDICT", _PRESET["NUM_PREDICT"])
TEMPERATURE = _env_float("TEMPERATURE", _PRESET["TEMPERATURE"])


@dataclass
class Detection:
    name: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class LoopMetrics:
    capture_s: float = 0.0
    detect_s: float = 0.0
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
    result = subprocess.run([CAPTURE_SCRIPT], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[warn] capture failed: {result.stderr.strip()}")
        return None

    try:
        payload = json.loads(result.stdout.strip())
        image_path = payload.get("image_path")
        if image_path and os.path.exists(image_path):
            return image_path
    except json.JSONDecodeError:
        pass

    print(f"[warn] invalid capture output: {result.stdout.strip()}")
    return None


def init_detector():
    if YOLO is None:
        print("[warn] ultralytics not installed. YOLO path disabled.")
        return None
    try:
        return YOLO(YOLO_MODEL_PATH)
    except Exception as exc:
        print(f"[warn] failed to load YOLO model '{YOLO_MODEL_PATH}': {exc}")
        return None


def detect_objects(detector, image_path: str) -> list[Detection]:
    if detector is None:
        return []

    try:
        results = detector.predict(
            source=image_path,
            conf=YOLO_CONFIDENCE,
            verbose=False,
            max_det=MAX_OBJECTS,
        )
    except Exception as exc:
        print(f"[warn] detection failed: {exc}")
        return []

    detections: list[Detection] = []
    for result in results:
        names = result.names
        boxes = result.boxes
        if boxes is None:
            continue
        for box in boxes:
            cls_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            coords = box.xyxy[0].tolist()
            detections.append(
                Detection(
                    name=str(names.get(cls_id, f"cls_{cls_id}")),
                    confidence=confidence,
                    x1=int(coords[0]),
                    y1=int(coords[1]),
                    x2=int(coords[2]),
                    y2=int(coords[3]),
                )
            )
    detections.sort(key=lambda d: d.confidence, reverse=True)
    return detections[:MAX_OBJECTS]


def detections_to_prompt(detections: list[Detection]) -> str:
    if not detections:
        return "No confident objects detected."

    lines = []
    for det in detections:
        lines.append(
            f"- {det.name} conf={det.confidence:.2f} bbox=({det.x1},{det.y1})-({det.x2},{det.y2})"
        )
    return "Detected objects:\n" + "\n".join(lines)


def build_payload(model: str, image_bytes: bytes, context: str) -> dict:
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a wearable assistant. "
                    "Use the object detections as hints, verify against the image, "
                    "and answer in one short sentence focused on nearby relevant objects."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Describe what is in front of me right now. "
                    "Prioritize practical awareness.\n"
                    f"{context}"
                ),
                "images": [image_b64],
            },
        ],
        "stream": False,
        "options": {
            "num_predict": NUM_PREDICT,
            "temperature": TEMPERATURE,
        },
    }


def ask_model(model: str, image_bytes: bytes, context: str) -> str | None:
    payload = build_payload(model, image_bytes, context)
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT_SEC)
    except requests.RequestException as exc:
        print(f"[warn] request to {model} failed: {exc}")
        return None

    if response.status_code != 200:
        print(f"[warn] api error from {model}: {response.status_code} {response.text}")
        return None

    content = response.json().get("message", {}).get("content", "").strip()
    if not content:
        return None
    return content.replace("**", "")


def run_loop(tts: TTSWorker):
    detector = init_detector()
    frame_idx = 0
    skip_infer_count = 0
    prev_signature = ""
    last_detections: list[Detection] = []

    while True:
        frame_idx += 1
        loop_start = time.time()
        metrics = LoopMetrics()

        t0 = time.time()
        image_path = capture_scene_path()
        metrics.capture_s = time.time() - t0
        if not image_path:
            time.sleep(LOOP_INTERVAL_SEC)
            continue

        try:
            with open(image_path, "rb") as image_file:
                image_bytes = image_file.read()
        except OSError as exc:
            print(f"[warn] read image failed: {exc}")
            time.sleep(LOOP_INTERVAL_SEC)
            continue

        run_detection = (frame_idx % max(1, YOLO_FRAME_SKIP)) == 0
        detections: list[Detection] = []
        object_signature = prev_signature
        if run_detection:
            t1 = time.time()
            detections = detect_objects(detector, image_path)
            metrics.detect_s = time.time() - t1
            last_detections = detections
            object_signature = "|".join([f"{d.name}:{int(d.confidence * 100)}" for d in detections])
        else:
            detections = last_detections

        force_due = (frame_idx % max(1, FORCE_LOCAL_INFER_EVERY)) == 0
        scene_changed = run_detection and object_signature != prev_signature
        should_infer = bool(detections) and scene_changed or force_due

        if not should_infer:
            skip_infer_count += 1
            metrics.total_s = time.time() - loop_start
            print(
                "[gate] skip infer "
                f"frame={frame_idx} skipped={skip_infer_count} total={metrics.total_s:.3f}s"
            )
            time.sleep(LOOP_INTERVAL_SEC)
            continue

        context = detections_to_prompt(detections)

        t2 = time.time()
        text = ask_model(LOCAL_MODEL, image_bytes, context)
        used_model = LOCAL_MODEL

        # Local-first fallback to cloud only if local result is missing or uncertain.
        if not text or "image unclear" in text.lower():
            fallback = ask_model(CLOUD_MODEL, image_bytes, context)
            if fallback:
                text = fallback
                used_model = CLOUD_MODEL
        metrics.infer_s = time.time() - t2

        if text:
            tts.speak_async(text)
        else:
            print("[warn] both local and cloud models returned no response")

        if run_detection:
            prev_signature = object_signature
        metrics.total_s = time.time() - loop_start
        print(
            "[timing] "
            f"model={used_model} capture={metrics.capture_s:.3f}s "
            f"detect={metrics.detect_s:.3f}s infer={metrics.infer_s:.3f}s "
            f"total={metrics.total_s:.3f}s objs={len(detections)}"
        )
        time.sleep(LOOP_INTERVAL_SEC)


if __name__ == "__main__":
    print("iVisAssist Phase 2 YOLO Loop ONLINE")
    print(f"endpoint={OLLAMA_URL}")
    print(f"local_model={LOCAL_MODEL} cloud_model={CLOUD_MODEL}")
    print(f"pi4_preset={PI4_PRESET}")
    print(
        "config="
        f"interval={LOOP_INTERVAL_SEC}s frame_skip={YOLO_FRAME_SKIP} "
        f"conf={YOLO_CONFIDENCE} max_objects={MAX_OBJECTS} "
        f"force_every={FORCE_LOCAL_INFER_EVERY} num_predict={NUM_PREDICT} temp={TEMPERATURE}"
    )
    print("Press Ctrl+C to stop.")

    tts_worker = TTSWorker()
    tts_worker.start()

    try:
        run_loop(tts_worker)
    except KeyboardInterrupt:
        print("\nStopping phase 2 loop safely.")
    finally:
        tts_worker.stop()