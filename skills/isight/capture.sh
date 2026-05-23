#!/bin/bash
# 1. Snap the photo natively via the working Pi stack
rpicam-still -t 400 -o /home/pi/live_snap.jpg --width 320 --height 240 -n >/dev/null 2>&1

# 2. Tell OpenClaw where the fresh file is located
echo '{"status": "success", "image_path": "/home/pi/live_snap.jpg"}'