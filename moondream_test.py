"""Describe an image using the local Ollama moondream:latest model.

Usage:
    python moondream_test.py [image_path]

Uses only the standard library (Ollama REST API at localhost:11434).
"""

import base64
import json
import sys
import time
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "moondream:latest"


def describe_image(image_path: str, prompt: str = "Describe this image.") -> tuple[str, float]:
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
    }

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - start

    return result["response"].strip(), elapsed


if __name__ == "__main__":
    image_path = sys.argv[1] if len(sys.argv) > 1 else "test.jpg"

    description, elapsed = describe_image(image_path)

    print(f"Image:       {image_path}")
    print(f"Description: {description}")
    print(f"Inference time: {elapsed:.2f} s")
