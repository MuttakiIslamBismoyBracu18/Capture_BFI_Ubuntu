#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_bfi_dims_gui.py

Robust extraction of Nc and Nr from VHT Compressed Beamforming reports
by parsing tshark verbose output (authoritative decoder).

Requirements:
    - tshark installed
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import re
import os
import sys

# ─────────────────────────────────────────────
# GUI: File selection
# ─────────────────────────────────────────────
root = tk.Tk()
root.withdraw()

pcap = filedialog.askopenfilename(
    title="Select a .pcapng capture file",
    filetypes=[("PCAPNG files", "*.pcapng"), ("All files", "*.*")]
)

if not pcap:
    messagebox.showinfo("Cancelled", "No file selected.")
    sys.exit(0)

if not os.path.exists(pcap):
    messagebox.showerror("Error", "File not found.")
    sys.exit(1)

print(f"\n📂 Selected file: {pcap}\n")

# ─────────────────────────────────────────────
# Run tshark (authoritative decoder)
# ─────────────────────────────────────────────
cmd = [
    "tshark",
    "-r", pcap,
    "-Y", "wlan.vht.compressed_beamforming_report",
    "-V"
]

try:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True
    )
except Exception as e:
    print("❌ Failed to run tshark")
    print(e)
    sys.exit(1)

output = proc.stdout.splitlines()

# ─────────────────────────────────────────────
# Parse VHT MIMO Control
# ─────────────────────────────────────────────
report_count = 0
decoded = []

mimo_re = re.compile(r"VHT MIMO Control:\s+0x([0-9a-fA-F]+)")

for line in output:
    match = mimo_re.search(line)
    if not match:
        continue

    report_count += 1
    mimo_val = int(match.group(1), 16)

    # IEEE 802.11ac decoding
    nc_index = mimo_val & 0x7
    nr_index = (mimo_val >> 3) & 0x7

    nc = nc_index + 1
    nr = nr_index + 1

    decoded.append((nc, nr))

    print(
        f"Report {report_count}: "
        f"MIMO_CTRL=0x{mimo_val:06x} → "
        f"Nc={nc}, Nr={nr} ({nr}x{nc})"
    )

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────
print("\n" + "-" * 50)
print(f"Total VHT Beamforming Reports: {report_count}")

if decoded:
    dims = sorted({f"{nr}x{nc}" for nc, nr in decoded})
    print(f"Unique matrix dimensions: {', '.join(dims)}")
else:
    print("No reports decoded.")

print("-" * 50 + "\n")

messagebox.showinfo(
    "Completed",
    f"Processed {report_count} VHT Beamforming reports.\n"
    "Check terminal for decoded Nc/Nr."
)
