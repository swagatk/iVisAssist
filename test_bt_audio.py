#!/usr/bin/env python3
"""
test_bt_audio.py
Tests Bluetooth earphone microphone input and speaker output over SSH.
Records a short speech clip from the microphone, plays it back to the user,
and asks for confirmation.
"""

from contextlib import contextmanager
import os
import subprocess
import sys
import tempfile
import wave
import pyaudio

RECORD_SECONDS = 5
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1024


@contextmanager
def suppress_alsa_warnings():
    """Suppress verbose ALSA/Jack C-library warnings printed by PortAudio on Raspberry Pi."""
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        old_stderr = os.dup(2)
        sys.stderr.flush()
        os.dup2(devnull, 2)
        os.close(devnull)
        try:
            yield
        finally:
            os.dup2(old_stderr, 2)
            os.close(old_stderr)
    except Exception:
        yield


def ensure_audio_env():
    """Ensure XDG_RUNTIME_DIR and DBUS_SESSION_BUS_ADDRESS are set for SSH sessions."""
    uid = os.getuid()
    runtime_dir = os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    bus_path = f"{runtime_dir}/bus"
    if "DBUS_SESSION_BUS_ADDRESS" not in os.environ and os.path.exists(bus_path):
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus_path}"


def check_pactl_defaults():
    """Print the active PulseAudio / PipeWire default sink and source if available."""
    try:
        info = subprocess.check_output(
            ["pactl", "info"], text=True, stderr=subprocess.DEVNULL
        )
        sink = ""
        source = ""
        for line in info.splitlines():
            if line.startswith("Default Sink:"):
                sink = line.split(":", 1)[1].strip()
            elif line.startswith("Default Source:"):
                source = line.split(":", 1)[1].strip()
        if sink or source:
            print("Active Audio Server Routing:")
            print(f"  Output Speaker (Sink) : {sink or 'Unknown'}")
            print(f"  Microphone (Source)   : {source or 'Unknown'}")
            if "bluez" not in sink.lower() and "bluez" not in source.lower():
                print(
                    "\n[!] Note: Your default audio device does not appear to be a 'bluez' Bluetooth device."
                )
                print(
                    "    If you haven't connected your earphones yet, run: ./connect_bluetooth_headphone.sh"
                )
            print()
    except Exception:
        pass


def select_devices(pa: pyaudio.PyAudio):
    """Find the best input and output device indices (preferring pulse/pipewire/default)."""
    input_idx = None
    output_idx = None

    try:
        input_idx = int(pa.get_default_input_device_info()["index"])
    except Exception:
        pass

    try:
        output_idx = int(pa.get_default_output_device_info()["index"])
    except Exception:
        pass

    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        name = str(info.get("name", "")).lower()
        if name in ("pulse", "pipewire", "default"):
            if info.get("maxInputChannels", 0) > 0:
                input_idx = i
            if info.get("maxOutputChannels", 0) > 0:
                output_idx = i
            if name == "pulse":
                break

    return input_idx, output_idx


def record_audio(pa: pyaudio.PyAudio, input_idx, wav_path: str, duration: int):
    """Record audio from the microphone and save it to a WAV file."""
    dev_info = (
        pa.get_device_info_by_index(input_idx)
        if input_idx is not None
        else pa.get_default_input_device_info()
    )
    sample_rate = int(dev_info.get("defaultSampleRate", 16000))

    # Try opening stream at device's default sample rate, falling back to 16000 Hz or 48000 Hz
    stream = None
    for rate in (sample_rate, 16000, 48000, 44100):
        try:
            stream = pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=rate,
                input=True,
                input_device_index=input_idx,
                frames_per_buffer=CHUNK,
            )
            sample_rate = rate
            break
        except Exception:
            continue

    if stream is None:
        raise RuntimeError(
            "Could not open microphone input stream. Ensure your Bluetooth microphone profile (HFP/HSP) is active."
        )

    print(
        f"\n>>> Recording for {duration} seconds... Speak into your earphone microphone now!"
    )
    frames = []
    total_chunks = int(sample_rate / CHUNK * duration)

    for i in range(total_chunks):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        # Simple progress indicator every second
        elapsed = int((i + 1) * CHUNK / sample_rate)
        sys.stdout.write(f"\r    Recording: {elapsed}/{duration}s ")
        sys.stdout.flush()

    print("\n>>> Finished recording!")
    stream.stop_stream()
    stream.close()

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pa.get_sample_size(FORMAT))
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))


def play_audio(pa: pyaudio.PyAudio, output_idx, wav_path: str):
    """Play the recorded WAV file back through the earphone speaker."""
    print("\n>>> Playing back your recording through the earphones...")
    with wave.open(wav_path, "rb") as wf:
        try:
            stream = pa.open(
                format=pa.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                output_device_index=output_idx,
            )
            data = wf.readframes(CHUNK)
            while data:
                stream.write(data)
                data = wf.readframes(CHUNK)
            stream.stop_stream()
            stream.close()
        except Exception:
            # Fallback to paplay/aplay if direct PortAudio playback rate mismatches
            subprocess.run(["paplay", wav_path], check=False)
    print(">>> Playback finished!")


def main():
    ensure_audio_env()
    print("==========================================================")
    print("         Bluetooth Earphone Audio & Mic Test              ")
    print("==========================================================\n")

    check_pactl_defaults()

    with suppress_alsa_warnings():
        pa = pyaudio.PyAudio()

    try:
        input_idx, output_idx = select_devices(pa)
        if input_idx is None:
            print("ERROR: No microphone input device was detected by PyAudio.")
            print("Run ./connect_bluetooth_headphone.sh first and try again.")
            sys.exit(1)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            wav_path = tmp_wav.name

        try:
            while True:
                input(
                    f"Press [Enter] when you are ready to record {RECORD_SECONDS} seconds of speech (or Ctrl+C to quit)..."
                )
                record_audio(pa, input_idx, wav_path, RECORD_SECONDS)

                input("\nPress [Enter] to play back the recorded audio...")
                play_audio(pa, output_idx, wav_path)

                answer = (
                    input(
                        "\nDid you clearly hear your recorded speech in your earphones? [y/n/r (retry)]: "
                    )
                    .strip()
                    .lower()
                )
                if answer in ("y", "yes"):
                    print(
                        "\nSUCCESS: Your Bluetooth earphone microphone and speaker are working properly!"
                    )
                    break
                elif answer in ("r", "retry"):
                    print("\nRetrying audio test...\n")
                    continue
                else:
                    print("\nTroubleshooting tips:")
                    print(
                        "  1. Run ./connect_bluetooth_headphone.sh to ensure the TOZO-T9 is connected and set to HFP/HSP profile."
                    )
                    print(
                        "  2. Check volume levels with: pactl set-sink-volume @DEFAULT_SINK@ 80%"
                    )
                    print(
                        "  3. Check mic gain with:     pactl set-source-volume @DEFAULT_SOURCE@ 100%"
                    )
                    retry = (
                        input("\nWould you like to try recording again? [y/n]: ")
                        .strip()
                        .lower()
                    )
                    if retry not in ("y", "yes"):
                        sys.exit(1)
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)
    except KeyboardInterrupt:
        print("\nTest cancelled by user.")
    finally:
        with suppress_alsa_warnings():
            pa.terminate()


if __name__ == "__main__":
    main()

