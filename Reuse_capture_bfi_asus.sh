#!/usr/bin/env bash
# ================================================================
# Automated BFI Capture Script (ASUS RT-AC86U + ALFA AWUS036ACM)
# Author: Muttaki I. Bismoy
# ================================================================

CAPTURE_DIR=~/captures
IF_MON="wlx00c0cab88d1f"
IF_STA="wlp0s20f3"
SSID="ASUS_BFI_5G"
PASS="WPA2-Personal"
CHANNEL=149
WIDTH="80MHz"
CAPTURE_FILE="bfi_capture_20251103_075257.pcapng"
DURATION=60

mkdir -p "$CAPTURE_DIR"
nmcli dev disconnect "$IF_STA" >/dev/null 2>&1
nmcli dev wifi connect "$SSID" password "$PASS"

sudo nmcli dev set "$IF_MON" managed no
sudo ip link set "$IF_MON" down
sudo iw dev "$IF_MON" set type monitor
sudo ip link set "$IF_MON" up
sudo iw "$IF_MON" set channel "$CHANNEL" "$WIDTH"

sudo tcpdump -i "$IF_MON" -s 0 -w "$CAPTURE_DIR/$CAPTURE_FILE" &
PID=$!

read -p "Enter IP of iperf3 server: " SERVER_IP
iperf3 -c "$SERVER_IP" -R -t "$DURATION"

sudo kill -SIGINT $PID
sleep 2

tshark -r "$CAPTURE_DIR/$CAPTURE_FILE" -Y "wlan.vht.compressed_beamforming_report" -T fields -e frame.number | head
