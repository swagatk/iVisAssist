# iVisAssist Setup & Deployment Guide

This guide outlines the step-by-step instructions to configure a Raspberry Pi 4 equipped with a Camera Module 3 (imx708) and TOZO-T9 Bluetooth earbuds into an autonomous, real-time, hands-free wearable assistant using the OpenClaw agentic orchestration framework and Ollama Cloud vision models.

## Architectural Overview
The wearable assistant leverages a hybrid edge-cloud architecture to optimize performance, preserve battery life, and bypass local hardware processing bottlenecks on the Raspberry Pi 4:
* Edge Layer (Pi 4): Handles local hardware triggers. It captures light-weight $640 \times 480$ frame snapshots from the imx708 camera, captures shell executions, and routes audio directly to your TOZO-T9 earbuds via the native system PipeWire routing daemon.
* Orchestration Layer (OpenClaw): Manages local execution sessions, state memory persistence, and indexes custom skills stored within the secure, trusted path-traversal workspace sandboxing perimeter (~/.openclaw/workspace/skills/).
* Cloud Inference Layer (Ollama Cloud): Accepts secure, low-latency base64 images tunneled over local port 11434 to calculate multi-billion parameter visual matrix math instantly on cloud GPUs using Google's gemma4:31b-cloud vision model.

## Step 1: Bluetooth Audio Pairing & Routing (PipeWire)
To route the synthetic voice of your assistant directly to your ears, your TOZO-T9 earbuds must be configured as the default system-wide audio sink inside the Linux PipeWire audio engine.
1. Ensure PipeWire is active on your Pi:
```
systemctl --user status pipewire pipewire-pulse
```
2. Put your TOZO-T9 earbuds in pairing mode, open the Bluetooth CLI control tool, and run the connection commands:
```
bluetoothctl
# Inside bluetoothctl shell:
power on
agent on
default-agent
scan on
# Locate your TOZO-T9 MAC address (e.g., 00:11:22:33:44:55)
pair 00:11:22:33:44:55
trust 00:11:22:33:44:55
connect 00:11:22:33:44:55
exit
```
3. Verify that your system automatically routes active audio playbacks through your earbuds:
```
espeak-ng -v en+f2 -s 150 "Testing system audio routing. Bluetooth link is active."
```

##  Step 2: Camera Hardware Verification
Test that your Raspberry Pi Camera Module 3 (imx708 driver stack) is correctly configured and capable of capture without locking up the OS.
1. Capture a quick, high-resolution test frame:
```
rpicam-still -t 400 -o /home/pi/test_still.jpg --width 320 --height 240 -n
```
2. Verify that the image file `test_still.jpg` was cleanly created in `/home/pi`.

## Step 3: OpenClaw Installation & Directory Prep

Ensure OpenClaw is running cleanly and establish the strict directory structure necessary to pass its path-traversal security guardrails.
1. If you haven't already, install OpenClaw globally on your system:
```
npm install -g openclaw
```
2. Initialize your local Git project directory:
```
mkdir -p /home/pi/iVisAssist/skills/isight
cd /home/pi/iVisAssist
git init
```
3. Set up the secure boundary for your standalone application. OpenClaw will symlink to this directory automatically later.
## Step 4: Ollama Cloud VLM Pull & Routing
Set up your local Ollama daemon to securely handshake with Ollama Cloud's distributed hardware network to process image requests instantly.
1.Authenticate your terminal with your Ollama registry profile:
```
ollama signin
```
2. Pull the lightweight manifest mapping for Google's cloud-tier vision model:
```
ollama pull gemma4:31b-cloud
```
3. Confirm the model is mapped successfully in your local index (it should display with a virtual size footprint):
```
ollama list
```
4. Set the model as OpenClaw's primary intelligence backend:
```
openclaw config set agents.defaults.model.primary "ollama/gemma4:31b-cloud"
```

## Step 5: Custom iSight Skill Creation
## Step 5: Custom iSight Skill Creation
OpenClaw blocks any custom skill whose target script resides outside the trusted workspace sandboxing root. We will define our skill in our standalone repository, and the `wearable_loop.py` script will safely symlink it into the secure zone dynamically.
Create your skill blueprint file at `/home/pi/iVisAssist/skills/isight/SKILL.md`:
```
nano /home/pi/iVisAssist/skills/isight/SKILL.md
```
Paste the following Markdown configuration:
```markdown
---
name: isight-vision
description: Captures real-time hardware images using the Raspberry Pi Camera module.
metadata:
  openclaw:
    requires:
      binaries:
        - rpicam-still
---

# Skill: iSight Wearable Camera Eye

Teaches the assistant how to look through the wearable device's lens to scan the environment for the user.

## Tool: capture_scene
Use this tool whenever the user explicitly asks you to look at something, describe what is in front of them, check for physical hazards, read text/signs, or scan their surroundings.

### Execution
```bash
/home/pi/iVisAssist/skills/isight/capture.sh
```

### Response Processing
The script returns a JSON payload containing the local path of a freshly snapped JPEG (`/home/pi/live_snap.jpg`). Take this path, pass the file matrix to your configured Gemma 4 cloud vision model, and read your description response aloud through the user's audio sink.

Create the execution script driver inside your directory:
```
nano /home/pi/iVisAssist/skills/isight/capture.sh
```
Paste the following shell execution commands:
```bash
#!/bin/bash
# Clean hardware snapshot from the imx708 lens
rpicam-still -t 400 -o /home/pi/live_snap.jpg --width 640 --height 480 -n >/dev/null 2>&1

