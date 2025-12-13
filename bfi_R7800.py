#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bfi_R7800.py — Passive BFI Observation Script with GUI Channel/Adapter Selection

Features:
---------
- GUI popup (Tkinter) lets user select:
    - Channel: [36, 40, 44, 48, 149, 153, 157, 161, 165]
    - Adapter: [wlxb01921e7721f, wlx00c0cab88d1f]
- Automatically sets monitor mode, locks to channel frequency
- Captures for fixed duration (default: 60 s)
- Analyzes BFI packets (wlan.vht.compressed_beamforming_report)
- Saves pcapng file in /home/obak-b/captures
- Restores adapter and NetworkManager management cleanly

Usage:
------
python3 bfi_R7800.py
or
sudo python3 bfi_R7800.py

Dependencies:
-------------
sudo apt install tcpdump tshark iw nmcli
"""

import os
import sys
import time
import shutil
import argparse
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# ----------------- Defaults -----------------
DEFAULTS = {
    "CAPTURE_TIME": 60,
    "OUTDIR": "/home/obak-b/captures",
    "TMPDIR": "/tmp",
}

# 5 GHz channel map (channel -> (freq, center1))
CHANNEL_FREQS = {
    36: (5180, 5210),
    40: (5200, 5230),
    44: (5220, 5250),
    48: (5240, 5270),
    149: (5745, 5775),
    153: (5765, 5775),
    157: (5785, 5775),
    161: (5805, 5835),
    165: (5825, 5855),
}

ADAPTERS = ["wlxb01921e7721f", "wlx00c0cab88d1f"]

# ----------------- Helper functions -----------------
def die(msg, code=1):
    print(f"[ERROR] {msg}", file=sys.stderr)
    messagebox.showerror("Error", msg)
    sys.exit(code)

def run(cmd, *, capture=False, soft=False):
    print(f"[RUN] {cmd}")
    res = subprocess.run(cmd, shell=True,
                         capture_output=capture, text=capture)
    if not soft and res.returncode != 0:
        err = (res.stderr or "").strip() if capture else ""
        die(f"Command failed ({res.returncode}): {cmd}\n{err}")
    return (res.stdout.strip() if capture else None)

def ensure_dir(p):
    try:
        os.makedirs(p, exist_ok=True)
    except Exception as e:
        die(f"Cannot create directory '{p}': {e}")

def file_size_ok(path, min_bytes=64):
    try:
        return os.path.getsize(path) >= min_bytes
    except Exception:
        return False

def now_tag():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

# ----------------- Monitor setup/restore -----------------
def set_monitor(iface, freq, center1):
    run(f"sudo nmcli dev set {iface} managed no", soft=True)
    run(f"sudo ip link set {iface} down")
    run(f"sudo iw dev {iface} set type monitor")
    run(f"sudo ip link set {iface} up")
    run(f"sudo iw dev {iface} set freq {freq} 80 {center1}")
    info = run(f"iw dev {iface} info", capture=True, soft=True) or ""
    print(info)
    if "width: 80 MHz" not in info:
        print("[WARN] Monitor interface may not be properly locked to 80 MHz.")

def restore_managed(iface):
    print("[CLEANUP] Restoring interface & NetworkManager...")
    run(f"sudo ip link set {iface} down", soft=True)
    run(f"sudo iw dev {iface} set type managed", soft=True)
    run(f"sudo ip link set {iface} up", soft=True)
    run(f"sudo nmcli dev set {iface} managed yes", soft=True)

# ----------------- Analysis -----------------
def tshark_count_bfi(pcap):
    out = run(f'tshark -r "{pcap}" -Y "wlan.vht.compressed_beamforming_report" | wc -l',
              capture=True, soft=True)
    try:
        return int(out.strip())
    except Exception:
        return 0

def tshark_times_bfi(pcap):
    out = run(
        f'tshark -r "{pcap}" -Y "wlan.vht.compressed_beamforming_report" '
        f'-T fields -e frame.time_relative',
        capture=True, soft=True
    ) or ""
    times = []
    for line in out.splitlines():
        try:
            times.append(float(line.strip()))
        except ValueError:
            continue
    return times

def analyze_bfi(pcap, fallback_duration):
    count = tshark_count_bfi(pcap)
    if count == 0:
        return {"count": 0, "duration": fallback_duration, "rate_s": 0.0}
    times = tshark_times_bfi(pcap)
    if len(times) >= 2:
        duration = max(0.0, times[-1] - times[0])
    else:
        duration = fallback_duration
    rate_s = (count / duration) if duration > 0 else 0.0
    return {"count": count, "duration": duration, "rate_s": rate_s}

# ----------------- GUI -----------------
def ask_user_gui():
    root = tk.Tk()
    root.title("BFI Capture Configuration")
    root.geometry("320x220")
    root.resizable(False, False)

    tk.Label(root, text="Select Channel:", font=("Arial", 11)).pack(pady=8)
    channel_var = tk.StringVar(value="149")
    ch_box = ttk.Combobox(root, textvariable=channel_var, values=list(CHANNEL_FREQS.keys()), state="readonly", width=15)
    ch_box.pack()

    tk.Label(root, text="Select Adapter:", font=("Arial", 11)).pack(pady=8)
    iface_var = tk.StringVar(value=ADAPTERS[0])
    iface_box = ttk.Combobox(root, textvariable=iface_var, values=ADAPTERS, state="readonly", width=25)
    iface_box.pack()

    done = tk.BooleanVar(value=False)
    def submit():
        done.set(True)
        root.destroy()

    tk.Button(root, text="Start Capture", command=submit, width=18, bg="#4CAF50", fg="white").pack(pady=18)
    root.mainloop()

    if not done.get():
        sys.exit(0)
    return int(channel_var.get()), iface_var.get()

# ----------------- Main -----------------
def main():
    # Re-exec with sudo if not root
    if os.geteuid() != 0:
        print("[INFO] Not root; re-executing with sudo...")
        os.execvp("sudo", ["sudo", sys.executable] + sys.argv)

    # Create output dir
    ensure_dir(DEFAULTS["OUTDIR"])
    ensure_dir(DEFAULTS["TMPDIR"])

    # Ask user via GUI
    channel, iface = ask_user_gui()

    if channel in CHANNEL_FREQS:
        freq, center1 = CHANNEL_FREQS[channel]
    else:
        freq, center1 = (channel * 5 + 5000, channel * 5 + 5030)
        print(f"[WARN] Unknown channel {channel}, using generic freq estimate.")

    print(f"[SETUP] Channel {channel} → freq {freq} MHz, center1 {center1} MHz")
    set_monitor(iface, freq, center1)

    tag = now_tag()
    tmp_pcap = os.path.join(DEFAULTS["TMPDIR"], f"bfi_capture_{tag}.pcapng")
    final_pcap = os.path.join(DEFAULTS["OUTDIR"], f"bfi_observe_{channel}_{tag}.pcapng")

    print(f"[CAPTURE] Observing traffic on {iface} for {DEFAULTS['CAPTURE_TIME']}s ...")
    tcp_cmd = [
        "sudo", "tcpdump", "-i", iface, "-s", "0", "-U",
        "-G", str(DEFAULTS["CAPTURE_TIME"]), "-W", "1", "-w", tmp_pcap
    ]
    proc = subprocess.Popen(tcp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=DEFAULTS["CAPTURE_TIME"] + 15)
    except subprocess.TimeoutExpired:
        print("[WARN] tcpdump did not exit; terminating...")
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            pass

    os.sync()
    time.sleep(0.5)
    if not file_size_ok(tmp_pcap):
        restore_managed(iface)
        die(f"No capture written or file too small: {tmp_pcap}")

    shutil.move(tmp_pcap, final_pcap)
    print(f"[CAPTURE] Saved: {final_pcap}")

    print("[ANALYZE] Counting BFI frames ...")
    result = analyze_bfi(final_pcap, fallback_duration=DEFAULTS["CAPTURE_TIME"])

    print("\n=== BFI Observation Summary ===")
    print(f"File:      {final_pcap}")
    print(f"Adapter:   {iface}")
    print(f"Channel:   {channel}")
    print(f"BFI count: {result['count']}")
    print(f"Duration:  {result['duration']:.2f} s")
    print(f"Rate:      {result['rate_s']:.3f} Hz ({result['rate_s']*60:.1f} per min)")

    restore_managed(iface)
    print("[DONE] Passive BFI observation complete.")

# ----------------- Entry -----------------
if __name__ == "__main__":
    main()
