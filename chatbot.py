import speech_recognition as sr
import subprocess
import time
import os
import requests

# Initialize recognizer
recognizer = sr.Recognizer()

def speak(text):
    if not text.strip(): return
    print(f"🎙️ Assistant: {text}")
    # Wake standard bluetooth sink, then use flite
    subprocess.run(["espeak-ng", "-a", "0", "wake"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    subprocess.run(["flite", "-voice", "slt", "-t", text])

def ask_openclaw(user_query):
    print(f"🧠 Sending to OpenClaw: {user_query}")
    start_time = time.time()
    
    cmd = [
        "openclaw", "agent", 
        "--agent", "main", 
        "--session-id", "ivis-voice-session",
        "-m", f"{user_query} (Keep your response to a single, brief sentence.)"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    latency = time.time() - start_time
    print(f"⏱️ Loop Latency (Cloud & Tool): {latency:.2f} seconds")
    
    # Parse OpenClaw output
    if "◇" in result.stdout:
        return result.stdout.split("◇")[-1].strip().replace("**", "")
    return result.stdout.strip().replace("**", "")

def determine_route(query):
    """
    Instantly decides whether to route the request to the cloud (OpenClaw) or local LLM.
    Returns "cloud" if camera/tools/live-data are needed, otherwise "local".
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
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "llama3.2:1b",
            "prompt": f"Answer with absolute brevity, under 10 words if possible.\nUser: {user_query}",
            "stream": False,
            "options": {
                "num_ctx": 512,
                "num_predict": 32
            }
        })
        if response.status_code == 200:
            output_text = response.json().get("response", "").strip()
        else:
            output_text = "Ollama returned an error."
    except Exception as e:
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
                text = recognizer.recognize_google(audio).lower()
                
                print(f"🗣️ Heard: {text}")
                
                # Use phonetic equivalents to make the wake word detection more robust
                wake_words = ["hello pi", "hello pie", "hello bhai", "hello by", "hello bye", "aloe pie"]
                
                if any(ww in text for ww in wake_words):
                    speak("I'm listening.")
                    print("🟢 Wake word detected! Waiting for command...")
                    
                    # Listen for the actual command
                    command_audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                    command_text = recognizer.recognize_google(command_audio)
                    print(f"🗣️ Command: {command_text}")
                    
                    # Routing logic
                    route = determine_route(command_text)
                    if route == "local":
                        response = ask_local(command_text)
                    else:
                        response = ask_openclaw(command_text)
                        
                    speak(response)
                    
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                print(f"⚠️ Speech Recognition service error: {e}")

if __name__ == "__main__":
    print("🚀 iVisAssist Voice Chatbot ONLINE")
    listen_for_wake_word_and_query()