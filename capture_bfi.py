#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Automated BFI Capture Script (ASUS RT-AC86U + ALFA AWUS036ACM)
-----------------------------------------------------------------------
This script automates the full BFI capture workflow:

1. Ensures STA connects to AP (5 GHz, VHT80)
2. Enables monitor mode on ALFA adapter
3. Locks sniffer channel to AP's 5 GHz channel (e.g., 149 @ 80MHz)
4. Starts tcpdump capture for fixed duration
5. Generates downlink MU-MIMO traffic (iperf3 reverse mode)
6. Verifies presence of BFI frames
7. Restores interfaces

Requires: tcpdump, tshark, iw, ip, nmcli, iperf3
Run with: sudo -E python3 capture_bfi.py
"""

import os
import subprocess
import time
from datetime import datetime

# -------- CONFIGURATION --------
IF_MON = "wlx00c0cab88d1f"           # ALFA AWUS036ACM
IF_STA = "wlp0s20f3"                 # Surface laptop internal Wi-Fi
SSID = "ASUS_BFI_5G"                 # Router SSID
PASSWORD = "WPA2-Personal"           # Router password
CHANNEL = 149                        # Router channel (5 GHz)
BANDWIDTH = "80MHz"                  # 20/40/80
CAPTURE_TIME = 60                    # seconds
CAPTURE_BASE = "/home/obak-b/Documents/GitHub/Capture_BFI_Ubuntu/Captures"
IPERF_SERVER = "192.168.50.150"      # Replace with your iperf3 server IP
# --------------------------------

def run(cmd, check=True, capture_output=False):
    print(f"$ {cmd}")
    return subprocess.run(cmd, shell=True, text=True, check=check,
                          capture_output=capture_output)

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cap_dir = os.path.join(CAPTURE_BASE, timestamp)
    ensure_dir(cap_dir)
    pcap_path = os.path.join(cap_dir, f"bfi_{timestamp}.pcapng")

    print("\n=== STEP 1: Connect STA to Router ===")
    try:
        run(f"nmcli dev disconnect {IF_STA}")
        run(f"nmcli dev wifi connect '{SSID}' password '{PASSWORD}'")
    except subprocess.CalledProcessError:
        print("⚠️  Could not (re)connect STA to Wi-Fi — ensure SSID and password are correct.")

    print("\n=== STEP 2: Prepare ALFA in Monitor Mode ===")
    run(f"nmcli dev set {IF_MON} managed no || true")
    run(f"ip link set {IF_MON} down")
    run(f"iw dev {IF_MON} set type monitor")
    run(f"ip link set {IF_MON} up")
    run(f"iw {IF_MON} set channel {CHANNEL} {BANDWIDTH}")

    print("\n=== STEP 3: Start tcpdump capture for "
          f"{CAPTURE_TIME} seconds ===")
    tcpdump_cmd = f"tcpdump -i {IF_MON} -s 0 -U -w {pcap_path}"
    proc = subprocess.Popen(f"sudo {tcpdump_cmd}", shell=True)
    time.sleep(3)

    print("\n=== STEP 4: Start iperf3 Reverse Traffic (Router → STA) ===")
    print(f"Connecting to iperf3 server at {IPERF_SERVER} ...")
    try:
        run(f"iperf3 -c {IPERF_SERVER} -R -t {CAPTURE_TIME}")
    except subprocess.CalledProcessError:
        print("⚠️ iperf3 traffic generation failed — verify server is reachable.")

    print("\n=== STEP 5: Stop Capture ===")
    proc.terminate()
    time.sleep(2)
    print(f"Capture complete → {pcap_path}")

    print("\n=== STEP 6: Verify BFI Frames ===")
    tshark_cmd = (
        f"tshark -r {pcap_path} "
        f"-Y 'wlan.vht.compressed_beamforming_report' "
        f"-T fields -e frame.number | head"
    )
    result = run(tshark_cmd, capture_output=True)
    if result.stdout.strip():
        print("✅ BFI frames found!\n")
        print(result.stdout)
    else:
        print("⚠️ No BFI frames detected.\n"
              "   → Ensure: Router=VHT80 + Explicit Beamforming + MU-MIMO\n"
              "   → STA actively downloading (iperf3 -R)\n"
              "   → ALFA tuned to same 5GHz channel.\n")

    print("\n=== STEP 7: Restore Interfaces ===")
    run(f"ip link set {IF_MON} down")
    run(f"iw dev {IF_MON} set type managed")
    run(f"ip link set {IF_MON} up")
    run(f"nmcli dev set {IF_MON} managed yes")
    print("\n✅ Done. File saved at:", pcap_path)
    print("You can open it in Wireshark or process it with pcap_to_bfa.py")

if __name__ == "__main__":
    main()
