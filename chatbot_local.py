import base64
import os
import subprocess
import time

import requests
import speech_recognition as sr


# Voice input
recognizer = sr.Recognizer()

# Local Ollama config
# Single local server and single model for all queries.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "moondream:latest")
TEXT_TIMEOUT_SEC = int(os.getenv("TEXT_TIMEOUT_SEC", "120"))
VISION_TIMEOUT_SEC = int(os.getenv("VISION_TIMEOUT_SEC", "120"))

# Camera config
IMAGE_PATH = "/home/pi/live_snap.jpg"
IMAGE_WIDTH = 160
IMAGE_HEIGHT = 120


def speak(text):
	if not text.strip():
		return
	print(f"🎙️ Assistant: {text}")

	# Wake bluetooth sink to reduce clipped first syllable.
	subprocess.run(
		["espeak-ng", "-a", "0", "wake"],
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL,
		check=False,
	)
	time.sleep(0.8)
	subprocess.run(["flite", "-voice", "slt", "-t", text], check=False)


def is_image_query(query):
	image_keywords = [
		"look",
		"see",
		"camera",
		"surroundings",
		"surrounding",
		"front",
		"what is this",
		"what do you see",
		"read this",
		"sign",
		"photo",
		"picture",
		"image",
	]
	query_lower = query.lower()
	return any(keyword in query_lower for keyword in image_keywords)


def capture_image(output_path):
	"""Capture one frame using raspi-still; fallback to rpicam-still if needed."""
	commands = [
		[
			"raspi-still",
			"-t",
			"400",
			"-o",
			output_path,
			"--width",
			str(IMAGE_WIDTH),
			"--height",
			str(IMAGE_HEIGHT),
			"-n",
		],
		[
			"rpicam-still",
			"-t",
			"400",
			"-o",
			output_path,
			"--width",
			str(IMAGE_WIDTH),
			"--height",
			str(IMAGE_HEIGHT),
			"-n",
		],
	]

	for cmd in commands:
		try:
			result = subprocess.run(cmd, capture_output=True, text=True, check=False)
			if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
				print(f"📷 Image captured: {output_path} via {cmd[0]}")
				return True
			print(f"⚠️ Capture failed with {cmd[0]}: {result.stderr.strip()}")
		except FileNotFoundError:
			print(f"⚠️ Camera command not found: {cmd[0]}")

	return False


def ask_local_text(user_query):
	payload = {
		"model": OLLAMA_MODEL,
		"messages": [
			{"role": "system", "content": "Keep replies to one brief sentence."},
			{"role": "user", "content": user_query},
		],
		"stream": False,
		"options": {
			"num_ctx": 512,
			"num_predict": 48,
			"temperature": 0.2,
		},
	}

	response = requests.post(OLLAMA_URL, json=payload, timeout=TEXT_TIMEOUT_SEC)
	if response.status_code != 200:
		print(f"⚠️ Text API error {response.status_code}: {response.text}")
		return "Local text model returned an error."

	data = response.json()
	text = data.get("message", {}).get("content", "").strip()
	return text or "I did not get a response from the local text model."


def ask_local_vision(user_query):
	if not capture_image(IMAGE_PATH):
		return "I could not capture an image right now."

	with open(IMAGE_PATH, "rb") as f:
		b64_image = base64.b64encode(f.read()).decode("utf-8")

	payload = {
		"model": OLLAMA_MODEL,
		"messages": [
			{
				"role": "system",
				"content": "Describe only what is visible in the image in one brief sentence.",
			},
			{
				"role": "user",
				"content": user_query,
				"images": [b64_image],
			},
		],
		"stream": False,
		"options": {
			"num_predict": 64,
			"temperature": 0.2,
		},
	}

	response = requests.post(OLLAMA_URL, json=payload, timeout=VISION_TIMEOUT_SEC)
	if response.status_code != 200:
		print(f"⚠️ Vision API error {response.status_code}: {response.text}")
		return "Local vision model returned an error."

	data = response.json()
	text = data.get("message", {}).get("content", "").strip()
	return text or "I did not get a response from the local vision model."


def ask_local(user_query, include_image=False):
	start_time = time.time()
	try:
		if include_image:
			answer = ask_local_vision(user_query)
		else:
			answer = ask_local_text(user_query)
		latency = time.time() - start_time
		return answer, latency
	except requests.RequestException as e:
		latency = time.time() - start_time
		print(f"⚠️ Local API exception: {e}")
		if "Read timed out" in str(e):
			return "Local model timed out. Try again, or increase TEXT_TIMEOUT_SEC/VISION_TIMEOUT_SEC.", latency
		return "Local Ollama server is not reachable right now.", latency


def warmup_model():
	"""Warm model into memory to reduce first user-query timeout risk."""
	payload = {
		"model": OLLAMA_MODEL,
		"messages": [{"role": "user", "content": "Reply with one word: ready"}],
		"stream": False,
		"options": {
			"num_predict": 2,
			"temperature": 0,
		},
	}

	try:
		print("🔥 Warming up local model...")
		requests.post(OLLAMA_URL, json=payload, timeout=TEXT_TIMEOUT_SEC)
		print("✅ Warmup completed.")
	except requests.RequestException as e:
		print(f"⚠️ Warmup skipped: {e}")


def listen_for_wake_word_and_query():
	with sr.Microphone() as source:
		print("\n🎧 Adjusting for ambient noise...")
		recognizer.adjust_for_ambient_noise(source, duration=1)

		while True:
			print("⏳ Listening for 'hello pi'...")
			try:
				audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
				text = recognizer.recognize_google(audio).lower()  # type: ignore[attr-defined]
				print(f"🗣️ Heard: {text}")

				wake_words = ["hello pi", "hello pie", "hello bhai", "hello by", "hello bye", "aloe pie"]
				if not any(ww in text for ww in wake_words):
					continue

				speak("I'm listening.")
				print("🟢 Wake word detected! Waiting for command...")

				command_audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
				command_text = recognizer.recognize_google(command_audio)  # type: ignore[attr-defined]
				print(f"🗣️ Command: {command_text}")

				include_image = is_image_query(command_text)
				answer, latency = ask_local(command_text, include_image=include_image)
				if include_image:
					print(f"⏱️ Loop Latency (Local Vision): {latency:.2f} seconds")
				else:
					print(f"⏱️ Loop Latency (Local Text): {latency:.2f} seconds")

				speak(answer)

			except sr.WaitTimeoutError:
				continue
			except sr.UnknownValueError:
				continue
			except sr.RequestError as e:
				print(f"⚠️ Speech Recognition service error: {e}")


if __name__ == "__main__":
	print("🚀 iVisAssist Local-Only Voice Chatbot ONLINE")
	print(f"🤖 Model: {OLLAMA_MODEL}")
	print(f"🏠 Endpoint: {OLLAMA_URL}")
	print(f"⏱️ Text timeout: {TEXT_TIMEOUT_SEC}s, Vision timeout: {VISION_TIMEOUT_SEC}s")
	warmup_model()
	listen_for_wake_word_and_query()
