#!/usr/bin/env python3
"""
============================================================
BFI Analyzer (bfi_analyzer.py)
============================================================
This script analyzes a .pcapng file and reports:
 - Total BFI frame count
 - Capture duration
 - BFI rate per second and per minute

Usage:
  python3 bfi_analyzer.py /path/to/bfi_capture.pcapng

Requires:
  - tshark must be installed and accessible in PATH
============================================================
"""

import os
import sys
import subprocess

def run_cmd(cmd):
    """Run a shell command and return its output as a string."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[!] Error executing: {cmd}\n{e.stderr}")
        sys.exit(1)

def analyze_bfi(file_path):
    if not os.path.exists(file_path):
        print(f"[!] File not found: {file_path}")
        sys.exit(1)

    print(f"[+] Analyzing BFI data in: {file_path}\n")

    # Extract start, end, duration using tshark
    awk_script = "NR==1{start=$1} {end=$1} END{print start, end, end-start}"
    cmd = f'tshark -r "{file_path}" -Y "wlan.vht.compressed_beamforming_report" -T fields -e frame.time_relative | awk \"{awk_script}\"'
    output = run_cmd(cmd)

    try:
        start, end, duration = map(float, output.split())
    except ValueError:
        print("[!] No BFI frames found or invalid output.")
        sys.exit(0)

    # Count total BFI frames
    count_cmd = f'tshark -r "{file_path}" -Y "wlan.vht.compressed_beamforming_report" | wc -l'
    count = int(run_cmd(count_cmd))

    rate_per_sec = count / duration if duration > 0 else 0
    rate_per_min = rate_per_sec * 60

    print("=== BFI Analysis Summary ===")
    print(f"File: {file_path}")
    print(f"Total BFI Frames: {count}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Rate: {rate_per_sec:.2f} per second ({rate_per_min:.2f} per minute)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 bfi_analyzer.py <path_to_pcapng>")
        sys.exit(1)

    analyze_bfi(sys.argv[1])
