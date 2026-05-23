import base64
import json
import os
import subprocess
import time

import requests


# Direct vision config
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")
LOOP_INTERVAL_SEC = int(os.getenv("LOOP_INTERVAL_SEC", "8"))
CAPTURE_SCRIPT = os.path.join(os.path.dirname(__file__), "capture.sh")


def speak(text):
    if not text.strip():
        return
    print(f"🎙️ Broadcasting: {text}")
    subprocess.run(
        ["espeak-ng", "-a", "0", "wake"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    time.sleep(0.8)
    subprocess.run(["flite", "-voice", "slt", "-t", text], check=False)


def capture_scene_path():
    result = subprocess.run([CAPTURE_SCRIPT], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"⚠️ Capture script failed: {result.stderr.strip()}")
        return None

    try:
        payload = json.loads(result.stdout.strip())
        image_path = payload.get("image_path")
        if image_path and os.path.exists(image_path):
            return image_path
        print(f"⚠️ Capture output missing valid image path: {result.stdout.strip()}")
        return None
    except json.JSONDecodeError:
        print(f"⚠️ Invalid JSON from capture script: {result.stdout.strip()}")
        return None


def run_direct_vision_sync():
    print("\n🔄 Triggering environment scan...")
    start_time = time.time()

    image_path = capture_scene_path()
    if not image_path:
        print("⚠️ Failed to capture a fresh image.")
        return

    with open(image_path, "rb") as image_file:
        image_b64 = base64.b64encode(image_file.read()).decode("utf-8")

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
            "num_predict": 48,
            "temperature": 0.1,
        },
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=90)
    except requests.RequestException as e:
        print(f"⚠️ Request failed: {e}")
        return

    latency = time.time() - start_time
    print(f"⏱️ Loop Latency (Direct Vision): {latency:.2f} seconds")

    if response.status_code != 200:
        print(f"⚠️ API error {response.status_code}: {response.text}")
        return

    data = response.json()
    output_text = data.get("message", {}).get("content", "").strip()
    if not output_text:
        print("⚠️ Empty vision response.")
        return

    speak(output_text.replace("**", ""))

if __name__ == "__main__":
    print("🚀 iVisAssist Direct Vision Loop ONLINE")
    print(f"🤖 Model: {OLLAMA_MODEL}")
    print(f"🏠 Endpoint: {OLLAMA_URL}")
    print("👉 Press [Ctrl+C] to stop.")

    try:
        while True:
            run_direct_vision_sync()
            print("⏳ Monitoring environment loop active...")
            time.sleep(LOOP_INTERVAL_SEC)
    except KeyboardInterrupt:
        print("\nSafely suspending wearable loop.")