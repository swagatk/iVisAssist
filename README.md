# iVisAssist Scripts Guide

This repository contains voice and wearable assistant scripts using local Ollama and Ollama cloud-backed models through the local Ollama API.

## Requirements

- Python 3.10+
- Microphone and speaker output configured
- `SpeechRecognition`, `requests`, and a working audio stack (`espeak-ng`, `flite`)
- Raspberry Pi camera tools (`rpicam-still`)

Install Python deps (example):

```bash
pip install SpeechRecognition requests pyaudio
```

## Files At A Glance

### `chatbot_cloud.py`

Wake-word assistant that routes all queries to cloud models.

Key behavior:
- Uses Ollama cloud API auth (`OLLAMA_API_KEY`)
- Supports single-model pinning (`OLLAMA_SINGLE_MODEL`) or text/vision split
- Captures image for visual prompts and sends to cloud model
- Logs per-mode latency

Run:

```bash
export OLLAMA_API_KEY='YOUR_KEY'
export OLLAMA_SINGLE_MODEL='gemma4:31b-cloud'
python3 ./chatbot_cloud.py
```

### `chatbot_local.py`

Wake-word assistant using one local model for both text and image queries.

Current defaults:
- Endpoint: `http://localhost:11434/api/chat`
- Model: `moondream:latest`

Run:

```bash
export OLLAMA_URL='http://localhost:11434/api/chat'
export OLLAMA_MODEL='moondream:latest'
python3 ./chatbot_local.py
```

### `chatbot_hybrid.py`

Wake-word assistant with hybrid routing:
- Local route: `llama3.2:1b`
- Cloud route: `gemma4:31b-cloud`

Key behavior:
- Routes visual/live-data style prompts to cloud model
- Uses root `capture.sh` for image capture when needed
- Uses local Ollama API (`/api/chat`) for both routes
- Logs model latency and total end-to-end loop latency per mode

Run:

```bash
export OLLAMA_CHAT_URL='http://localhost:11434/api/chat'
export LOCAL_MODEL='llama3.2:1b'
export CLOUD_MODEL='gemma4:31b-cloud'
python3 ./chatbot_hybrid.py
```

### `wearable_loop.py`

Autonomous direct-vision loop (no wake word) for continuous scene narration.

Key behavior:
- Calls root `capture.sh` each loop
- Sends image directly to local Ollama API (`/api/chat`)
- Speaks one short scene description

Run:

```bash
export OLLAMA_URL='http://localhost:11434/api/chat'
export OLLAMA_MODEL='gemma4:31b-cloud'
export LOOP_INTERVAL_SEC='8'
python3 ./wearable_loop.py
```

### `capture.sh`

Root capture helper used by `wearable_loop.py` and `chatbot_hybrid.py`.

Key behavior:
- Captures with `rpicam-still`
- Overwrites `/home/pi/live_snap.jpg` each run
- Returns JSON including `image_path`

Run manually:

```bash
bash ./capture.sh
```

### `setup_local_llm.py`

Downloads the GGUF model artifact into `models/`.

Run:

```bash
python3 ./setup_local_llm.py
```

### `agent_test.py`

Utility test script for capture + inference experimentation.

Run:

```bash
python3 ./agent_test.py
```

## Camera Capture Notes

- Capture output path: `/home/pi/live_snap.jpg`
- Capture command: `rpicam-still`
- Capture resolution is configured in `capture.sh` (currently `160x120`)

## Typical Workflows

### 1) Cloud-only voice assistant

```bash
export OLLAMA_API_KEY='YOUR_KEY'
export OLLAMA_SINGLE_MODEL='gemma4:31b-cloud'
python3 ./chatbot_cloud.py
```

### 2) Local-only voice assistant

```bash
ollama run moondream:latest
python3 ./chatbot_local.py
```

### 3) Hybrid voice assistant (local + cloud)

```bash
python3 ./chatbot_hybrid.py
```

### 4) Continuous wearable scene narration

```bash
python3 ./wearable_loop.py
```

## Troubleshooting

### `Missing OLLAMA_API_KEY environment variable`
Set and export the key in the same shell before running `chatbot_cloud.py`.

### Cloud `401 unauthorized`
Verify key validity and cloud endpoint config.

### Cloud `404 model not found`
Choose a model name available in your account/region.

### Cloud `403 requires subscription`
Selected model is plan-gated. Switch to an available model.

### Repetitive or stale image descriptions
- Confirm `/home/pi/live_snap.jpg` is updating on each loop
- Keep vision model fixed (for example `gemma4:31b-cloud`)
- Prefer direct wearable path (`wearable_loop.py`) for deterministic image-grounded behavior

## Notes

- Stop loops with `Ctrl+C`.
- `initial_setup.md` reflects the current direct runtime flow.
