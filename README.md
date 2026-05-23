# iVisAssist Scripts Guide

This repository contains multiple assistant runners for different routing strategies: OpenClaw-based, Ollama Cloud API-based, and local Ollama-based.

## Requirements

- Python 3.10+
- Microphone and speaker output configured
- `speech_recognition`, `requests`, and a working audio stack (`espeak-ng`, `flite`)
- Raspberry Pi camera tools (`rpicam-still`; optional `raspi-still` compatibility)

Install Python deps (example):

```bash
pip install SpeechRecognition requests pyaudio
```

## Files At A Glance

### `chatbot.py`

Wake-word assistant (`hello pi` variants) that routes:
- Local text queries to local Ollama (`llama3.2:1b` via `/api/generate`)
- Camera/live-data style queries to OpenClaw (`openclaw agent`)

Run:

```bash
python3 ./chatbot.py
```

Use when you want hybrid local + OpenClaw behavior.

### `chatbot_cloud.py`

Wake-word assistant that uses Ollama Cloud API for all queries.

Key behavior:
- Text and image queries both go to cloud API (`/api/chat`)
- Image queries capture a fresh frame first (`raspi-still`, fallback `rpicam-still`)
- Supports fixed single model or separate text/vision model selection
- Logs loop latency for cloud text and cloud vision

Run:

```bash
export OLLAMA_API_KEY='YOUR_KEY'
# Optional: force one model for all requests
export OLLAMA_SINGLE_MODEL='gemma4:31b-cloud'
python3 ./chatbot_cloud.py
```

Important env vars:

- `OLLAMA_API_KEY` (required)
- `OLLAMA_CLOUD_URL` (default: `https://ollama.com/api/chat`)
- `OLLAMA_SINGLE_MODEL` (recommended to avoid auto-switching)
- `OLLAMA_TEXT_MODEL` / `OLLAMA_VISION_MODEL` (optional split control)

### `chatbot_local.py`

Wake-word assistant that uses a single local Ollama server/model for both text and image queries.

Current defaults:
- Endpoint: `http://localhost:11434/api/chat`
- Model: `moondream:latest`

Image queries still capture a camera frame and send it as image input.

Run:

```bash
# Optional overrides
export OLLAMA_URL='http://localhost:11434/api/chat'
export OLLAMA_MODEL='moondream:latest'
python3 ./chatbot_local.py
```

Use when you want fully local inference with one model.

### `wearable_loop.py`

Autonomous direct-vision loop (no wake word) that repeatedly scans surroundings and speaks short summaries.

Key behavior:
- Calls root `capture.sh` every loop to take a fresh image
- Sends image directly to local Ollama API (`/api/chat`)
- Speaks response to earbuds using local TTS
- Does not use OpenClaw at runtime

Run:

```bash
# Optional overrides
export OLLAMA_URL='http://localhost:11434/api/chat'
export OLLAMA_MODEL='gemma4:31b-cloud'
export LOOP_INTERVAL_SEC='8'
python3 ./wearable_loop.py
```

Use when you want continuous environment narration.

### `capture.sh`

Root capture helper used by `wearable_loop.py`.

Key behavior:
- Captures a frame with `rpicam-still`
- Overwrites `/home/pi/live_snap.jpg` each run
- Returns JSON including `image_path` for the caller

Run manually (debug):

```bash
bash ./capture.sh
```

### `setup_local_llm.py`

Utility script to download a GGUF model file into `models/`.

Run:

```bash
python3 ./setup_local_llm.py
```

### `agent_test.py`

Simple test script for image capture + local Ollama API call, mainly for manual experimentation.

Run:

```bash
python3 ./agent_test.py
```

## Camera Capture Notes

Direct wearable capture saves to:
- `/home/pi/live_snap.jpg`

`capture.sh` currently uses:
1. `rpicam-still`

Some chatbot scripts still include `raspi-still` -> `rpicam-still` fallback logic.

If you see `Camera command not found: raspi-still`, that is expected on many Pi setups as long as `rpicam-still` succeeds.

## Typical Workflows

### 1) Cloud-only fixed model (recommended for consistency)

```bash
export OLLAMA_API_KEY='YOUR_KEY'
export OLLAMA_SINGLE_MODEL='gemma4:31b-cloud'
python3 ./chatbot_cloud.py
```

### 2) Fully local single-model mode

```bash
ollama run moondream:latest
# in another terminal
python3 ./chatbot_local.py
```

### 3) Direct wearable loop (recommended)

```bash
export OLLAMA_MODEL='gemma4:31b-cloud'
python3 ./wearable_loop.py
```

### 4) Hybrid (legacy routing)

```bash
python3 ./chatbot.py
```

## Troubleshooting

### `Missing OLLAMA_API_KEY environment variable`
Set and export your key in the same terminal session before running cloud script.

### Cloud `401 unauthorized`
Usually invalid/revoked key or wrong endpoint. Verify key and `OLLAMA_CLOUD_URL`.

### Cloud `404 model not found`
Configured model is unavailable in your account/region. Set `OLLAMA_SINGLE_MODEL` to a valid name.

### Cloud `403 requires subscription`
That model is gated for your current plan. Pick another available model.

### Repetitive or stale image descriptions
- Prefer `wearable_loop.py` direct mode (current default implementation)
- Keep `OLLAMA_MODEL` fixed to a known vision-capable model
- Verify `capture.sh` returns `/home/pi/live_snap.jpg` and that file mtime updates each loop

## Notes

- Stop any loop with `Ctrl+C`.
- `initial_setup.md` contains historical setup notes; current wearable runtime is direct (`wearable_loop.py` + `capture.sh`).
