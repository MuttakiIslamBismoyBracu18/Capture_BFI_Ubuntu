# 🧭 BFI Capture Guide using ASUS RT-AC86U + ALFA AWUS036ACM

## 📌 Overview
This guide describes how to capture **Beamforming Feedback Information (BFI)** frames from 802.11ac MU-MIMO transmissions using:
- ASUS RT-AC86U Router
- ALFA AWUS036ACM (MT7612U chipset)
- Surface Laptop (Ubuntu 24.04)

---

## 🧰 Hardware Setup
| Component | Role | Description |
|------------|------|-------------|
| **ASUS RT-AC86U** | Access Point | Enable Explicit Beamforming, MU-MIMO |
| **ALFA AWUS036ACM** | Capture Adapter | Runs in Monitor mode on 5GHz |
| **Surface Laptop Go 3** | Client + Capture Host | Connects to SSID and runs capture |
| **Optional Device** | iperf3 Server | Generates MU-MIMO traffic |

---

## ⚙️ ASUS Router Configuration
1. Go to `http://192.168.50.1` → **Wireless > General > 5GHz**
   - Channel: **149**
   - Bandwidth: **80 MHz**
2. Then go to **Wireless > Professional > 5GHz**
   - ✅ Explicit Beamforming  
   - ✅ MU-MIMO  
   - ✅ Universal Beamforming  
3. Apply settings and restart the router.

---

## 🧠 Linux Configuration Steps

### 1️⃣ Connect to Router (Client)
```bash
nmcli dev disconnect wlp0s20f3
nmcli dev wifi connect "ASUS_BFI_5G" password "WPA2-Personal"
```

### 2️⃣ Set Up ALFA Adapter (Monitor Mode)
```bash
sudo nmcli dev set wlx00c0cab88d1f managed no
sudo ip link set wlx00c0cab88d1f down
sudo iw dev wlx00c0cab88d1f set type monitor
sudo ip link set wlx00c0cab88d1f up
sudo iw wlx00c0cab88d1f set channel 149 80MHz
```

### 3️⃣ Start Capture
```bash
sudo tcpdump -i wlx00c0cab88d1f -s 0 -w ~/captures/bfi_capture.pcapng
```

### 4️⃣ Generate MU-MIMO Traffic
Run on **another device** connected to the same router:
```bash
iperf3 -s
```
Then, from your Surface (client):
```bash
iperf3 -c <SERVER_IP> -R -t 60
```

### 5️⃣ Stop and Verify
Stop tcpdump with `Ctrl+C` and verify:
```bash
tshark -r ~/captures/bfi_capture.pcapng -Y "wlan.vht.compressed_beamforming_report" -T fields -e frame.number | head
```

If you see numbers (e.g., `353`, `356`, `359`), BFI frames were captured successfully.

---

## 🧩 Optional Commands
Count total BFI frames:
```bash
tshark -r ~/captures/bfi_capture.pcapng -Y "wlan.vht.compressed_beamforming_report" | wc -l
```

List all BFI frame numbers:
```bash
tshark -r ~/captures/bfi_capture.pcapng -Y "wlan.vht.compressed_beamforming_report" -T fields -e frame.number
```

Extract SNR values:
```bash
tshark -r ~/captures/bfi_capture.pcapng -Y "wlan.vht.compressed_beamforming_report.snr" -T fields -e wlan.vht.compressed_beamforming_report.snr
```

---

## ✅ Expected Output Example
```
353
356
359
364
367
370
403
406
409
525
```

These represent valid **VHT Beamforming Feedback** frames captured by your ALFA adapter.

---

## 🧾 File Summary
| File | Description |
|------|-------------|
| **capture_bfi_asus.sh** | Bash script for full automation |
| **bfi_capture.md** | Full documentation guide |

---
**Author:** Muttaki I. Bismoy  
**Date:** 20251103_075257
