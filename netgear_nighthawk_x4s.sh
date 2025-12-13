#!/bin/bash
# ============================================================
#  Automated BFI Capture Script (bfi_capture.sh)
#  For ALFA AWUS036ACM + Netgear Nighthawk R7800
# ============================================================
#  This script:
#   1. Sets up the ALFA adapter into monitor mode on channel 149 (80 MHz)
#   2. Starts tcpdump capture for 60 seconds
#   3. Computes BFI frame count and rate per second
# ============================================================

set -e

# --- Configuration ---
INTERFACE="wlx00c0cab88d1f"
CAPTURE_DIR="$HOME/captures"
DURATION=60

# --- Preparation ---
echo "[+] Creating capture directory at $CAPTURE_DIR"
mkdir -p "$CAPTURE_DIR"

# --- Switch to monitor mode ---
echo "[+] Setting up $INTERFACE into monitor mode..."
sudo nmcli dev set $INTERFACE managed no || true
sudo ip link set $INTERFACE down
sudo iw dev $INTERFACE set type monitor
sudo ip link set $INTERFACE up
sudo iw dev $INTERFACE set freq 5745 80 5775

echo "[+] Verifying interface setup:"
iw dev $INTERFACE info

# --- Start capture ---
FILE="$CAPTURE_DIR/bfi_raw_$(date +%Y%m%d_%H%M%S).pcapng"
echo "[+] Capturing Wi-Fi traffic for $DURATION seconds..."
sudo tcpdump -i $INTERFACE -s 0 -w "$FILE" &
PID=$!
sleep $DURATION
echo "[+] Stopping capture (PID=$PID)"
sudo kill -INT $PID 2>/dev/null || true
sleep 2

# --- Compute BFI rate ---
echo "[+] Computing BFI rate..."
read START END DURATION <<<$(tshark -r "$FILE" \
  -Y "wlan.vht.compressed_beamforming_report" \
  -T fields -e frame.time_relative \
  | awk 'NR==1{start=$1} {end=$1} END{print start, end, end-start}')

COUNT=$(tshark -r "$FILE" -Y "wlan.vht.compressed_beamforming_report" | wc -l)
if [ -z "$DURATION" ] || [ "$DURATION" == "" ]; then
  DURATION=60
fi

RATE=$(echo "$COUNT / $DURATION" | bc -l)

printf "\n=== BFI Capture Summary ===\n"
printf "File: %s\n" "$FILE"
printf "BFI Frames: %d\n" "$COUNT"
printf "Duration: %.2fs\n" "$DURATION"
printf "Rate: %.2f per second (%.2f per minute)\n" "$RATE" $(echo "$RATE*60" | bc -l)

echo "[+] Capture complete! File saved at: $FILE"
