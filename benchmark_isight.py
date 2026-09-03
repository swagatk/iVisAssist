import sys
import time
import base64
import json
import requests
from pathlib import Path

OLLAMA_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "isight-fast"
DEFAULT_IMAGE = "/home/pi/live_snap.jpg"
PROMPT = "Describe what is directly in front of me concisely."

def encode_image(image_path: str) -> str:
    path = Path(image_path)
    if not path.is_file():
        print(f"❌ Error: File not found at '{image_path}'")
        sys.exit(1)
    with open(path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def run_benchmark(image_path: str, model_name: str = DEFAULT_MODEL):
    print(f"🖼️  Image:  {image_path}")
    print(f"🧠 Model:  {model_name}")
    print(f"💬 Prompt: \"{PROMPT}\"\n")
    print("⏳ Encoding image and sending to Ollama...")

    t0_start = time.perf_counter()
    b64_image = encode_image(image_path)
    t_encoded = time.perf_counter()

    payload = {
        "model": model_name,
        "prompt": PROMPT,
        "images": [b64_image],
        "stream": True,
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, stream=True)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to Ollama. Ensure Ollama is running (`systemctl status ollama`).")
        sys.exit(1)

    t_first_token = None
    full_text = []
    final_stats = {}

    print("\n--- Model Output ---")
    for line in response.iter_lines():
        if not line:
            continue
        chunk = json.loads(line.decode("utf-8"))

        # Mark timestamp on first generated response token
        if "response" in chunk and chunk["response"] and t_first_token is None:
            t_first_token = time.perf_counter()

        token = chunk.get("response", "")
        full_text.append(token)
        sys.stdout.write(token)
        sys.stdout.flush()

        if chunk.get("done", False):
            final_stats = chunk
            break

    t_end = time.perf_counter()
    print("\n--------------------\n")

    # Metrics calculation
    wall_total = t_end - t0_start
    encode_time = t_encoded - t0_start
    ttft = (t_first_token - t_encoded) if t_first_token else 0.0
    decode_time = (t_end - t_first_token) if t_first_token else 0.0

    # Ollama internal timing metrics (nanoseconds to seconds)
    load_duration = final_stats.get("load_duration", 0) / 1e9
    prompt_eval_duration = final_stats.get("prompt_eval_duration", 0) / 1e9
    eval_count = final_stats.get("eval_count", 0)
    eval_duration = final_stats.get("eval_duration", 0) / 1e9
    eval_rate = (eval_count / eval_duration) if eval_duration > 0 else 0.0

    print("📊 Latency & Throughput Benchmark:")
    print(f" • Image Read & B64 Encode : {encode_time * 1000:.1f} ms")
    print(f" • Time to First Token (TTFT): {ttft:.2f} s")
    print(f" • Generation Decode Time  : {decode_time:.2f} s")
    print(f" • Total Turnaround Time   : {wall_total:.2f} s")
    print(f" • Tokens Generated        : {eval_count}")
    print(f" • Generation Throughput   : {eval_rate:.2f} tokens/sec")

    if load_duration > 0.05:
        print(f"\n⚠️ Model cold-load overhead: {load_duration:.2f} s (first run only)")

if __name__ == "__main__":
    target_image = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMAGE
    target_model = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL
    run_benchmark(target_image, target_model)