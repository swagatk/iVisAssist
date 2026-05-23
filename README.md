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

Autonomous OpenClaw loop (no wake word) that repeatedly scans surroundings and speaks short summaries.

Key behavior:
- Ensures `skills/isight` is linked into OpenClaw workspace
- Calls `openclaw agent` periodically
- Speaks response to earbuds using local TTS

Run:

```bash
python3 ./wearable_loop.py
```

Use when you want continuous environment narration.

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

Scripts that need images save to:
- `/home/pi/live_snap.jpg`

Capture command fallback order:
1. `raspi-still`
2. `rpicam-still`

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

### 3) Hybrid (legacy routing)

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
- Ensure image file updates each capture
- Use a fixed vision-capable model
- Keep camera pointed at clearly different scenes for testing

## Notes

- Stop any loop with `Ctrl+C`.
- `initial_setup.md` contains the deeper end-to-end deployment notes and hardware setup details.
