#!/bin/bash
# 1. Snap the photo natively via the working Pi stack
IMAGE_PATH="/home/pi/live_snap.jpg"

# Remove target first so downstream consumers cannot reuse stale bytes by inode/path cache.
rm -f "$IMAGE_PATH"
rpicam-still -t 400 -o "$IMAGE_PATH" --width 160 --height 120 -n >/dev/null 2>&1

# 2. Return the fresh file location
echo "{\"status\": \"success\", \"image_path\": \"${IMAGE_PATH}\"}"
