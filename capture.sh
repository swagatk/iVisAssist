#!/bin/bash

# Pi 4 camera capture profiles (override any value via env vars).
# Profiles: ultra_latency, low_latency, balanced, quality
# Compatibility mode: by default stdout uses legacy JSON keys only:
#   {"status":"success","image_path":"..."}
# Set CAPTURE_EXTENDED_JSON=1 for additional metadata fields.
PROFILE="${PI4_CAPTURE_PROFILE:-balanced}"
IMAGE_PATH="${CAPTURE_IMAGE_PATH:-/home/pi/live_snap.jpg}"
EXTENDED_JSON="${CAPTURE_EXTENDED_JSON:-0}"

case "$PROFILE" in
	ultra_latency)
		DEFAULT_WIDTH=160
		DEFAULT_HEIGHT=120
		DEFAULT_TIMEOUT_MS=140
		;;
	low_latency)
		DEFAULT_WIDTH=320
		DEFAULT_HEIGHT=240
		DEFAULT_TIMEOUT_MS=180
		;;
	quality)
		DEFAULT_WIDTH=640
		DEFAULT_HEIGHT=480
		DEFAULT_TIMEOUT_MS=320
		;;
	*)
		DEFAULT_WIDTH=416
		DEFAULT_HEIGHT=320
		DEFAULT_TIMEOUT_MS=250
		PROFILE="balanced"
		;;
esac

WIDTH="${CAPTURE_WIDTH:-$DEFAULT_WIDTH}"
HEIGHT="${CAPTURE_HEIGHT:-$DEFAULT_HEIGHT}"
TIMEOUT_MS="${CAPTURE_TIMEOUT_MS:-$DEFAULT_TIMEOUT_MS}"

# Remove target first so downstream consumers cannot reuse stale bytes by inode/path cache.
rm -f "$IMAGE_PATH"

CAPTURE_OK=0
if command -v rpicam-still >/dev/null 2>&1; then
	if rpicam-still -t "$TIMEOUT_MS" -o "$IMAGE_PATH" --width "$WIDTH" --height "$HEIGHT" -n >/dev/null 2>&1; then
		CAPTURE_OK=1
	fi
fi

if [[ "$CAPTURE_OK" -eq 0 ]] && command -v raspi-still >/dev/null 2>&1; then
	if raspi-still -t "$TIMEOUT_MS" -o "$IMAGE_PATH" --width "$WIDTH" --height "$HEIGHT" -n >/dev/null 2>&1; then
		CAPTURE_OK=1
	fi
fi

if [[ "$CAPTURE_OK" -eq 0 ]]; then
	echo "{\"status\": \"error\", \"message\": \"capture failed\"}" >&2
	exit 1
fi

if [[ ! -s "$IMAGE_PATH" ]]; then
	echo "{\"status\": \"error\", \"message\": \"empty image\"}" >&2
	exit 1
fi

if [[ "$EXTENDED_JSON" = "1" ]]; then
	echo "{\"status\": \"success\", \"image_path\": \"${IMAGE_PATH}\", \"profile\": \"${PROFILE}\", \"width\": ${WIDTH}, \"height\": ${HEIGHT}, \"timeout_ms\": ${TIMEOUT_MS}}"
else
	echo "{\"status\": \"success\", \"image_path\": \"${IMAGE_PATH}\"}"
fi
