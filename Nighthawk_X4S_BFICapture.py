#!/usr/bin/env python3
"""
capture_bfi.py

Robust automated BFI capture script for:
 - ALFA AWUS036ACM (example iface wlx00c0cab88d1f)
 - Surface internal Wi-Fi (wlp0s20f3)
 - Netgear/ASUS 5GHz (802.11ac VHT) AP on channel 149

What it does:
 1. Verifies dependencies (nmcli, iw, ip, tcpdump, tshark, iperf3)
 2. Puts ALFA into monitor mode and locks to freq (149 @ 80 MHz)
 3. Starts tcpdump to capture to a timestamped .pcapng in CAPTURE_BASE
 4. Optionally launches an iperf3 client to IPERF_SERVER for CAPTURE_TIME seconds
 5. Stops capture, parses the pcap with tshark to count BFI frames and compute rate
 6. Restores NetworkManager management (recommended) and prints summary

Usage:
  sudo python3 Nighthawk_X4S_BFICapture.py [--no-iperf] [--iface IF_MON] [--sta IF_STA]
                             [--server IPERF_SERVER] [--time CAPTURE_TIME]
                             [--outdir CAPTURE_BASE]

How to run:
# basic capture + iperf traffic (make sure IPERF_SERVER is reachable)
sudo python3 Nighthawk_X4S_BFICapture.py --ipserver 192.168.1.5 --time 120 --outdir ~/captures

# or capture-only (no iperf)
sudo python3 ~/scripts/Nighthawk_X4S_BFICapture.py --no-iperf --time 60 --outdir ~/captures

Notes:
 - Running with sudo is recommended so tcpdump and iw commands run cleanly.
 - If you don't have an iperf3 server, use --no-iperf and perform traffic using another device (phone/laptop) manually.
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capture_bfi.py  — robust BFI capture + analysis for 802.11ac (VHT)

What it does (safely):
  1) Verifies tools (nmcli, iw, ip, tcpdump, tshark; optional iperf3)
  2) Takes ALFA (IF_MON) under manual control, sets monitor, locks channel 149@80MHz
  3) Starts tcpdump with auto-stop (-G/-W) to avoid truncated pcaps
  4) (Optional) Runs iperf3 client to generate traffic during capture
  5) Flushes/validates pcap, analyzes with tshark (soft on warnings)
  6) Restores interface & NetworkManager management, prints BFI rate

Usage examples:
  sudo python3 Nighthawk_X4S_BFICapture.py \
    --if-mon wlxb01921e7721f --if-sta wlp0s20f3 \
    --ipserver 192.168.1.3 --time 120 --outdir ~/captures

  # Capture-only (no iperf)
  sudo python3 capture_bfi.py --no-iperf --time 60 --outdir ~/captures

Notes:
  - Run with sudo (script will re-exec with sudo if needed).
  - Make sure your STA (Surface) is connected to the AP (VHT mode).
  - Router should be in 802.11ac-only, Explicit Beamforming ON, 80 MHz, ch149.
"""

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime

# ----------------- Defaults -----------------
DEFAULTS = {
    "IF_MON": "wlxb01921e7721f",
    "IF_STA": "wlp0s20f3",
    "SSID": "BFI_Test_5G",
    "CHANNEL": 157,
    "FREQ": 5785,          # MHz center freq for ch 149
    "CENTER1": 5775,       # center1 for 80 MHz block
    "CAPTURE_TIME": 60,    # seconds
    "OUTDIR": os.path.expanduser("~/captures"),
    "TMPDIR": "/tmp",
    "IPERF_SERVER": "192.168.1.3",
    "IPERF_PORT": 5202,
    "IPERF_PARALLELS": 4,
}

# ----------------- Helpers -----------------
def which_or_die(name):
    path = shutil.which(name)
    if not path:
        die(f"Required binary '{name}' not found in PATH.")
    return path

def die(msg, code=1):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)

