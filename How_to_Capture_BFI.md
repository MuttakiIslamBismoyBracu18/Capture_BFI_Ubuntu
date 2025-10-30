
# How to Capture Beamforming Feedback Information (BFI) using TP-Link Archer T2U Plus, ASUS RT-AC86U Router, and Ubuntu on Surface Laptop

---

## 🧩 Overview

This guide provides a **complete step-by-step walkthrough** to set up, connect, and capture **Beamforming Feedback Information (BFI)** using:

- **TP-Link Archer T2U Plus (RTL8821AU chipset)** — Receiver
- **ASUS RT-AC86U Router (802.11ac MU-MIMO)** — Transmitter
- **Surface Laptop (Ubuntu 24.04)** — Capture and analysis system

This guide assumes **no prior experience** with Ubuntu or networking. Every step, command, and troubleshooting method is explained clearly.

---

## 🧠 Prerequisites

- Ubuntu 22.04+ or 24.04 installed on Surface Laptop (any system with at least 8 GB RAM)
- Internet connection (temporarily, via built-in Wi-Fi)
- ASUS RT-AC86U router (factory reset recommended)
- TP-Link Archer T2U Plus USB Adapter (connected to Surface Laptop)
- MATLAB with `pcap_to_bfa.m` (for extraction after capture)

---

## 🧩 Step 1: Connect and Verify the TP-Link Adapter

Plug in the **TP-Link Archer T2U Plus** into a USB port.

### 1. Check if Ubuntu detects the device

```bash
lsusb
```

✅ Expected output (line of interest):
```
Bus 003 Device 006: ID 2357:0120 TP-Link Archer T2U PLUS [RTL8821AU]
```

If you see this, the device is recognized by USB.

If not:
- Try a different USB port.
- Run `dmesg | tail` to see if it’s detected but uninitialized.

---

## 🧩 Step 2: Install Required Packages

Before installing the driver, install development tools:

```bash
sudo apt update
sudo apt install -y dkms git build-essential
```

---

## 🧩 Step 3: Install the TP-Link (RTL8821AU) Driver

Clone and install the open-source driver:

```bash
git clone https://github.com/morrownr/8821au-20210708.git
cd 8821au-20210708
sudo ./install-driver.sh
```

If you see `SecureBoot enabled` in the output, **you must enroll the MOK key** to allow the driver to load.

Run:
```bash
sudo mokutil --import /var/lib/shim-signed/mok/MOK.der
```
Set a password (like `1234`), then reboot:
```bash
sudo reboot
```

When a **blue MOK Manager screen** appears during boot:
1. Select “Enroll MOK”
2. Choose “Continue”
3. Select “Yes”
4. Enter the password you set
5. Reboot

---

## 🧩 Step 4: Verify the Driver is Loaded

After reboot, check:

```bash
lsmod | grep 8821
```

✅ You should see something like:
```
8821au               2789376  0
cfg80211             1433600  4 iwlmvm,8821au,iwlwifi,mac80211
```

Confirm a Wi-Fi interface exists:
```bash
iwconfig
```

Expected:
```
wlxb01921e7721f  IEEE 802.11  ESSID:off/any
```
This is your **TP-Link adapter interface name**.

---

## 🧩 Step 5: Configure the ASUS RT-AC86U Router

### 1. Open the router setup page
In a browser, go to:
```
http://router.asus.com
```
or
```
192.168.50.1
```

If you see only minimal options like:
```
- I want to set this device as AiMesh Node
- Choose operation mode
- Upload settings file
```
→ Click **“Choose Operation Mode”**.

Select:
```
Wireless Router Mode (Default)
```

Click **Next**.

---

### 2. Create a new Wi-Fi network

When prompted:
- **SSID:** `ASUS_BFI_5G`
- **Wireless Security:** WPA2-Personal
- **Password:** `bfiproject123`

Click **Next**, then **Apply**.

Wait ~60 seconds for reboot.

---

### 3. Enable Beamforming and MU-MIMO

After the reboot, reconnect to the router via `http://router.asus.com`.

Navigate to:

```
Advanced Settings → Wireless → Professional tab (5GHz)
```

