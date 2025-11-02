# 📡 How to Capture Beamforming Feedback Information (BFI) using ALFA AWUS036ACM (MT7612U) on Ubuntu

This document provides **end-to-end instructions** for capturing Wi-Fi **Beamforming Feedback Information (BFI)** frames using an **ALFA AWUS036ACM** USB adapter on Ubuntu 24.04 (or similar).

---

## 🧰 Hardware and Setup Overview

| Component | Purpose |
|------------|----------|
| **ASUS RT-AC86U Router** | Acts as the 802.11ac Access Point (AP) with explicit beamforming enabled |
| **Surface Laptop (Intel AX201)** | Connects to the router normally as a client (STA) and generates downlink traffic |
| **ALFA AWUS036ACM (MT7612U)** | Used in **monitor mode** to sniff 802.11ac frames and record BFI reports |
| **Ubuntu 24.04** | Host operating system for capturing and decoding frames |

---

## 🧠 What You’ll Achieve

By the end of this guide, you will:
1. Enable the ALFA adapter and verify monitor-mode capability.
2. Lock it to your router’s 5 GHz channel.
3. Capture 802.11ac (VHT) frames with radiotap headers.
4. Verify that your `.pcapng` file contains **compressed beamforming reports** (BFI).

---

## 1️⃣ Prerequisites

Make sure your router’s 5 GHz radio is **ON** and configured for:
- **Fixed channel:** e.g., Channel 149 (5745 MHz)
- **Channel width:** 80 MHz (VHT80)
- **Explicit Beamforming:** Enabled
- **MU-MIMO:** Enabled

Install required tools on Ubuntu:
```bash
sudo apt update
sudo apt install tcpdump tshark iw net-tools
```

---

## 2️⃣ Plug in the ALFA Adapter

Plug the ALFA AWUS036ACM into a **USB 3.0 port**.

Check detection:
```bash
lsusb | grep MT76
```

**Expected output:**
```
ID 0e8d:7612 MediaTek Inc. MT7612U 802.11a/b/g/n/ac Wireless Adapter
```

---

## 3️⃣ Load the Driver

Ubuntu includes the correct open-source driver (`mt76x2u`).

Load it manually and verify:
```bash
sudo modprobe mt76x2u
lsmod | grep mt76x2u
```

**Expected output (truncated):**
```
mt76x2u                28672  0
mt76x2_common          28672  1 mt76x2u
mt76_usb               40960  1 mt76x2u
mt76                  155648  5 mt76_usb,mt76x2u,mt76x2_common
mac80211             1814528  ...
```

---

## 4️⃣ Confirm Interface Capabilities

Check that monitor mode is supported:
```bash
iw list | grep -A5 "Supported interface modes"
```

**Expected output includes:**
```
* managed
* AP
* AP/VLAN
* monitor
```
Monitor mode ✅ supported.

---

## 5️⃣ Set Up the Environment

### Router connection (STA)
Your **Surface internal Wi-Fi** (`wlp0s20f3`) should be connected to the router SSID:
```bash
iw dev
```

**Expected output:**
```
Interface wlp0s20f3
    type managed
    ssid ASUS_BFI_5G
    channel 149 (5745 MHz), width: 80 MHz
```

---

## 6️⃣ Prepare ALFA Adapter for Monitor Mode

> Interface name may differ (commonly `wlx00c0cab88d1f`).

Bring interface down:
```bash
sudo ip link set wlx00c0cab88d1f down
```

Switch to monitor mode:
```bash
sudo iw dev wlx00c0cab88d1f set type monitor
```

Bring it back up:
```bash
sudo ip link set wlx00c0cab88d1f up
```

Verify:
```bash
iw dev
```

**Expected output snippet:**
```
Interface wlx00c0cab88d1f
    type monitor
    channel 1 (2412 MHz)
```

---

## 7️⃣ Lock the Sniffer to Router Channel

Set to the router’s channel (e.g., Channel 149, 80 MHz width):
```bash
sudo iw wlx00c0cab88d1f set channel 149 80MHz
```