def run(cmd, *, capture=False, soft=False, env=None):
    """
    Run shell command.
    - capture=True  -> return stdout string
    - soft=True     -> do not raise/die on non-zero exit; return stdout anyway
    """
    print(f"[RUN] {cmd}")
    res = subprocess.run(cmd, shell=True,
                         capture_output=capture, text=capture, env=env)
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

# ----------------- Global child tracking -----------------
CHILDREN = []

def add_child(proc):
    if proc:
        CHILDREN.append(proc)

def terminate_children():
    for p in CHILDREN:
        try: p.terminate()
        except Exception: pass
    time.sleep(0.3)
    for p in CHILDREN:
        try: p.kill()
        except Exception: pass

# ----------------- Monitor setup/restore -----------------
def set_monitor(iface, freq, center1):
    # detach from NetworkManager (best-effort)
    run(f"sudo nmcli dev set {iface} managed no", soft=True)

    # set monitor + lock frequency
    run(f"sudo ip link set {iface} down")
    run(f"sudo iw dev {iface} set type monitor")
    run(f"sudo ip link set {iface} up")
    run(f"sudo iw dev {iface} set freq {freq} 80 {center1}")
    info = run(f"iw dev {iface} info", capture=True, soft=True) or ""
    print(info)
    if f"channel {DEFAULTS['CHANNEL']} (" not in info or "width: 80 MHz" not in info:
        print("[WARN] Monitor interface may not be locked correctly. Continuing anyway.")

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
    # Extract relative times of BFI frames; tolerate warnings / partial files
    out = run(
        f'tshark -r "{pcap}" -Y "wlan.vht.compressed_beamforming_report" '
        f'-T fields -e frame.time_relative',
        capture=True, soft=True
    ) or ""
    times = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            times.append(float(line))
        except ValueError:
            continue
    return times

def analyze_bfi(pcap, fallback_duration=None):
    count = tshark_count_bfi(pcap)
    if count == 0:
        return {"count": 0, "duration": float(fallback_duration or 0), "rate_s": 0.0}

    times = tshark_times_bfi(pcap)
    if len(times) >= 2:
        duration = max(0.0, times[-1] - times[0])
    else:
        # Fall back to capture duration if BFI time field list is empty
        duration = float(fallback_duration or 0)
    rate_s = (count / duration) if duration > 0 else 0.0
    return {"count": count, "duration": duration, "rate_s": rate_s}

