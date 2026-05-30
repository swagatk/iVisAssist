# YOLO Experiment Guide (Raspberry Pi 4)

This document captures the end-to-end workflow for:

1. Installing Ultralytics on Raspberry Pi 4.
2. Detecting object bounding boxes with YOLO.
3. Sending detection context plus image data to an LLM endpoint (local-first, cloud fallback).
4. Running with environment variables for repeatable experiments.


## 1) What We Are Running

The main runtime script is `wearable_loop_yolo.py`.

High-level flow:

1. Capture a frame via `capture.sh`.
2. Run YOLO object detection (Ultralytics `.pt` or NCNN backend).
3. Convert detections into a compact context string (labels, confidence, bounding boxes).
4. Send image + context to local model first.
5. Fall back to cloud model if local output is missing or uncertain.


## 2) Install Steps on Raspberry Pi 4

Use your virtual environment (example used in this project: `yolo_pi`).

### 2.1 System dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev libatlas-base-dev libopenblas-dev libjpeg-dev zlib1g-dev
sudo apt-get install -y portaudio19-dev python3-pyaudio
```

### 2.2 Python environment

```bash
python3 -m venv ~/.virtualenvs/yolo_pi
source ~/.virtualenvs/yolo_pi/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

### 2.3 Python packages

```bash
pip install ultralytics requests SpeechRecognition PyAudio
```

Notes:

- `ultralytics` provides YOLO inference.
- `requests` is used for LLM HTTP calls.
- `SpeechRecognition` + `PyAudio` support microphone input for chatbot scripts.


## 3) Models and Files

Expected model locations (typical):

- Ultralytics model: `~/yolo_models/yolov8n.pt`
- NCNN model directory: `~/yolo_models/yolov8n_ncnn_model`

If you only have `.pt`, use `DETECTOR_BACKEND=ultralytics`.
If NCNN folder is available, use `DETECTOR_BACKEND=ncnn` for Pi-friendly CPU inference.


## 4) Command Variables

These environment variables control performance and behavior:

- `PI4_CAPTURE_PROFILE`: capture profile (`ultra_latency`, `low_latency`, `balanced`, `quality`).
- `PI4_PRESET`: loop preset (`low_latency`, `balanced`, `quality`).
- `DETECTOR_BACKEND`: `auto`, `ultralytics`, `ncnn`, or `none`.
- `YOLO_FRAME_SKIP`: run detector every Nth frame.
- `YOLO_CONFIDENCE`: detection confidence threshold.
- `MAX_OBJECTS`: cap detections forwarded to LLM context.
- `YOLO_MODEL_PATH`: `.pt` model path.
- `YOLO_NCNN_MODEL_PATH`: NCNN model directory path.
- `FORCE_LOCAL_INFER_EVERY`: force periodic LLM inference even when scene is stable.
- `LOOP_INTERVAL_SEC`: loop sleep interval.
- `NUM_PREDICT`: LLM token budget.
- `TEMPERATURE`: LLM generation temperature.
- `OLLAMA_URL`: LLM endpoint (local server URL).
- `LOCAL_MODEL`: primary model.
- `CLOUD_MODEL`: fallback model.


## 5) Recommended Run Commands

### 5.1 NCNN + low latency + frame skip 1

```bash
PI4_CAPTURE_PROFILE=low_latency \
PI4_PRESET=low_latency \
DETECTOR_BACKEND=ncnn \
YOLO_FRAME_SKIP=1 \
YOLO_NCNN_MODEL_PATH=~/yolo_models/yolov8n_ncnn_model \
python3 ./wearable_loop_yolo.py
```

### 5.2 NCNN + low latency + frame skip 2

```bash
PI4_CAPTURE_PROFILE=low_latency \
PI4_PRESET=low_latency \
DETECTOR_BACKEND=ncnn \
YOLO_FRAME_SKIP=2 \
YOLO_NCNN_MODEL_PATH=~/yolo_models/yolov8n_ncnn_model \
python3 ./wearable_loop_yolo.py
```

### 5.3 Ultralytics `.pt` backend example

```bash
PI4_CAPTURE_PROFILE=low_latency \
PI4_PRESET=low_latency \
DETECTOR_BACKEND=ultralytics \
YOLO_MODEL_PATH=~/yolo_models/yolov8n.pt \
YOLO_FRAME_SKIP=1 \
python3 ./wearable_loop_yolo.py
```


## 6) Local vs Cloud Processing Logic

The script is local-first by default:

1. Send image + detection context to `LOCAL_MODEL`.
2. If no answer (or unclear answer), retry with `CLOUD_MODEL`.

Practical control patterns:

- Local-first hybrid (default behavior):

```bash
LOCAL_MODEL=llama3.2:1b CLOUD_MODEL=gemma4:31b-cloud
```

- Cloud-primary behavior (force both to cloud model):

```bash
LOCAL_MODEL=gemma4:31b-cloud CLOUD_MODEL=gemma4:31b-cloud
```


## 7) Outcome Summary From This Effort

Based on recent test runs on this Pi 4 setup:

- YOLO detection stage was generally around ~1.4 to ~1.5 seconds per detection pass.
- End-to-end inference latency varied significantly, roughly ~5 to ~14 seconds depending on model response time.
- Gating (`YOLO_FRAME_SKIP`, scene-change checks, and periodic force inference) reduced unnecessary LLM calls and improved practical responsiveness.
- Low-latency capture profiles improved capture speed relative to balanced defaults.
- Bluetooth audio output required recovery steps once the adapter entered an HCI timeout state; after reset/reconnect, speech output was restored.

Overall conclusion:

- This architecture works on Raspberry Pi 4 for real-time awareness with bounded object context.
- The main bottleneck is LLM inference latency, not camera capture.
- Best practical tuning is low-latency capture + NCNN or lightweight YOLO + conservative LLM token budget.


## 8) Suggested Next Tuning Iterations

1. Compare `YOLO_FRAME_SKIP=1` vs `2` for recall vs responsiveness.
2. Lower `NUM_PREDICT` further if narration is still too slow.
3. Tighten `MAX_OBJECTS` and `YOLO_CONFIDENCE` to reduce noisy context.
4. Keep `PI4_CAPTURE_PROFILE=low_latency` for daily wearable loop use.

