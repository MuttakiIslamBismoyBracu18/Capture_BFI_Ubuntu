#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bfi_R7800.py — Full passive BFI capture & analysis with GUI and iperf3 option
Author: Obak Bismoy
"""

import os
import sys
import time
import shutil
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# ---------- Defaults ----------
DEFAULTS = {
    "CAPTURE_TIME": 60,
    "OUTDIR": "/home/obak-b/captures",
    "TMPDIR": "/tmp",
    "IF_STA": "wlp0s20f3",
    "IPERF_PORT": 5202,
    "IPERF_PARALLELS": 4,
    "SSID_CHOICES": ["BFI_Test_5G", "NETGEAR25-5G", "ASUS_BFI_5G"],
    "WIFI_PASSWORD": "WPA2-Personal"
}

CHANNEL_FREQS = {
    36:(5180,5210),40:(5200,5230),44:(5220,5250),48:(5240,5270),
    149:(5745,5775),153:(5765,5775),157:(5785,5775),
    161:(5805,5775),165:(5825,5855)
}

ADAPTERS = ["wlxb01921e7721f", "wlx00c0cab88d1f"]

# ---------- Utility ----------
def now_tag(): return datetime.now().strftime("%Y%m%d_%H%M%S")

def run(cmd, *, capture=False, soft=False):
    print(f"[RUN] {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=capture, text=capture)
    if not soft and res.returncode != 0:
        err = (res.stderr or "").strip() if capture else ""
        print(f"[ERROR] {cmd}\n{err}")
        sys.exit(1)
    return (res.stdout.strip() if capture else None)

def ensure_dir(path): os.makedirs(path, exist_ok=True)
def file_size_ok(path): return os.path.exists(path) and os.path.getsize(path) > 64

# ---------- Network ----------
def set_monitor(iface, freq, center1):
    run(f"sudo nmcli dev set {iface} managed no", soft=True)
    run(f"sudo ip link set {iface} down")
    run(f"sudo iw dev {iface} set type monitor")
    run(f"sudo ip link set {iface} up")
    run(f"sudo iw dev {iface} set freq {freq} 80 {center1}")
    info = run(f"iw dev {iface} info", capture=True, soft=True)
    print(info)

def restore_managed(iface):
    print("[CLEANUP] Restoring interface & NetworkManager...")
    run(f"sudo ip link set {iface} down", soft=True)
    run(f"sudo iw dev {iface} set type managed", soft=True)
    run(f"sudo ip link set {iface} up", soft=True)
    run(f"sudo nmcli dev set {iface} managed yes", soft=True)

def nmcli_connect(ssid, sta_iface, pwd):
    run(f"sudo nmcli dev set {sta_iface} managed yes", soft=True)
    run(f"sudo nmcli dev disconnect {sta_iface}", soft=True)
    run(f'sudo nmcli dev wifi connect "{ssid}" password "{pwd}" ifname "{sta_iface}"', soft=True)

def start_iperf3(ip, port, secs, par):
    if not shutil.which("iperf3"):
        print("[IPERF] iperf3 not found; skipping.")
        return None
    cmd=f"iperf3 -c {ip} -p {port} -t {secs} -P {par}"
    try:
        p=subprocess.Popen(cmd.split(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        print(f"[IPERF] Started iperf3 client -> {ip}:{port} for {secs}s ({par} streams)")
        return p
    except Exception as e:
        print(f"[IPERF] Error: {e}")
        return None

# ---------- tshark analysis ----------
def tshark_count_bfi(pcap):
    out=run(f'tshark -r "{pcap}" -Y "wlan.vht.compressed_beamforming_report" | wc -l',capture=True,soft=True)
    return int(out.strip() or 0)

def detect_ap_mac(pcap):
    out=run(f'tshark -r "{pcap}" -Y "wlan.vht.compressed_beamforming_report" -T fields -e wlan.da',capture=True,soft=True)
    counts={}
    for line in out.splitlines():
        mac=line.strip()
        if mac: counts[mac]=counts.get(mac,0)+1
    if not counts: return None,{}
    ap=max(counts.items(),key=lambda kv:kv[1])[0]
    return ap,counts

def list_rx_counts(pcap,ap):
    out=run(f'tshark -r "{pcap}" -Y "wlan.vht.compressed_beamforming_report && wlan.da=={ap}" -T fields -e wlan.sa',capture=True,soft=True)
    counts={}
    for line in out.splitlines():
        mac=line.strip()
        if mac: counts[mac]=counts.get(mac,0)+1
    return counts

def sta_stats(pcap,sta,ap):
    times=run(f'tshark -r "{pcap}" -Y "wlan.vht.compressed_beamforming_report && wlan.sa=={sta} && wlan.da=={ap}" -T fields -e frame.time_relative',capture=True,soft=True)
    tvals=[float(x) for x in times.splitlines() if x.strip()]
    if not tvals: return 0,0,0
    dur=tvals[-1]-tvals[0] if len(tvals)>1 else 0
    count=len(tvals)
    rate=count/dur if dur>0 else 0
    return count,dur,rate

# ---------- GUI ----------
def ask_user():
    root=tk.Tk(); root.title("BFI Capture Configuration"); root.geometry("400x360"); root.resizable(False,False)
    tk.Label(root,text="Select Channel:",font=("Arial",11)).pack(pady=6)
    chv=tk.StringVar(value="157"); ttk.Combobox(root,textvariable=chv,values=list(CHANNEL_FREQS.keys()),state="readonly",width=15).pack()
    tk.Label(root,text="Select Adapter:",font=("Arial",11)).pack(pady=6)
    ifv=tk.StringVar(value=ADAPTERS[0]); ttk.Combobox(root,textvariable=ifv,values=ADAPTERS,state="readonly",width=25).pack()

    iperf_on=tk.BooleanVar(value=False)
    def toggle():
        state="normal" if iperf_on.get() else "disabled"
        ipent.config(state=state); portent.config(state=state); parent.config(state=state); ssident.config(state=state)
    tk.Checkbutton(root,text="Enable iperf3 traffic",variable=iperf_on,command=toggle).pack(pady=10)

    tk.Label(root,text="Receiver IPv4:",font=("Arial",10)).pack()
    ipv=tk.StringVar(value="192.168.1.3"); ipent=ttk.Entry(root,textvariable=ipv,width=20,state="disabled"); ipent.pack()
    tk.Label(root,text="Port / Streams:",font=("Arial",10)).pack()
    frm=tk.Frame(root); frm.pack()
    pv=tk.StringVar(value=str(DEFAULTS["IPERF_PORT"])); portent=ttk.Entry(frm,textvariable=pv,width=8,state="disabled"); portent.grid(row=0,column=0,padx=4)
    parv=tk.StringVar(value=str(DEFAULTS["IPERF_PARALLELS"])); parent=ttk.Entry(frm,textvariable=parv,width=8,state="disabled"); parent.grid(row=0,column=1,padx=4)
    tk.Label(root,text="Select SSID:",font=("Arial",10)).pack(pady=6)
    ssidv=tk.StringVar(value=DEFAULTS["SSID_CHOICES"][0]); ssident=ttk.Combobox(root,textvariable=ssidv,values=DEFAULTS["SSID_CHOICES"],state="disabled",width=25); ssident.pack()

    res={"done":False}
    def go():
        res.update({"ch":int(chv.get()),"iface":ifv.get(),"iperf":iperf_on.get(),
                    "ip":ipv.get(),"port":int(pv.get()),"par":int(parv.get()),"ssid":ssidv.get()})
        res["done"]=True; root.destroy()
    tk.Button(root,text="Start Capture",bg="#4CAF50",fg="white",width=20,command=go).pack(pady=14)
    root.mainloop()
    if not res["done"]: sys.exit(0)
    return res

# ---------- MAIN ----------
def main():
    if os.geteuid()!=0:
        print("[INFO] Not root; re-executing with sudo...")
        os.execvp("sudo",["sudo",sys.executable]+sys.argv)

    ensure_dir(DEFAULTS["OUTDIR"]); ensure_dir(DEFAULTS["TMPDIR"])
    cfg=ask_user(); ch=cfg["ch"]; iface=cfg["iface"]

    freq,center1=CHANNEL_FREQS.get(ch,(ch*5+5000,ch*5+5030))
    print(f"[SETUP] Channel {ch} → freq {freq} MHz, center1 {center1} MHz")
    set_monitor(iface,freq,center1)

    tag=now_tag()
    tmp=os.path.join(DEFAULTS["TMPDIR"],f"bfi_capture_{tag}.pcapng")
    final=os.path.join(DEFAULTS["OUTDIR"],f"bfi_observe_{ch}_{tag}.pcapng")

    iperf_proc=None
    if cfg["iperf"]:
        print(f"[WIFI] Connecting STA ({DEFAULTS['IF_STA']}) to SSID '{cfg['ssid']}' ...")
        nmcli_connect(cfg["ssid"],DEFAULTS["IF_STA"],DEFAULTS["WIFI_PASSWORD"])
        time.sleep(3)
        iperf_proc=start_iperf3(cfg["ip"],cfg["port"],DEFAULTS["CAPTURE_TIME"],cfg["par"])

    print(f"[CAPTURE] Observing traffic on {iface} for {DEFAULTS['CAPTURE_TIME']}s ...")
    proc=subprocess.Popen(["sudo","tcpdump","-i",iface,"-s","0","-U","-G",str(DEFAULTS["CAPTURE_TIME"]),"-W","1","-w",tmp],
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try: proc.wait(timeout=DEFAULTS["CAPTURE_TIME"]+15)
    except subprocess.TimeoutExpired: proc.terminate()

    if iperf_proc and iperf_proc.poll() is None: iperf_proc.terminate()
    os.sync(); time.sleep(0.5)
    if not file_size_ok(tmp): restore_managed(iface); sys.exit("No capture file.")
    shutil.move(tmp,final)
    print(f"[CAPTURE] Saved: {final}")

    total=tshark_count_bfi(final)
    ap,ap_counts=detect_ap_mac(final)

    print("\n=== BFI Observation Summary ===")
    print(f"File:          {final}")
    print(f"Channel:       {ch}")
    print(f"Total BFI:     {total}\n")

    if ap:
        print("List of Tx [AP]:")
        print(f" {ap_counts.get(ap,0):5d} {ap}")
        print("\nList of Rx [STA]:")
        rx_counts=list_rx_counts(final,ap)
        for sta,count in rx_counts.items():
            print(f" {count:5d} {sta}")

        print("\nBFI Rate per Rx:")
        for sta in rx_counts:
            c,d,r=sta_stats(final,sta,ap)
            print(f"STA (Rx): {sta}  |  BFIs: {c}  |  Active: {d:.2f}s  |  Rate: {r:.2f} Hz")

        # overall BFI rate using AP frames
        times=run(f'tshark -r "{final}" -Y "wlan.vht.compressed_beamforming_report && wlan.da=={ap}" -T fields -e frame.time_relative',
                  capture=True,soft=True)
        tvals=[float(x) for x in times.splitlines() if x.strip()]
        dur=(tvals[-1]-tvals[0]) if len(tvals)>1 else 0
        rate=(ap_counts.get(ap,0)/dur) if dur>0 else 0
        print(f"\nAP: {ap}\nBFI Frames: {ap_counts.get(ap,0)}\nDuration: {dur:.2f}s\nOverall BFI Rate: {rate:.2f} Hz")
    else:
        print("No AP detected in capture.")

    restore_managed(iface)
    print("\n[DONE] Passive BFI observation complete.")

# ---------- ENTRY ----------
if __name__=="__main__": main()
