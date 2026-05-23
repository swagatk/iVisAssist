import base64
import hashlib
import os
import subprocess
import time

import requests
import speech_recognition as sr


# Voice input
recognizer = sr.Recognizer()

# Cloud API config
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
OLLAMA_CLOUD_URL = os.getenv("OLLAMA_CLOUD_URL", "https://ollama.com/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
OLLAMA_SINGLE_MODEL = os.getenv("OLLAMA_SINGLE_MODEL", OLLAMA_MODEL)
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", OLLAMA_SINGLE_MODEL)
OLLAMA_TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", OLLAMA_SINGLE_MODEL or OLLAMA_VISION_MODEL)
VISION_MODEL_HINTS = ("vision", "vl", "llava", "minicpm", "pixtral", "qwen2.5vl", "gemma3")

_CACHED_MODELS = None

# Camera config
IMAGE_PATH = "/home/pi/live_snap.jpg"
IMAGE_WIDTH = 320
IMAGE_HEIGHT = 240


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
	old_mtime = os.path.getmtime(output_path) if os.path.exists(output_path) else None
	if os.path.exists(output_path):
		try:
			os.remove(output_path)
		except OSError:
			pass

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
				new_mtime = os.path.getmtime(output_path)
				if old_mtime is not None and new_mtime <= old_mtime:
					print(f"⚠️ Capture file timestamp did not advance with {cmd[0]}")
					continue
				print(f"📷 Image captured: {output_path} via {cmd[0]}")
				return True
			print(f"⚠️ Capture failed with {cmd[0]}: {result.stderr.strip()}")
		except FileNotFoundError:
			print(f"⚠️ Camera command not found: {cmd[0]}")

	return False


def _cloud_headers():
	return {
		"Authorization": f"Bearer {OLLAMA_API_KEY}",
		"Content-Type": "application/json",
	}


def _list_cloud_models():
	global _CACHED_MODELS
	if _CACHED_MODELS is not None:
		return _CACHED_MODELS

	try:
		tags_url = OLLAMA_CLOUD_URL.replace("/api/chat", "/api/tags")
		response = requests.get(tags_url, headers=_cloud_headers(), timeout=20)
		if response.status_code != 200:
			print(f"⚠️ Could not list cloud models ({response.status_code})")
			_CACHED_MODELS = []
			return _CACHED_MODELS

		data = response.json()
		_CACHED_MODELS = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
		return _CACHED_MODELS
	except requests.RequestException as e:
		print(f"⚠️ Failed to fetch model list: {e}")
		_CACHED_MODELS = []
		return _CACHED_MODELS


def _select_model(include_image):
	# Explicit single-model mode: use the same model for all prompts.
	if OLLAMA_SINGLE_MODEL:
		return OLLAMA_SINGLE_MODEL

	available = _list_cloud_models()
	if not available:
		# Fall back to explicitly configured values if tags call is unavailable.
		if include_image:
			return OLLAMA_VISION_MODEL or OLLAMA_TEXT_MODEL
		return OLLAMA_TEXT_MODEL or OLLAMA_VISION_MODEL

	if include_image:
		if OLLAMA_VISION_MODEL and OLLAMA_VISION_MODEL in available:
			return OLLAMA_VISION_MODEL
		if OLLAMA_MODEL and OLLAMA_MODEL in available:
			return OLLAMA_MODEL

		for name in available:
			if any(h in name.lower() for h in VISION_MODEL_HINTS):
				return name

		# For image prompts, avoid silent fallback to a random text-only model.
		return None

	if OLLAMA_TEXT_MODEL and OLLAMA_TEXT_MODEL in available:
		return OLLAMA_TEXT_MODEL
	if OLLAMA_MODEL and OLLAMA_MODEL in available:
		return OLLAMA_MODEL
	return available[0]


def _build_cloud_payload(user_query, model_name, image_path=None):
	if image_path:
		with open(image_path, "rb") as f:
			raw_image = f.read()
			b64_image = base64.b64encode(raw_image).decode("utf-8")
			img_sha = hashlib.sha1(raw_image).hexdigest()[:12]

		grounded_query = (
			f"{user_query}\n"
			f"Image checksum: {img_sha}.\n"
			"Describe only what is visible in the attached image right now in one brief sentence. "
			"If the image is unclear, say exactly 'image unclear'."
		)

		user_message = {
			"role": "user",
			"content": grounded_query,
			"images": [b64_image],
		}
	else:
		user_message = {
			"role": "user",
			"content": user_query,
		}

	return {
		"model": model_name,
		"messages": [
			{
				"role": "system",
				"content": "You are concise and helpful. Keep replies to one brief sentence.",
			},
			user_message,
		],
		"stream": False,
		"options": {
			"temperature": 0.2,
			"num_predict": 50,
		},
	}


def ask_ollama_cloud(user_query, include_image=False):
	start_time = time.time()
	image_path = None

	if include_image:
		if not capture_image(IMAGE_PATH):
			return "I could not capture an image right now.", 0.0
		image_path = IMAGE_PATH

	if not OLLAMA_API_KEY:
		return "Missing OLLAMA_API_KEY environment variable.", 0.0

	selected_model = _select_model(include_image)
	if not selected_model:
		if include_image:
			return "No vision-capable cloud model found. Set OLLAMA_VISION_MODEL from /api/tags.", 0.0
		return "No cloud model is configured or available.", 0.0

	payload = _build_cloud_payload(user_query, selected_model, image_path=image_path)
	headers = _cloud_headers()
	print(f"☁️ Using model: {selected_model}")

	try:
		response = requests.post(
			OLLAMA_CLOUD_URL,
			headers=headers,
			json=payload,
			timeout=45,
		)

		latency = time.time() - start_time

		if response.status_code != 200:
			print(f"⚠️ Cloud API error {response.status_code}: {response.text}")
			if response.status_code == 401:
				print("⚠️ 401 indicates invalid API key, expired/revoked key, or wrong cloud endpoint.")
			if response.status_code == 404 and "model" in response.text.lower():
				print("⚠️ Requested model is unavailable. Set OLLAMA_TEXT_MODEL/OLLAMA_VISION_MODEL to names from /api/tags.")
			return "Cloud API returned an error.", latency

		data = response.json()
		output_text = data.get("message", {}).get("content", "").strip()

		if not output_text:
			output_text = "I did not get a response from the cloud model."

		return output_text, latency

	except requests.RequestException as e:
		latency = time.time() - start_time
		print(f"⚠️ Network/API exception: {e}")
		return "Cloud API is not reachable right now.", latency


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
				answer, latency = ask_ollama_cloud(command_text, include_image=include_image)
				if include_image:
					print(f"⏱️ Loop Latency (Cloud Vision): {latency:.2f} seconds")
				else:
					print(f"⏱️ Loop Latency (Cloud Text): {latency:.2f} seconds")

				speak(answer)

			except sr.WaitTimeoutError:
				continue
			except sr.UnknownValueError:
				continue
			except sr.RequestError as e:
				print(f"⚠️ Speech Recognition service error: {e}")


if __name__ == "__main__":
	print("🚀 iVisAssist Cloud-Only Voice Chatbot ONLINE")
	print(f"☁️ Endpoint: {OLLAMA_CLOUD_URL}")
	print(f"🤖 Single model: {OLLAMA_SINGLE_MODEL or '<auto>'}")
	print(f"📝 Text model: {OLLAMA_TEXT_MODEL or '<auto>'}")
	print(f"🖼️ Vision model: {OLLAMA_VISION_MODEL or '<auto>'}")
	print(f"🔐 API key loaded: {'yes' if bool(OLLAMA_API_KEY) else 'no'}")
	listen_for_wake_word_and_query()
