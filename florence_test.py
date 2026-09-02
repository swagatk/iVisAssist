import os
import time

import torch
from PIL import Image
from transformers import (
    AutoModelForCausalLM,
    AutoProcessor,
)

model_id = "microsoft/Florence-2-base"

# Load model and processor
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    trust_remote_code=True,
    attn_implementation="eager",
    torch_dtype=torch.float32,
)
processor = AutoProcessor.from_pretrained(
    model_id,
    trust_remote_code=True,
)

# Load your image
image_path = os.path.expanduser("~/test_still.jpg")
if not os.path.isfile(image_path):
    raise FileNotFoundError(f"Image not found: {image_path}")
image = Image.open(image_path).convert("RGB")

# Florence-2 uses task tokens rather than natural-language prompts.
task_prompt = "<MORE_DETAILED_CAPTION>"

inputs = processor(text=task_prompt, images=image, return_tensors="pt")

# Generate output
model.eval()
start_time = time.perf_counter()
with torch.inference_mode():
    generated_ids = model.generate(
        input_ids=inputs["input_ids"],
        pixel_values=inputs["pixel_values"],
        max_new_tokens=256,
        num_beams=3,
    )
response_time = time.perf_counter() - start_time

generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
result = processor.post_process_generation(
    generated_text, 
    task=task_prompt, 
    image_size=(image.width, image.height)
)

print(result)
print(f"Response time: {response_time:.2f} seconds")