Enable these options:
| Option | Status |
|---------|---------|
| Explicit Beamforming | ✅ Enable |
| Implicit Beamforming | ✅ Enable |
| MU-MIMO | ✅ Enable |
| TX Beamforming | ✅ Enable |

Click **Apply**.

---

### 4. Set Channel and Bandwidth

Go to **Wireless → General → Band 5GHz**:

| Setting | Value |
|----------|--------|
| Wireless Mode | 802.11ac only |
| Channel bandwidth | 80 MHz |
| Control Channel | 36 |
| Enable Radio | ✅ |

Click **Apply**.

Your router is now broadcasting a 5 GHz 802.11ac MU-MIMO beamforming network.

---

## 🧩 Step 6: Connect the TP-Link Adapter to the ASUS Router

Disconnect your internal Wi-Fi card (optional, to avoid confusion):

```bash
sudo nmcli device disconnect wlp0s20f3
```

Scan for networks using the TP-Link interface:

```bash
sudo nmcli device wifi list ifname wlxb01921e7721f
```

Connect to your ASUS router:

```bash
sudo nmcli device wifi connect "ASUS_BFI_5G" password "bfiproject123" ifname wlxb01921e7721f
```

Verify connection:

```bash
nmcli device
```

Expected output:
```
wlxb01921e7721f  wifi  connected  ASUS_BFI_5G
```

And check signal quality:

```bash
iwconfig wlxb01921e7721f
```

✅ You should see:
```
Mode:Managed  Frequency:5.18 GHz  ESSID:"ASUS_BFI_5G"
Bit Rate=866.7 Mb/s  Link Quality=65/70
```

The adapter’s LED should now blink continuously — confirming active link.

---

## 🧩 Step 7: Generate Traffic for Beamforming Feedback

Beamforming occurs only during **active data transfer**.  
Use `ping` or `iperf3` to force traffic.

### Option A: Simple ping test

```bash
ping -i 0.1 192.168.50.1
```

### Option B: Continuous traffic with iperf3

Install:
```bash
sudo apt install iperf3
```

If another device on the network can act as a server (Windows/Linux), run there:
```bash
iperf3 -s
```

Then from your Ubuntu laptop:
```bash
iperf3 -c 192.168.50.1 -t 120
```

This pushes high throughput traffic for 120 seconds.

---

## 🧩 Step 8: Switch the TP-Link Adapter to Monitor Mode

To capture raw Wi-Fi frames:

```bash
sudo ip link set wlxb01921e7721f down
sudo iw dev wlxb01921e7721f set type monitor
sudo ip link set wlxb01921e7721f up
```

Check mode:
```bash
iwconfig
```
Should show:
```
Mode:Monitor
```

---

## 🧩 Step 9: Capture Wi-Fi Packets Containing BFI

Use `tcpdump` or `airodump-ng` to capture all over-the-air 802.11ac frames.

### Using tcpdump

```bash
sudo tcpdump -i wlxb01921e7721f -w bfi_capture.pcapng
```

Let it run for 1–2 minutes while traffic (ping or iperf3) continues.

Stop with **Ctrl + C**.

✅ Output message:
```
14600 packets captured
0 packets dropped by kernel
```

The file `bfi_capture.pcapng` is saved in your **home directory**:
```
/home/yourusername/bfi_capture.pcapng
```

Verify:
```bash
ls -lh ~/bfi_capture.pcapng
```

---

## 🧩 Step 10: Verify Capture with Wireshark

Install Wireshark:
```bash
sudo apt install wireshark
```

Open the capture file:
```bash
wireshark ~/bfi_capture.pcapng &
```

### Apply Filter

In the top “Display Filter” bar, type:
```
wlan.vht
```
Press **Enter**.

This filters packets to only show **802.11ac (VHT)** frames.

### Inspect Packets

Click any packet → expand the tree:
```
IEEE 802.11 → IEEE 802.11ac VHT information
```

Look for these fields:
- **VHT MCS**
- **VHT NSS**
- **VHT Beamforming Report**
- **Compressed Beamforming Feedback**
- **Channel Sounding**

✅ If any appear — your capture **contains BFI data**.

---

## 🧩 Step 11: Extract BFI Matrices in MATLAB

Transfer `bfi_capture.pcapng` to your Windows MATLAB environment (if needed).

