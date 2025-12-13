#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract Nc, Nr, and count the number of VHT Compressed Beamforming Reports
from a selected .pcapng file.

Requirements:
    pip install pyshark
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import pyshark
import os

# ---- GUI: file selection ----
root = tk.Tk()
root.withdraw()  # Hide the main window

file_path = filedialog.askopenfilename(
    title="Select a .pcapng capture file",
    filetypes=[("PCAPNG files", "*.pcapng"), ("All files", "*.*")]
)

if not file_path:
    messagebox.showinfo("Cancelled", "No file selected.")
    exit()

# ---- Analyze the selected file ----
print(f"\n📂 Selected file: {file_path}\n")
if not os.path.exists(file_path):
    print("File not found!")
    exit(1)

cap = pyshark.FileCapture(file_path, display_filter="wlan.vht.compressed_beamforming_report")

count = 0
found_reports = []

try:
    for pkt in cap:
        count += 1
        text = pkt._packet_string

        if "Nc:" in text and "Nr:" in text:
            nc = text.split("Nc:")[1].split()[0]
            nr = text.split("Nr:")[1].split()[0]
            found_reports.append((nc, nr))
            print(f"Report {count}: Nc={nc}, Nr={nr}")
        else:
            print(f"Report {count}: Nc/Nr not decoded")

except Exception as e:
    print(f"Error while parsing: {e}")

cap.close()

print("\n--------------------------------------")
print(f"Total reports found: {count}")
if found_reports:
    unique_dims = {f'{nr}x{nc}' for nc, nr in found_reports}
    print(f"Unique matrix dimensions: {', '.join(unique_dims)}")
print("--------------------------------------\n")

messagebox.showinfo("Completed", f"Processed {count} reports.\nCheck terminal for details.")
