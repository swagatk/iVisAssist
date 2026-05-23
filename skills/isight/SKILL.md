---
name: isight-vision
description: Captures real-time hardware images using the Raspberry Pi Camera module.
metadata:
  openclaw:
    requires:
      binaries:
        - rpicam-still
---

# Skill: iSight Wearable Camera Eye

Teaches the assistant how to look through the wearable device's lens to scan the environment for the user.

## Tool: capture_scene
Use this tool whenever the user explicitly asks you to look at something, describe what is in front of them, check for physical hazards, read text/signs, or scan their surroundings.

### Execution
```bash
/home/pi/iVisAssist/skills/isight/capture.sh