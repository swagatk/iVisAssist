#!/usr/bin/env bash
# ==============================================================================
# connect_bluetooth_headphone.sh
# Automatically finds, pairs, trusts, connects to TOZO-T9 over SSH, and configures
# both audio output (speaker) and microphone input (Handsfree/HFP/HSP profile).
# ==============================================================================

set -euo pipefail

DEVICE_NAME="${1:-TOZO-T9}"
SCAN_DURATION="${SCAN_DURATION:-10}"

# Ensure XDG_RUNTIME_DIR and DBUS_SESSION_BUS_ADDRESS are set when running via SSH
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] && [ -S "${XDG_RUNTIME_DIR}/bus" ]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
fi

echo "==> Checking Bluetooth service and adapter..."
if command -v rfkill >/dev/null 2>&1; then
    if rfkill list bluetooth | grep -q "Soft blocked: yes"; then
        echo "    Unblocking Bluetooth via rfkill..."
        sudo rfkill unblock bluetooth || rfkill unblock bluetooth || true
    fi
fi

bluetoothctl power on >/dev/null 2>&1 || true
bluetoothctl agent on >/dev/null 2>&1 || true
bluetoothctl default-agent >/dev/null 2>&1 || true

# Helper: Look up MAC address by device name in cached devices
get_mac_address() {
    bluetoothctl devices | grep -i "$DEVICE_NAME" | head -n 1 | awk '{print $2}' || true
}

MAC=$(get_mac_address)

if [ -z "$MAC" ]; then
    echo "==> '$DEVICE_NAME' not found in known devices. Scanning for ${SCAN_DURATION}s..."
    echo "    (Make sure your $DEVICE_NAME earphones are in pairing mode!)"
    bluetoothctl --timeout "$SCAN_DURATION" scan on >/dev/null 2>&1 || true
    MAC=$(get_mac_address)
fi

if [ -z "$MAC" ]; then
    echo "ERROR: Could not find Bluetooth device matching '$DEVICE_NAME'."
    echo "       Ensure the earphones are powered on, in pairing mode, and nearby."
    exit 1
fi

echo "==> Found '$DEVICE_NAME' at MAC address: $MAC"

# Check if already paired; if not, pair
PAIRED=$(bluetoothctl info "$MAC" | grep "Paired: yes" || true)
if [ -z "$PAIRED" ]; then
    echo "==> Pairing with $MAC..."
    bluetoothctl pair "$MAC" || true
fi

echo "==> Trusting $MAC..."
bluetoothctl trust "$MAC" >/dev/null 2>&1 || true

# Connect (with retries in case the device is still settling)
echo "==> Connecting to $MAC..."
CONNECTED=""
for attempt in 1 2 3; do
    if bluetoothctl connect "$MAC"; then
        CONNECTED="yes"
        break
    fi
    echo "    Connection attempt $attempt failed, retrying in 2s..."
    sleep 2
done

if [ -z "$CONNECTED" ]; then
    if ! bluetoothctl info "$MAC" | grep -q "Connected: yes"; then
        echo "ERROR: Failed to connect to $DEVICE_NAME ($MAC)."
        exit 1
    fi
fi

echo "==> Connected! Waiting for audio server (PipeWire / PulseAudio) to register card..."

# Ensure user audio services are running (helpful in headless SSH sessions)
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user start pipewire pipewire-pulse wireplumber 2>/dev/null || \
    systemctl --user start pulseaudio 2>/dev/null || true
fi

# Convert MAC XX:XX:XX:XX:XX:XX to XX_XX_XX_XX_XX_XX for PulseAudio/PipeWire matching
MAC_UNDERSCORE="${MAC//:/_}"
CARD_NAME=""

for _ in $(seq 1 15); do
    CARD_NAME=$(pactl list cards short 2>/dev/null | awk '{print $2}' | grep -i "$MAC_UNDERSCORE" | head -n 1 || true)
    if [ -n "$CARD_NAME" ]; then
        break
    fi
    sleep 1
