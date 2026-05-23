import base64
import json
import os
import subprocess
import time

import requests
import speech_recognition as sr

# Initialize recognizer
recognizer = sr.Recognizer()

# Local and cloud models are both accessed via local Ollama API.
OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://localhost:11434/api/chat")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "llama3.2:1b")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "gemma4:31b-cloud")
CAPTURE_SCRIPT = os.path.join(os.path.dirname(__file__), "capture.sh")

def speak(text):
    if not text.strip(): return
    print(f"🎙️ Assistant: {text}")
    # Wake standard bluetooth sink, then use flite
    subprocess.run(["espeak-ng", "-a", "0", "wake"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    subprocess.run(["flite", "-voice", "slt", "-t", text])

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
    except json.JSONDecodeError:
        pass

    print(f"⚠️ Invalid capture output: {result.stdout.strip()}")
    return None


def is_visual_query(query):
    visual_keywords = [
        "look",
        "see",
        "camera",
        "surrounding",
        "front",
        "what is this",
        "what do you see",
        "image",
        "picture",
        "photo",
        "read this",
        "sign",
    ]
    q = query.lower()
    return any(keyword in q for keyword in visual_keywords)


def ask_cloud(user_query):
    print(f"☁️ Sending to Ollama Cloud Model: {user_query}")
    start_time = time.time()

    messages: list[dict[str, object]] = [
        {
            "role": "system",
            "content": "Keep replies concise and clear. Prefer one brief sentence.",
        }
    ]

    if is_visual_query(user_query):
        image_path = capture_scene_path()
        if not image_path:
            return "I could not capture an image right now."

        with open(image_path, "rb") as image_file:
            image_b64 = base64.b64encode(image_file.read()).decode("utf-8")

        messages.append(
            {
                "role": "user",
                "content": user_query,
                "images": [image_b64],
            }
        )
    else:
        messages.append({"role": "user", "content": user_query})

    payload = {
        "model": CLOUD_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": 64,
            "temperature": 0.2,
        },
    }

    try:
        response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=90)
        latency = time.time() - start_time
        print(f"⏱️ Loop Latency (Cloud Ollama): {latency:.2f} seconds")

        if response.status_code != 200:
            print(f"⚠️ Cloud API error {response.status_code}: {response.text}")
            return "Cloud model returned an error."

        data = response.json()
        return data.get("message", {}).get("content", "").strip() or "No response from cloud model."
    except requests.RequestException as e:
        print(f"⚠️ Cloud request exception: {e}")
        return "Cloud model is not reachable right now."

def determine_route(query):
    """
    Instantly decides whether to route the request to cloud model or local model.
    Returns "cloud" if camera/live-data are likely needed, otherwise "local".
    """
    cloud_keywords = ["look", "see", "camera", "surrounding", "front", "weather", "search", "latest", "what is this"]
    query_lower = query.lower()
    
    if any(keyword in query_lower for keyword in cloud_keywords):
        return "cloud"
    return "local"

def ask_local(user_query):
    print(f"🏠 Sending to Local Ollama: {user_query}")
    start_time = time.time()
    
    try:
        response = requests.post(OLLAMA_CHAT_URL, json={
            "model": LOCAL_MODEL,
            "messages": [
                {"role": "system", "content": "Answer with absolute brevity, under 10 words if possible."},
                {"role": "user", "content": user_query},
            ],
            "stream": False,
            "options": {
                "num_ctx": 512,
                "num_predict": 32
            }
        })
        if response.status_code == 200:
            output_text = response.json().get("message", {}).get("content", "").strip()
        else:
            output_text = "Ollama returned an error."
    except requests.RequestException as e:
        output_text = "Ollama server is not reachable."
        print(f"⚠️ {e}")
        
    latency = time.time() - start_time
    print(f"⏱️ Loop Latency (Local Ollama): {latency:.2f} seconds")
    return output_text

def listen_for_wake_word_and_query():
    with sr.Microphone() as source:
        print("\n🎧 Adjusting for ambient noise...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        
        while True:
            print("⏳ Listening for 'hello pi'...")
            try:
                # Listen continuously
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                text = recognizer.recognize_google(audio).lower()  # type: ignore[attr-defined]
                
                print(f"🗣️ Heard: {text}")
                
                # Use phonetic equivalents to make the wake word detection more robust
                wake_words = ["hello pi", "hello pie", "hello bhai", "hello by", "hello bye", "aloe pie"]
                
                if any(ww in text for ww in wake_words):
                    speak("I'm listening.")
                    print("🟢 Wake word detected! Waiting for command...")
                    
                    # Listen for the actual command
                    command_audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                    command_text = recognizer.recognize_google(command_audio)  # type: ignore[attr-defined]
                    print(f"🗣️ Command: {command_text}")

                    loop_start = time.time()
                    
                    # Routing logic
                    route = determine_route(command_text)
                    if route == "local":
                        response = ask_local(command_text)
                    else:
                        response = ask_cloud(command_text)
                        
                    speak(response)
                    total_latency = time.time() - loop_start
                    if route == "local":
                        print(f"🧮 Total Loop Latency (Local Mode): {total_latency:.2f} seconds")
                    else:
                        print(f"🧮 Total Loop Latency (Cloud Mode): {total_latency:.2f} seconds")
                    
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                print(f"⚠️ Speech Recognition service error: {e}")

if __name__ == "__main__":
    print("🚀 iVisAssist Hybrid Chatbot ONLINE")
    print(f"☁️ Cloud model: {CLOUD_MODEL}")
    print(f"🏠 Local model: {LOCAL_MODEL}")
    listen_for_wake_word_and_query()