import subprocess
import time
import sys
import os

def ensure_skills_linked():
    """Symlink the standalone skills directory into OpenClaw's global workspace so it initializes them cleanly."""
    target = os.path.expanduser("~/.openclaw/workspace/skills/isight")
    source = os.path.abspath(os.path.join(os.path.dirname(__file__), "skills", "isight"))
    
    if not os.path.exists(target):
        print(f"🔗 Linking standalone skill into OpenClaw workspace...")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        try:
            os.symlink(source, target)
        except Exception as e:
            print(f"⚠️ Failed to link standalone skill: {e}")

# Uses the exact underlying execution architecture we verified earlier
def speak(text):
    if not text.strip():
        return
    print(f"🎙️ Broadcasting to TOZO Earbuds: {text}")
    # Direct hardware route to your connected PipeWire bluetooth sink
    subprocess.run(["espeak-ng", "-v", "en+f2", "-s", "150", text])

def run_isight_sync():
    print("\n🔄 Triggering autonomous iSight environment scan...")
    
    # Calls your verified OpenClaw workspace tool configuration cleanly
    cmd = [
        "openclaw", "agent",
        "--agent", "main",
        "--session-id", "isight-wearable-active",
        "-m", "Scan my surroundings using the capture_scene tool and describe it concisely."
    ]
    
    # Capture standard output where OpenClaw prints the agent response text
    result = subprocess.run(cmd, capture_output=True, text=True)
    stdout = result.stdout
    
    # In non-interactive mode, stdout contains just the response.
    # If run in a TTY, it might contain the '◇' token.
    if "◇" in stdout:
        raw_response = stdout.split("◇")[-1].strip()
    else:
        raw_response = stdout.strip()
        
    if raw_response:
        # Strip out markdown bold tags (**) so espeak doesn't read them as punctuation
        cleaned_response = raw_response.replace("**", "")
        speak(cleaned_response)
    else:
        print("⚠️ Waiting for system synchronization channel...")

if __name__ == "__main__":
    ensure_skills_linked()
    print("🚀 iVisAssist Wearable Hybrid System: ONLINE")
    print("🎧 Connected Device: TOZO-T9 Wireless Earbuds")
    print("📷 Active Sensor: Raspberry Pi Camera Module 3 (imx708)")
    print("👉 Press [Ctrl+C] in this shell to safely power down.")
    
    try:
        while True:
            run_isight_sync()
            # Scans your environment automatically every 8 seconds without touching the keyboard
            print("⏳ Monitoring environment loop active...")
            time.sleep(8)
    except KeyboardInterrupt:
        print("\nSafely suspending wearable companion software hooks.")