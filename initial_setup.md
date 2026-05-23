# iVisAssist Setup & Deployment Guide

This guide explains the current direct pipeline on Raspberry Pi:

1. Capture an image with `capture.sh`
2. Send it directly to Ollama vision model via local API
3. Speak the response through earbuds in `wearable_loop.py`

No orchestration framework is required for this flow.

## Architecture Overview

- Edge Layer (Pi 4): camera capture, loop control, and TTS playback.
- Inference Layer (Ollama): local Ollama API endpoint (`http://localhost:11434/api/chat`) using a vision-capable model, typically `gemma4:31b-cloud`.

## Step 1: Bluetooth Audio Pairing (PipeWire)

1. Ensure PipeWire is active:

```bash
systemctl --user status pipewire pipewire-pulse
```

2. Pair TOZO-T9 earbuds:

```bash
bluetoothctl
# Inside bluetoothctl shell:
power on
agent on
default-agent
scan on
# Replace MAC with your device address
pair 00:11:22:33:44:55
trust 00:11:22:33:44:55
connect 00:11:22:33:44:55
exit
```

3. Quick audio test:

```bash
espeak-ng -v en+f2 -s 150 "Testing system audio routing. Bluetooth link is active."
```

## Step 2: Camera Verification

1. Capture a test frame:

```bash
rpicam-still -t 400 -o /home/pi/test_still.jpg --width 320 --height 240 -n
```

2. Confirm `/home/pi/test_still.jpg` exists.

## Step 3: Ollama Setup

1. Sign in (for cloud-backed models):

```bash
ollama signin
```

2. Pull the model used by wearable loop:

```bash
ollama pull gemma4:31b-cloud
```

3. Confirm availability:

```bash
ollama list
```

## Step 4: Capture Script Setup

The active capture script is in the project root:

```bash
/home/pi/iVisAssist/capture.sh
```

Current behavior:

- Captures to `/home/pi/live_snap.jpg`
- Overwrites the same file each run
- Returns JSON with the image path

Ensure it is executable:

```bash
chmod +x /home/pi/iVisAssist/capture.sh
```

Manual test:

```bash
bash /home/pi/iVisAssist/capture.sh
```

## Step 5: Run Continuous Wearable Loop

Run with defaults:

```bash
/home/pi/.virtualenvs/ai_agent/bin/python /home/pi/iVisAssist/wearable_loop.py
```

Optional overrides:

```bash
export OLLAMA_URL='http://localhost:11434/api/chat'
export OLLAMA_MODEL='gemma4:31b-cloud'
export LOOP_INTERVAL_SEC='8'
python3 /home/pi/iVisAssist/wearable_loop.py
```

## Notes

- Stop the loop with `Ctrl+C`.
- If model responses are slow on first run, allow one warmup cycle.
- If output becomes irrelevant, confirm camera framing and that `/home/pi/live_snap.jpg` is updating.

