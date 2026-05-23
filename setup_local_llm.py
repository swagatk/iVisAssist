import os
import requests

MODEL_URL = "https://huggingface.co/unsloth/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf?download=true"
MODEL_DIR = "/home/pi/iVisAssist/models"
MODEL_PATH = os.path.join(MODEL_DIR, "Llama-3.2-1B-Instruct-Q4_K_M.gguf")

def download_model():
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        
    if os.path.exists(MODEL_PATH):
        print("✅ Local LLM model already exists. You are good to go!")
        return

    print("📥 Downloading Llama-3.2-1B-Instruct (This may take a few minutes depending on your internet connection...)")
    response = requests.get(MODEL_URL, stream=True)
    response.raise_for_status()
    
    with open(MODEL_PATH, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            
    print(f"🎉 Model downloaded successfully to {MODEL_PATH}")

if __name__ == "__main__":
    download_model()