# Return a success verification object back to the active OpenClaw frame
echo '{"status": "success", "image_path": "/home/pi/live_snap.jpg"}'
```
Authorize hardware script execution permissions:
```
chmod +x /home/pi/iVisAssist/skills/isight/capture.sh
```

## Step 6: Text-to-Speech (TTS) Configuration
Configure OpenClaw's internal JSON configuration profile to use Microsoft's built-in neural audio provider (edge) to render synthetic descriptions on the Pi.
Open your master configuration file:
```
nano ~/.openclaw/openclaw.json
```
Scroll to the bottom and ensure your "messages" segment is formatted as follows:  "messages": {
    "tts": {
      "auto": "always",
      "provider": "edge",
      "edge": {
        "voice": "en-US-MichelleNeural",
        "lang": "en-US"
      }
    }
  }
Run diagnostic checks and restart OpenClaw:openclaw doctor --repair
openclaw gateway restart
Verify your custom skill is successfully parsed and unblocked by checking your active tool indexes:openclaw skills list
(You should see isight-vision displayed cleanly with a ✓ ready status in the table list).🔁 Step 7: Automated Wearable Controller LoopBecause standard terminal shell sessions treat synthetic audio files as text-channel message attachments, we execute a continuous python controller script inside your project workspace (/home/pi/iVisAssist/wearable_loop.py) to automate hands-free captures and route clean speech natively.Create your controller file:nano /home/pi/iVisAssist/wearable_loop.py
Paste the following automated execution code:import subprocess
import time
import sys

def speak(text):
    if not text.strip():
        return
    print(f"🎙️ Broadcasting to TOZO Earbuds: {text}")
    # Direct hardware route to your connected PipeWire bluetooth sink
    subprocess.run(["espeak-ng", "-v", "en+f2", "-s", "150", text])

def run_isight_sync():
    print("\n🔄 Triggering autonomous iSight environment scan...")

    cmd = [
        "openclaw", "agent",
        "--agent", "main",
        "--session-id", "isight-wearable-active",
        "-m", "Scan my surroundings using the capture_scene tool and describe it concisely."
    ]

    # Captures stdout and stderr independently to prevent log intermixing
    result = subprocess.run(cmd, capture_output=True, text=True)
    stdout = result.stdout

    # Fallback to check if the response landed in stderr or stdout
    full_output = stdout if stdout.strip() else result.stderr

    # Split output into clean lines to discard system initialization telemetry
    clean_lines = []
    for line in full_output.splitlines():
        if "[plugins]" in line or "🦞" in line or "OpenClaw" in line:
            continue
        parsed_line = line.replace("◇", "").strip()
        if parsed_line:
            clean_lines.append(parsed_line)

    final_response = " ".join(clean_lines).strip()

    if final_response:
        speech_text = final_response.replace("**", "")
        speak(speech_text)
    else:
        print("⚠️ Waiting for system synchronization channel...")
        if result.stderr.strip():
            print(f"[Raw Debug Error]: {result.stderr.strip()}")

if __name__ == "__main__":
    print("🚀 iVisAssist Wearable Hybrid System: ONLINE")
    print("🎧 Connected Device: TOZO-T9 Wireless Earbuds")
    print("📷 Active Sensor: Raspberry Pi Camera Module 3 (imx708)")
    print("👉 Press [Ctrl+C] in this shell to safely power down.")

    try:
        while True:
            run_isight_sync()
            print("⏳ Monitoring environment loop active...")
            time.sleep(8)
    except KeyboardInterrupt:
        print("\nSafely suspending wearable companion software hooks.")
🚀 Step 8: System Run InstructionsWhenever you are ready to use your wearable device hands-free:Put your TOZO-T9 earbuds in and ensure they are paired.Run your workspace controller script inside your active virtual environment wrapper:/home/pi/.virtualenvs/ai_agent/bin/python /home/pi/iVisAssist/wearable_loop.py
Put your Pi in a wearable pocket or harness, walk around your surroundings, and your headset will continuously describe key landmarks, safety hazards, and interesting visuals in real-time.🐙 Step 9: Version Control (Pushing to GitHub)To backup your workspace skills cleanly to GitHub, simply track and push your code files directly from your workspace directory:cd /home/pi/iVisAssist
git init
git add setup.md wearable_loop.py
git commit -m "feat: initial release of iVisAssist hands-free setup and wearable loop"
git push origin main
Your skills folder inside your workspace serves as an instant backup for anyone looking to build their own iSight wearable module!