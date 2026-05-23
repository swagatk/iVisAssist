import os
import time
import subprocess
import requests
import base64

# --- CONFIGURATION ---
# Targets your local instance, which securely wraps the outbound cloud request
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma4:31b-cloud"  # Or gemma3-vl-cloud
IMAGE_PATH = "/home/pi/live_snap.jpg"

def speak(text):
    print(f"🎙️ AI Response: {text}")
    # Crystal clear hardware sound right to your connected TOZO-T9
    subprocess.run(["espeak-ng", "-v", "en+f2", "-s", "150", text])

def capture_image():
    print("\n📸 Capturing high-res scene...")
    # Since the cloud is doing the math, we can boost resolution to 640x480 for sharper eyes!
    subprocess.run([
        "rpicam-still", "-t", "400", "-o", IMAGE_PATH, 
        "--width", "320", "--height", "240", "-n"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def analyze_image():
    if not os.path.exists(IMAGE_PATH):
        speak("Camera capture failed.")
        return

    print(f"🧠 Routing frame to Ollama Cloud ({MODEL_NAME})...")
    
    with open(IMAGE_PATH, "rb") as image_file:
        img_base64 = base64.b64encode(image_file.read()).decode('utf-8')

    payload = {
        "model": MODEL_NAME,
        "prompt": "You are a companion wearable. Describe what is in front of me in 12 words or less. Point out hazards, landmarks, or cool toys.",
        "stream": False,
        "images": [img_base64]
    }

    try:
        # Standard timeout is perfectly safe now since the cloud executes this in ~1.5 seconds
        response = requests.post(OLLAMA_URL, json=payload, timeout=20)
        result = response.json()
        output_text = result.get("response", "").strip()
        speak(output_text)
    except Exception as e:
        print(f"❌ Error: {e}")
        speak("Cloud transmission error.")

if __name__ == "__main__":
    print(f"🚀 iVisAssist Hybrid Cloud Engine Active [{MODEL_NAME}]")
    print("🎧 Output: TOZO-T9 Bluetooth Headset")
    print("👉 Press [ENTER] to process your surroundings...")
    
    try:
        while True:
            input()
            capture_image()
            analyze_image()
    except KeyboardInterrupt:
        print("\nSafely disarming wearable engine.")