Confirm:
```bash
iw dev wlx00c0cab88d1f info
```

**Expected output:**
```
type monitor
channel 149 (5745 MHz), width: 80 MHz (VHT80)
```

---

## 8️⃣ Start the Capture

> ⚠️ Do **NOT** use `-I` flag with tcpdump; your interface is already in monitor mode.

Start capture:
```bash
sudo tcpdump -i wlx00c0cab88d1f -s 0 -w ~/captures/bfi_acm.pcapng
```

**Expected output:**
```
tcpdump: listening on wlx00c0cab88d1f, link-type IEEE802_11_RADIO (802.11 plus radiotap header)
```

If you see `EN10MB`, it means monitor mode failed — repeat step 6.

---

## 9️⃣ Generate Traffic to Trigger BFI

On your connected device (`wlp0s20f3`), start a heavy **downlink** stream (so the AP sends sounding packets):

Examples:
```bash
# Option 1: stream 4K YouTube or download a large file
# Option 2: iperf3 download test
iperf3 -c <server_ip> -R -t 60
```

Let the capture run for 30–60 seconds.

Stop capture with `Ctrl + C`.

---

## 🔟 Verify Captured BFI Frames

Analyze your capture:
```bash
tshark -r ~/captures/bfi_acm.pcapng -Y "wlan.vht.compressed_beamforming_report" -T fields -e frame.number | head
```

**Expected output (success):**
```
12
13
14
15
...
```

If nothing appears:
- Ensure router is on 5 GHz VHT80.
- Make sure you generated **downlink** traffic.
- Keep ALFA near both AP and STA.

---

## 1️⃣1️⃣ Optional: Return to Managed Mode

After capture, reset the adapter:
```bash
sudo ip link set wlx00c0cab88d1f down
sudo iw dev wlx00c0cab88d1f set type managed
sudo ip link set wlx00c0cab88d1f up
sudo nmcli dev set wlx00c0cab88d1f managed yes
```

---

## ✅ Expected Results Summary

| Stage | Command | Expected Output / Verification |
|--------|----------|-------------------------------|
| Detect adapter | `lsusb | grep MT76` | Shows `MT7612U` |
| Driver loaded | `lsmod | grep mt76x2u` | Lists mt76 modules |
| Monitor supported | `iw list` | Contains `* monitor` |
| Type monitor | `iw dev` | Shows `type monitor` |
| Lock channel | `iw ... set channel 149 80MHz` | Confirms channel 149 |
| Start capture | `tcpdump -i wlx...` | `IEEE802_11_RADIO` appears |
| Verify BFI | `tshark -r ...` | Frame numbers printed |

---

## 🧩 Common Pitfalls

| Issue | Cause | Fix |
|-------|--------|-----|
| `tcpdump: That device doesn't support monitor mode` | Used `-I` flag unnecessarily | Remove `-I` |
| No frames captured | Wrong channel or adapter too far | Match channel 149 VHT80, move closer |
| Still no BFI | Router not sending sounding packets | Enable explicit beamforming & MU-MIMO, stream heavy data |
| `link-type EN10MB` | Adapter not actually in monitor mode | Repeat Step 6 setup |

---

## 📁 Capture File Output

Your valid capture file will be saved at:
```
~/captures/bfi_acm.pcapng
```

You can open it in **Wireshark** and filter:
```
wlan.vht.compressed_beamforming_report
```
Each frame of this type contains BFI matrices, SNR, and channel-state data used by your Python scripts.

---

## 🏁 End of Guide

Once the above setup produces valid BFI frames, you can convert them using your existing MATLAB/Python pipeline:

```bash
python3 pcap_to_bfa.py ~/captures/bfi_acm.pcapng
```

---

**Author:** Muttaki I. Bismoy  
**Device:** ALFA AWUS036ACM (MT7612U)  
**Router:** ASUS RT-AC86U  
**Platform:** Ubuntu 24.04 LTS  
**Purpose:** 802.11ac BFI capture for Wi-Fi sensing research