Run in MATLAB:

```matlab
BFI = pcap_to_bfa('bfi_capture.pcapng');
```

MATLAB will generate the following directories:

```
/beam_angles/
/exclusive_bf_reports/
/vtilde_matrices/
```

These contain per-frame BFI matrices ready for further processing or ML training.

---

## 🧩 Step 12: Troubleshooting

| Problem | Possible Cause | Fix |
|----------|----------------|-----|
| `lsmod | grep 8821` shows nothing | Driver not loaded | Reinstall driver, enroll MOK key |
| TP-Link LED doesn’t blink | Not associated with AP | Check SSID/password, ensure router 5GHz enabled |
| No `wlan.vht` frames in Wireshark | Router not in 802.11ac mode | Recheck router settings: 80 MHz, 5GHz, beamforming enabled |
| `tcpdump` captures 0 packets | Adapter not in monitor mode | Re-run `iw dev ... set type monitor` |
| `pcap_to_bfa` errors in MATLAB | Missing VHT feedback frames | Ensure high data transfer during capture (use `iperf3`) |

---

## 🧩 Step 13: (Optional) Automate with Script

Create a bash script `capture_bfi.sh`:

```bash
#!/bin/bash
echo "[1/4] Switching to monitor mode..."
sudo ip link set wlxb01921e7721f down
sudo iw dev wlxb01921e7721f set type monitor
sudo ip link set wlxb01921e7721f up

echo "[2/4] Starting capture..."
sudo tcpdump -i wlxb01921e7721f -w ~/bfi_capture.pcapng &
CAP_PID=$!

echo "[3/4] Generating traffic..."
ping -i 0.1 192.168.50.1 > /dev/null &
PING_PID=$!

sleep 120

echo "[4/4] Stopping capture..."
sudo kill $CAP_PID
sudo kill $PING_PID
echo "Capture complete → saved as ~/bfi_capture.pcapng"
```

Make executable and run:
```bash
chmod +x capture_bfi.sh
./capture_bfi.sh
```

## How to use

```bash
# make executable (if needed)
chmod +x capture_bfi.sh

# simplest (with your defaults)
sudo ./capture_bfi.sh --ssid "ASUS_BFI_5G" --password "bfiproject123" --router 192.168.50.1

# more control
sudo ./capture_bfi.sh \
  --iface wlxb01921e7721f \
  --ssid "ASUS_BFI_5G" \
  --password "bfiproject123" \
  --router 192.168.50.1 \
  --channel 149 \
  --width 80 \
  --duration 120 \
  --outfile ~/bfi_capture.pcapng
```

---

## ✅ Final Recap

| Stage | Goal | Verification |
|--------|------|--------------|
| TP-Link detected | `lsusb` shows 2357:0120 | ✅ |
| Driver loaded | `lsmod | grep 8821` | ✅ |
| Router setup | 5GHz, 80MHz, Beamforming ON | ✅ |
| Adapter connected | `nmcli device` → connected | ✅ |
| Monitor mode | `iwconfig` → Mode:Monitor | ✅ |
| Capture running | `.pcapng` growing in size | ✅ |
| Wireshark verification | `wlan.vht` frames visible | ✅ |
| MATLAB extraction | Outputs BFI matrices | ✅ |

---

## 🧠 Notes

- The **ASUS RT-AC86U** must remain in **Wireless Router Mode** for beamforming to occur.
- The **TP-Link Archer T2U Plus (RTL8821AU)** must use the **morrownr/8821au driver** for stable monitor mode.
- Beamforming feedback is only generated during **downlink activity** (AP → Client), so always run ping or iperf3 during capture.

---

## 📚 References

- [morrownr/8821au-20210708 Driver](https://github.com/morrownr/8821au-20210708)
- [ASUS RT-AC86U Manual](https://www.asus.com/support/)
- [Wireshark WLAN VHT Filter](https://wiki.wireshark.org/IEEE_802.11)
- [MATLAB WLAN Toolbox Documentation](https://www.mathworks.com/help/wlan/)

---

✅ **End of Guide — You have successfully captured BFI using TP-Link Archer T2U Plus and ASUS RT-AC86U on Ubuntu.**

---