# ----------------- iperf3 traffic -----------------
def start_iperf3(ip, port, secs, parallels):
    cmd = f'iperf3 -c {ip} -p {port} -t {secs} -P {parallels}'
    try:
        p = subprocess.Popen(cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        add_child(p)
        print(f"[IPERF] Started iperf3 client -> {ip}:{port} for {secs}s ({parallels} streams)")
        return p
    except FileNotFoundError:
        print("[IPERF] iperf3 not found; skipping traffic generation.")
    except Exception as e:
        print(f"[IPERF] Could not start iperf3: {e}")
    return None

# ----------------- Main -----------------
def main():
    ap = argparse.ArgumentParser(description="Robust BFI capture (VHT)")
    ap.add_argument("--if-mon", default=DEFAULTS["IF_MON"], help="monitor interface (ALFA)")
    ap.add_argument("--if-sta", default=DEFAULTS["IF_STA"], help="station interface (Surface) [informational]")
    ap.add_argument("--ssid",   default=DEFAULTS["SSID"],   help="SSID (informational)")
    ap.add_argument("--channel", default=DEFAULTS["CHANNEL"], type=int, help="channel number (default 149)")
    ap.add_argument("--freq",    default=DEFAULTS["FREQ"],    type=int, help="center frequency MHz (default 5745)")
    ap.add_argument("--center1", default=DEFAULTS["CENTER1"], type=int, help="center1 MHz (default 5775)")
    ap.add_argument("--time",    default=DEFAULTS["CAPTURE_TIME"], type=int, help="capture duration seconds")
    ap.add_argument("--outdir",  default=DEFAULTS["OUTDIR"], help="directory to store final pcap")
    ap.add_argument("--tmpdir",  default=DEFAULTS["TMPDIR"], help="temp directory for capture")
    ap.add_argument("--ipserver", default=DEFAULTS["IPERF_SERVER"], help="iperf3 server IP (omit with --no-iperf)")
    ap.add_argument("--ipport",   default=DEFAULTS["IPERF_PORT"], type=int, help="iperf3 port")
    ap.add_argument("--parallels", default=DEFAULTS["IPERF_PARALLELS"], type=int, help="iperf3 parallel streams")
    ap.add_argument("--no-iperf", action="store_true", help="skip iperf3 traffic generation")
    args = ap.parse_args()

    # Re-exec with sudo if needed
    if os.geteuid() != 0:
        print("[INFO] Not root; re-executing with sudo...")
        os.execvp("sudo", ["sudo", sys.executable] + sys.argv)

    # Tool checks
    for tool in ("nmcli", "iw", "ip", "tcpdump", "tshark"):
        which_or_die(tool)
    if not args.no_iperf:
        _ = shutil.which("iperf3") or print("[WARN] iperf3 not found; will skip if start fails.")

    # Dirs
    ensure_dir(args.outdir)
    ensure_dir(args.tmpdir)

    # Set monitor + lock freq
    set_monitor(args.if_mon, args.freq, args.center1)

    # Filenames
    tag = now_tag()
    tmp_pcap = os.path.join(args.tmpdir, f"bfi_capture_{tag}.pcapng")
    final_pcap = os.path.join(args.outdir, f"bfi_0x1_{tag}.pcapng")

    # Start tcpdump with auto-stop (-G secs, -W 1) and packet-buffered (-U)
    print(f"[CAPTURE] Writing to temp file: {tmp_pcap}")
    tcp_cmd = [
        "sudo", "tcpdump",
        "-i", args.if_mon,
        "-s", "0",
        "-U",                 # packet-buffered writes
        "-G", str(args.time), # stop/rotate every N seconds
        "-W", "1",            # keep 1 file
        "-w", tmp_pcap
    ]
    tcp_proc = subprocess.Popen(tcp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    add_child(tcp_proc)

    # Start iperf3 if requested
    iperf_proc = None
    if not args.no_iperf and args.ipserver:
        iperf_proc = start_iperf3(args.ipserver, args.ipport, args.time, args.parallels)

    # Wait for tcpdump to exit by itself
    try:
        tcp_proc.wait(timeout=args.time + 15)
    except subprocess.TimeoutExpired:
        print("[WARN] tcpdump did not exit; terminating...")
        try:
            tcp_proc.terminate()
            tcp_proc.wait(timeout=3)
        except Exception:
            pass

    # Ensure iperf is stopped
    if iperf_proc and iperf_proc.poll() is None:
        try:
            iperf_proc.terminate()
        except Exception:
            pass

    # Flush to disk
    try:
        os.sync()
    except Exception:
        pass
    time.sleep(0.5)

    # Validate temp file and move it
    if not file_size_ok(tmp_pcap):
        restore_managed(args.if_mon)
        terminate_children()
        die(f"No capture written or file too small: {tmp_pcap}")
    try:
        shutil.move(tmp_pcap, final_pcap)
    except Exception as e:
        restore_managed(args.if_mon)
        terminate_children()
        die(f"Failed to move pcap to outdir: {e}")

    print(f"[CAPTURE] Saved: {final_pcap}")

    # Analyze BFI (tolerate warnings/partial pcaps)
    print("[ANALYZE] Counting BFI...")
    result = analyze_bfi(final_pcap, fallback_duration=args.time)

    # Print summary
    print("\n=== BFI Capture Summary ===")
    print(f"File: {final_pcap}")
    print(f"BFI frames: {result['count']}")
    print(f"Duration: {result['duration']:.2f} s")
    print(f"Rate: {result['rate_s']:.3f} per sec ({result['rate_s']*60:.1f} per min)")

    # Restore interface
    restore_managed(args.if_mon)
    terminate_children()
    print("[DONE] capture_bfi.py finished cleanly.")

# ----------------- Entry -----------------
if __name__ == "__main__":
    main()

