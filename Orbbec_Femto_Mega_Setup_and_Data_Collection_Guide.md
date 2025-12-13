# 📘 Orbbec Femto Mega Setup and Data Collection Guide (Ubuntu 24.04)

This document provides a complete step-by-step guide for setting up, installing, and using the **Orbbec Femto Mega Depth + RGB Camera** on Ubuntu 24.04 LTS in **Host PC Mode**.

---

## 🧩 1. Download Required Software

### 📦 SDK Download
- Download the Orbbec SDK v2.5.5 for **x86_64 (AMD64)** systems:  
  👉 [SDK v2.5.5 (AMD64)](https://github.com/orbbec/OrbbecSDK_v2/releases/download/v2.5.5/OrbbecSDK_v2.5.5_amd64.deb)

### 🔧 Firmware (Optional Update)
- Official Femto Mega firmware releases:  
  👉 [Femto Mega Firmware](https://github.com/orbbec/OrbbecFirmware/releases/tag/Femto-Mega-Firmware)

---

## ⚙️ 2. Install SDK and Drivers

Open your terminal and run the following commands:

```bash
cd ~/Downloads
sudo apt install ./OrbbecSDK_v2.5.5_amd64.deb
```

### Add USB Permissions (if needed)
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

---

## 🔌 3. Connect the Camera

1. Use a **USB 3.0 Type-C cable** (data capable, not power-only).  
2. Plug the camera into your Ubuntu laptop or PC.  
3. Verify the connection:

```bash
lsusb | grep Orbbec
```

✅ Expected Output:
```
Bus 002 Device 002: ID 2bc5:0669 Orbbec 3D Technology International, Inc Orbbec Femto Mega 3D Camera
```

---

## 🖥️ 4. Start the Orbbec Viewer GUI

Launch the viewer tool to verify everything works:

```bash
OrbbecViewer
```

If the GUI doesn’t open, try:

```bash
OrbbecViewer --gui
```

### 🧠 Expected Behavior
A window opens showing three live video feeds:
- **Color (RGB)** stream
- **Depth** stream (colorized depth map)
- **IR (Infrared)** feed

---

## 🎥 5. Start Capturing and Collecting Data (Python SDK)

Install dependencies:

```bash
pip install pyorbbecsdk opencv-python numpy
```

### ✳️ Python Data Capture Script

```python
import orbbecsdk as ob
import cv2
import numpy as np
import os, time

# Output directory
save_dir = "captures"
os.makedirs(save_dir, exist_ok=True)

# Initialize pipeline
pipeline = ob.Pipeline()
config = ob.Config()
config.enable_stream(ob.StreamType.COLOR, 1280, 720, ob.Format.RGB888, 30)
config.enable_stream(ob.StreamType.DEPTH, 640, 576, ob.Format.Z16, 30)

pipeline.start(config)

i = 0
try:
    while i < 100:  # Capture 100 frames
        frames = pipeline.wait_for_frames(100)
        color = np.asanyarray(frames.get_color_frame().get_data())
        depth = np.asanyarray(frames.get_depth_frame().get_data())

        ts = int(time.time() * 1000)
        cv2.imwrite(f"{save_dir}/color_{ts}.png", cv2.cvtColor(color, cv2.COLOR_RGB2BGR))
        np.save(f"{save_dir}/depth_{ts}.npy", depth)

        cv2.imshow("Color", cv2.cvtColor(color, cv2.COLOR_RGB2BGR))
        cv2.imshow("Depth", cv2.applyColorMap(cv2.convertScaleAbs(depth, alpha=0.03), cv2.COLORMAP_JET))

        if cv2.waitKey(1) == 27:  # ESC to exit
            break
        i += 1
finally:
    pipeline.stop()
    cv2.destroyAllWindows()
```

This script records **100 synchronized RGB + Depth pairs** and saves them in a folder called `captures/`.

---

## ♻️ 6. Reusing the Setup (Next Time)

Once the SDK is installed, follow these simple steps whenever you reconnect the camera:

1. Plug in the Femto Mega (USB-C).  
2. Verify detection:
   ```bash
   lsusb | grep Orbbec
   ```
3. Launch the viewer:
   ```bash
   OrbbecViewer
   ```
4. (Optional) Run your Python capture script.

That’s it — no need to reinstall anything!

---

## 🧾 Summary

| Step | Action | Command / Link |
|------|---------|----------------|
| 1 | Download SDK | [SDK v2.5.5 (AMD64)](https://github.com/orbbec/OrbbecSDK_v2/releases/download/v2.5.5/OrbbecSDK_v2.5.5_amd64.deb) |
| 2 | Install SDK | `sudo apt install ./OrbbecSDK_v2.5.5_amd64.deb` |
| 3 | Connect Camera | `lsusb | grep Orbbec` |
| 4 | Launch GUI | `OrbbecViewer` |
| 5 | Capture Data (Python) | `python capture_orbbec_data.py` |
| 6 | Reuse Anytime | Plug → Verify → Run Viewer or Python |

---

**Author:** Muttaki I. Bismoy  
**Device:** Orbbec Femto Mega Depth + RGB Camera  
**Environment:** Ubuntu 24.04 LTS  
**Mode:** Host PC Mode
