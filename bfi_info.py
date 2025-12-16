#!/usr/bin/env python3
# Python 3.11.9

import os
import re
import subprocess
import numpy as np
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog
from collections import defaultdict

# ---------------- GUI ----------------
def pick_pcap():
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(
        title="Select BFI .pcapng file",
        filetypes=[("pcapng files", "*.pcapng")]
    )
    return path

# ---------------- Tshark Extraction ----------------
def extract_bfi(pcap):
    cmd = [
        "tshark", "-r", pcap,
        "-Y", "wlan.vht.compressed_beamforming_report",
        "-T", "fields",
        "-e", "frame.time_relative",
        "-e", "wlan.sa",
        "-e", "wlan.da",
        "-e", "wlan.vht.compressed_beamforming_report"
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    rows = []

    for line in res.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        t, sa, da, hexdata = parts
        hexdata = re.sub(r"[^0-9A-Fa-f]", "", hexdata)
        if not hexdata:
            continue
        data = np.frombuffer(bytes.fromhex(hexdata), dtype=np.uint8)
        rows.append((float(t), sa, da, data))

    return rows

# ---------------- Plot Helpers ----------------
def save_plot(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)

# ---------------- Main Analysis ----------------
def main():
    pcap = pick_pcap()
    if not pcap:
        return

    base = os.path.splitext(os.path.basename(pcap))[0]
    outdir = os.path.join(os.getcwd(), base)
    os.makedirs(outdir, exist_ok=True)

    rows = extract_bfi(pcap)
    if not rows:
        print("No BFI frames found.")
        return

    times = np.array([r[0] for r in rows])
    datas = [r[3] for r in rows]

    max_len = max(len(d) for d in datas)
    X = np.zeros((len(datas), max_len))
    for i, d in enumerate(datas):
        X[i, :len(d)] = d

    amp = np.abs(X)
    phase = (X / 255.0) * 2 * np.pi - np.pi

    sub = np.arange(max_len)
    freq_offset = sub - max_len // 2

    # ---------- Plots ----------
    fig = plt.figure()
    plt.plot(sub, amp.mean(axis=0))
    plt.xlabel("Subcarrier Index")
    plt.ylabel("Amplitude")
    save_plot(fig, f"{outdir}/amp_vs_subcarrier.png")

    fig = plt.figure()
    plt.plot(times, amp.mean(axis=1))
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude")
    save_plot(fig, f"{outdir}/amp_vs_time.png")

    fig = plt.figure()
    plt.plot(times, phase.mean(axis=1))
    plt.xlabel("Time (s)")
    plt.ylabel("Phase (rad)")
    save_plot(fig, f"{outdir}/phase_vs_time.png")

    fig = plt.figure()
    plt.plot(sub, phase.mean(axis=0))
    plt.xlabel("Subcarrier Index")
    plt.ylabel("Phase (rad)")
    save_plot(fig, f"{outdir}/phase_vs_subcarrier.png")

    fig = plt.figure()
    plt.imshow(amp, aspect="auto", origin="lower")
    plt.xlabel("Subcarrier")
    plt.ylabel("Packet Index")
    plt.colorbar(label="Amplitude")
    save_plot(fig, f"{outdir}/amp_heatmap.png")

    fig = plt.figure()
    plt.plot(freq_offset, amp.mean(axis=0))
    plt.xlabel("Frequency Offset")
    plt.ylabel("Mean Amplitude")
    save_plot(fig, f"{outdir}/mean_amp_vs_freq_offset.png")

    fig = plt.figure()
    plt.plot(times, np.arange(1, len(times)+1))
    plt.xlabel("Time (s)")
    plt.ylabel("Cumulative BFI Packets")
    save_plot(fig, f"{outdir}/cumulative_bfi.png")

    # ---------- Summary ----------
    tx_count = defaultdict(int)
    rx_count = defaultdict(int)
    per_rx_times = defaultdict(list)

    for t, sa, da, _ in rows:
        tx_count[da] += 1
        rx_count[sa] += 1
        per_rx_times[sa].append(t)

    duration = times.max() - times.min()

    with open(f"{outdir}/Summary.txt", "w") as f:
        f.write("BFI Observation Summary\n")
        f.write(f"File: {pcap}\n")
        f.write(f"Total BFI: {len(rows)}\n\n")

        f.write("List of Tx [AP]:\n")
        for k,v in tx_count.items():
            f.write(f"  {v:5d} {k}\n")

        f.write("\nList of Rx [STA]:\n")
        for k,v in rx_count.items():
            f.write(f"  {v:5d} {k}\n")

        f.write("\nBFI Rate per Rx:\n")
        for sta, ts in per_rx_times.items():
            rate = len(ts)/(max(ts)-min(ts)) if len(ts)>1 else 0
            f.write(f"STA (Rx): {sta} | BFIs: {len(ts)} | Rate: {rate:.2f} Hz\n")

        f.write("\n")
        f.write(f"Duration: {duration:.2f}s\n")
        f.write(f"Overall BFI Rate: {len(rows)/duration:.2f} Hz\n")
        f.write(f"Dimension(NcXNr): {len(tx_count)}X{len(rx_count)}\n")

    print(f"All outputs saved to: {outdir}")

# ---------------- Entry ----------------
if __name__ == "__main__":
    main()
