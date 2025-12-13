# BFI Data Capture and Analysis Guide (Netgear Nighthawk R7800 + ALFA AWUS036ACM)

This guide will walk you through every step to **capture Beamforming Feedback Information (BFI)** packets using your **Netgear Nighthawk R7800 router**, **ALFA AWUS036ACM adapter**, and your **Surface laptop running Ubuntu**. It also includes scripts to automate the process and calculate the BFI rate per minute.

---

## 🧩 1. Router Setup (Netgear Nighthawk R7800)

### Step 1 — Access the Router Admin Panel

1. Connect your Surface to the router’s Wi-Fi (e.g., `BFI_Test_5G` - Password `WPA2-Personal`).
2. Open a browser and go to: **[http://192.168.1.1](http://192.168.1.1)**
3. Login using your router admin credentials.

### Step 2 — Configure 5 GHz Settings

Go to:

```
Advanced → Setup → Wireless Settings → Advanced Wireless Settings (5GHz 802.11a/n/ac)
```

Then configure the following:

| Setting                      | Value       |
| ---------------------------- | ----------- |
| Enable Wireless Router Radio | ✅ Checked   |
| CTS/RTS Threshold            | 2347        |
| Preamble Mode                | Automatic   |
| Transmit Power Control       | 100%        |
| Enable Implicit Beamforming  | ✅ Checked   |
| Enable MU-MIMO               | ✅ Checked   |
| Enable HT160                 | ❌ Unchecked |

Click **Apply** to save the settings.

> 💡 These options ensure the router uses **VHT (802.11ac)** mode, allowing BFI frames to be exchanged between your Surface and the router.

---

## ⚙️ 2. Setting up ALFA AWUS036ACM Adapter (Monitor Mode)

### Step 1 — Identify your adapter

```bash
lsusb
```

You should see a line similar to:

```
MediaTek Inc. MT7612U 802.11a/b/g/n/ac Wireless Adapter
```

```
iw dev
```

If you see the similar result, skip to BFI Trigger part
```
phy#3
	Interface wlx00c0cab88d1f
		ifindex 6
		wdev 0x300000001
		addr 00:c0:ca:b8:8d:1f
		type monitor
		channel 149 (5745 MHz), width: 80 MHz, center1: 5775 MHz
		txpower 20.00 dBm
		multicast TXQ:
			qsz-byt	qsz-pkt	flows	drops	marks	overlmt	hashcoltx-bytes	tx-packets
			0	0	0	0	0	0	0	00
phy#0
	Unnamed/non-netdev interface
		wdev 0x8
		addr c8:5e:a9:bf:61:5d
		type P2P-device
	Interface wlp0s20f3
		ifindex 2
		wdev 0x1
		addr c8:5e:a9:bf:61:5c
		ssid BFI_Test_5G
		type managed
		channel 149 (5745 MHz), width: 80 MHz, center1: 5775 MHz
		txpower 22.00 dBm
		multicast TXQ:
			qsz-byt	qsz-pkt	flows	drops	marks	overlmt	hashcoltx-bytes	tx-packets
			0	0	0	0	0	0	0	00
```

### Step 2 — Set the adapter to Monitor Mode

```bash
sudo nmcli dev set wlx00c0cab88d1f managed no
sudo ip link set wlx00c0cab88d1f down
sudo iw dev wlx00c0cab88d1f set type monitor
sudo ip link set wlx00c0cab88d1f up
sudo iw dev wlx00c0cab88d1f set freq 5745 80 5775
```

### Step 3 — Verify configuration

```bash
iw dev wlx00c0cab88d1f info
```

You should see:

```
channel 149 (5745 MHz), width: 80 MHz, center1: 5775 MHz
```

---

## 🌐 3. Creating Traffic to Trigger BFI Frames

BFI frames are generated when the router performs **beamforming sounding** during active data transmission.

### Step 1 — On the Secondary Device (same Wi-Fi)

Run the following command to start an **iPerf3 server**:

```bash
iperf3 -s -p 5202
```

### Step 2 — On your Surface laptop

Run an **iPerf3 client** command to generate continuous traffic:

```bash
iperf3 -c 192.168.1.5 -p 5202 -t 160 -P 4
```

* Replace `192.168.1.5` with the IP address of your secondary device.
* The `-t 160` means 160 seconds of continuous traffic.
* The `-P 4` creates 4 parallel data streams for heavy throughput.

This forces the router to send frequent sounding frames, resulting in multiple BFI frames per minute.

---

## 📡 4. Capturing BFI Data using TCPDUMP

Run this command on your Surface laptop:

```bash
sudo tcpdump -i wlx00c0cab88d1f -s 0 -w ~/captures/bfi_raw_$(date +%Y%m%d_%H%M%S).pcapng
```

* This starts capturing all Wi-Fi traffic for analysis.
* Let it run for 60–160 seconds while the iPerf3 transfer is active.
* The captured file will be stored in `~/captures/`.

### To verify capture success:

```bash
ls ~/captures
```

You should see a file such as:

```
bfi_raw_20251105_150212.pcapng
```
Run this command to know that BFI is actually captured or not?
```
tshark -r ~/captures/bfi_raw_20.pcapng -Y "wlan.vht.compressed_beamforming_report" -T fields -e frame.number | head
```
You'll see results as such the following:
```
2015
2017
9855
15252
15859
15861
16924
19265
22752
34737
```

---

## 📊 5. Counting BFI Frames and Calculating Rate

Use the following bash code snippet to compute the BFI rate:

```bash
FILE=~/captures/bfi_raw_20.pcapng
read START END DURATION <<<$(tshark -r "$FILE" \
  -Y "wlan.vht.compressed_beamforming_report" \
  -T fields -e frame.time_relative \
  | awk 'NR==1{start=$1} {end=$1} END{print start, end, end-start}')

COUNT=$(tshark -r "$FILE" -Y "wlan.vht.compressed_beamforming_report" | wc -l)
RATE=$(echo "$COUNT / $DURATION" | bc -l)
printf "BFI Frames: %d\nDuration: %.2fs\nRate: %.2f per second\n" "$COUNT" "$DURATION" "$RATE"
```

**Output Example:**

```
BFI Frames: 412
Duration: 60.05s
Rate: 6.86 per second
```

---

## 🧮 6. Output Meaning

| Term         | Description                                                        |
| ------------ | ------------------------------------------------------------------ |
| `BFI Frames` | Total number of captured beamforming feedback frames               |
| `Duration`   | Total capture time (seconds)                                       |
| `Rate`       | Average BFI frames per second (multiply by 60 for per-minute rate) |

**Example:**
If `Rate = 6.86/sec`, → `6.86 × 60 ≈ 411.6 BFIs/min`.

---

## 🧰 7. Automations

* **Python Script:** Automates BFI counting from a selected pcapng file.
* **Shell Script:** Automates adapter setup, capture, and BFI computation.

Both files are included below for download.

---

## 🧾 Summary Workflow

| Step | Command             | Description                                            |
| ---- | ------------------- | ------------------------------------------------------ |
| 1    | Configure Router    | Enable implicit BF + MU-MIMO                           |
| 2    | Setup Adapter       | Switch to monitor mode, ch149 80MHz                    |
| 3    | Start iPerf3 Server | On secondary device `iperf3 -s -p 5202`                |
| 4    | Start iPerf3 Client | On Surface `iperf3 -c 192.168.1.5 -p 5202 -t 160 -P 4` |
| 5    | Capture Traffic     | `sudo tcpdump …`                                       |
| 6    | Compute BFI Rate    | Run provided bash or Python script                     |

---

# 📁 Included Files

### 1. `bfi_capture.sh`

Automates adapter setup, capture, and computation.

### 2. `bfi_analyzer.py`

Parses any `.pcapng` file and reports BFI rate per minute.

### 3. `BFI_Data_Capture_Guide.md`

This documentation file — ready for beginners to follow step-by-step.

---

## 🚀 Next Steps

* Keep the router and adapter close for optimal capture.
* Always ensure the Surface’s Wi-Fi is connected to the same SSID being monitored.
* To maximize BFIs, generate high traffic (iperf3, local streaming, large file copies, etc.).