done

if [ -z "$CARD_NAME" ]; then
    echo "WARNING: Bluetooth connected, but audio card for $MAC was not found via pactl."
    echo "         Check that pipewire-pulse or pulseaudio-module-bluetooth is installed and running."
    exit 1
fi

echo "==> Found audio card: $CARD_NAME"

# To use BOTH audio output and microphone input simultaneously on Bluetooth,
# the card must be switched from A2DP (output-only) to the Headset/Handsfree profile (HFP/HSP).
echo "==> Configuring bidirectional audio profile (Output + Microphone Input)..."
AVAILABLE_PROFILES=$(pactl list cards 2>/dev/null | awk "/Name: $CARD_NAME/,/Active Profile:/" || true)

SELECTED_PROFILE=""
for candidate in \
    "headset-head-unit-msbc" \
    "headset-head-unit" \
    "headset-head-unit-cvsd" \
    "handsfree_head_unit" \
    "headset_head_unit" \
    "hfp_hf" \
    "hsp_hs"; do
    if echo "$AVAILABLE_PROFILES" | grep -q "${candidate}:"; then
        SELECTED_PROFILE="$candidate"
        break
    fi
done

# Fallback: dynamically match any available headset/handsfree profile name
if [ -z "$SELECTED_PROFILE" ]; then
    SELECTED_PROFILE=$(echo "$AVAILABLE_PROFILES" | grep -oE '^\s*(headset|handsfree|hfp|hsp)[^:]+' | head -n 1 | tr -d '[:space:]' || true)
fi

if [ -n "$SELECTED_PROFILE" ]; then
    echo "    Setting card profile to '$SELECTED_PROFILE'..."
    pactl set-card-profile "$CARD_NAME" "$SELECTED_PROFILE"
else
    echo "WARNING: Could not automatically detect an HFP/HSP profile on $CARD_NAME."
    echo "         Available profiles:"
    echo "$AVAILABLE_PROFILES" | grep -E "^\s+[a-zA-Z0-9_-]+:" || true
fi

# Give the audio server a brief moment to spawn the new sink & source nodes
sleep 2

SINK_NAME=$(pactl list sinks short 2>/dev/null | awk '{print $2}' | grep -i "$MAC_UNDERSCORE" | head -n 1 || true)
SOURCE_NAME=$(pactl list sources short 2>/dev/null | awk '{print $2}' | grep -i "$MAC_UNDERSCORE" | grep -v "\.monitor$" | head -n 1 || true)

if [ -n "$SINK_NAME" ]; then
    echo "==> Setting default audio output (sink) to: $SINK_NAME"
    pactl set-default-sink "$SINK_NAME"
    pactl set-sink-mute "$SINK_NAME" 0 || true
else
    echo "WARNING: No output sink found for $MAC."
fi

if [ -n "$SOURCE_NAME" ]; then
    echo "==> Setting default microphone input (source) to: $SOURCE_NAME"
    pactl set-default-source "$SOURCE_NAME"
    pactl set-source-mute "$SOURCE_NAME" 0 || true
else
    echo "WARNING: No microphone input source found for $MAC."
    echo "         (If the card remained in a2dp-sink profile, mic input is disabled by Bluetooth spec.)"
fi

echo ""
echo "=============================================================================="
echo " Setup Complete for $DEVICE_NAME ($MAC)"
echo "   Card Profile : ${SELECTED_PROFILE:-unknown}"
echo "   Default Sink : ${SINK_NAME:-none}"
echo "   Default Mic  : ${SOURCE_NAME:-none}"
echo "=============================================================================="
echo "Quick test commands:"
echo "  Record 5s from mic : parecord -d \"$SOURCE_NAME\" test.wav   (or: arecord -D pulse -d 5 test.wav)"
echo "  Play back audio    : paplay -d \"$SINK_NAME\" test.wav       (or: aplay -D pulse test.wav)"

