#!/usr/bin/env bash
# capture_bfi.sh
# One-click helper to install deps, set up the TP‑Link Archer T2U Plus (RTL8821AU),
# and capture 802.11ac BFI-ready traffic into a .pcapng file.
#
# USAGE (most common):
#   sudo bash capture_bfi.sh --ssid "ASUS_BFI_5G" --password "bfiproject123" --router 192.168.50.1
#
# Advanced:
#   sudo bash capture_bfi.sh --ssid "ASUS_BFI_5G" --password "xxx" --router 192.168.50.1 \
#       --iface wlxb01921e7721f --channel 149 --width 80 --duration 120 --outfile ~/bfi_capture.pcapng
#
# Notes:
# - This script targets Ubuntu 22.04/24.04.
# - It installs: dkms git build-essential tcpdump aircrack-ng wireshark iperf3 mokutil.
# - It will try to install the RTL8821AU driver from morrownr/8821au-20210708 (DKMS).
# - If Secure Boot is enabled, you will need to enroll the MOK key at reboot (manual step).
# - Router configuration cannot be automated from Linux; follow the README for ASUS settings.
#
set -euo pipefail

# ---------- defaults ----------
SSID_DEFAULT="ASUS_BFI_5G"
PASS_DEFAULT="bfiproject123"
ROUTER_IP_DEFAULT="192.168.50.1"
IFACE_DEFAULT=""
CHANNEL_DEFAULT=""
WIDTH_DEFAULT="80"
DURATION_DEFAULT="120"
OUTFILE_DEFAULT="$HOME/bfi_capture.pcapng"
DRIVER_REPO="https://github.com/morrownr/8821au-20210708.git"
DRIVER_DIR="$HOME/8821au-20210708"

# ---------- color helpers ----------
c_green() { echo -e "\033[1;32m$*\033[0m"; }
c_red()   { echo -e "\033[1;31m$*\033[0m"; }
c_yel()   { echo -e "\033[1;33m$*\033[0m"; }
c_cya()   { echo -e "\033[1;36m$*\033[0m"; }

# ---------- usage ----------
usage() {
  cat <<EOF
$(basename "$0") — Capture 802.11ac BFI-ready traffic with TP-Link Archer T2U Plus (RTL8821AU)

Required (recommended defaults shown):
  --ssid "<name>"        Wi‑Fi SSID to connect before capture (default: ${SSID_DEFAULT})
  --password "<pass>"    Wi‑Fi password (default: ${PASS_DEFAULT})
  --router <ip>          Router IP for ping/iperf traffic (default: ${ROUTER_IP_DEFAULT})

Optional:
  --iface <name>         Wireless interface (auto-detects a wlx* USB iface)
  --channel <num>        Lock monitor channel (e.g., 36, 149). If empty, stays auto.
  --width <mhz>          HT/VHT channel width (20|40|80) (default: ${WIDTH_DEFAULT})
  --duration <sec>       Capture duration in seconds (default: ${DURATION_DEFAULT})
  --outfile <path>       Output .pcapng file (default: ${OUTFILE_DEFAULT})
  --no-install           Skip installing packages/driver
  --no-connect           Skip associating to SSID (capture only in monitor mode)
  --help                 Show this help

Examples:
  sudo bash $(basename "$0") --ssid "ASUS_BFI_5G" --password "bfiproject123" --router 192.168.50.1
  sudo bash $(basename "$0") --channel 149 --duration 180 --outfile /tmp/bfi_$(date +%F).pcapng
EOF
}

# ---------- arg parse ----------
SSID="$SSID_DEFAULT"
PASSWORD="$PASS_DEFAULT"
ROUTER_IP="$ROUTER_IP_DEFAULT"
IFACE="$IFACE_DEFAULT"
CHANNEL="$CHANNEL_DEFAULT"
WIDTH="$WIDTH_DEFAULT"
DURATION="$DURATION_DEFAULT"
OUTFILE="$OUTFILE_DEFAULT"
DO_INSTALL=1
DO_CONNECT=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ssid)       SSID="$2"; shift 2;;
    --password)   PASSWORD="$2"; shift 2;;
    --router)     ROUTER_IP="$2"; shift 2;;
    --iface)      IFACE="$2"; shift 2;;
    --channel)    CHANNEL="$2"; shift 2;;
    --width)      WIDTH="$2"; shift 2;;
    --duration)   DURATION="$2"; shift 2;;
    --outfile)    OUTFILE="$2"; shift 2;;
    --no-install) DO_INSTALL=0; shift;;
    --no-connect) DO_CONNECT=0; shift;;
    --help|-h)    usage; exit 0;;
    *) c_red "Unknown argument: $1"; usage; exit 1;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  c_red "Please run as root: sudo bash $0 [args]"
  exit 1
fi

log_header() {
  c_cya "\n===== $* =====\n"
}

# ---------- detect usb wifi iface (wlx*) ----------
detect_iface() {
  # pick first wlx* that exists
  local candidates
  candidates=$(ls /sys/class/net 2>/dev/null | grep -E '^wlx' || true)
  if [[ -n "$candidates" ]]; then
    echo "$candidates" | head -n1
    return 0
  fi
  # fallback: pick any wireless other than wlp* internal
  candidates=$(ls /sys/class/net 2>/dev/null | grep -E '^wl' || true)
  if [[ -n "$candidates" ]]; then
    echo "$candidates" | head -n1
    return 0
  fi
  return 1
}

# ---------- install deps and driver ----------
install_everything() {
  log_header "Installing packages"
  DEBIAN_FRONTEND=noninteractive apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    dkms git build-essential tcpdump aircrack-ng wireshark iperf3 mokutil

  if ! lsmod | grep -q 8821au; then
    log_header "Installing RTL8821AU driver via DKMS"
    if [[ ! -d "$DRIVER_DIR" ]]; then
      sudo -u "$SUDO_USER" git clone "$DRIVER_REPO" "$DRIVER_DIR"
    else
      pushd "$DRIVER_DIR" >/dev/null
      sudo -u "$SUDO_USER" git pull --ff-only || true
      popd >/dev/null
    fi
    pushd "$DRIVER_DIR" >/dev/null
    bash ./install-driver.sh || true
    popd >/dev/null

    # SecureBoot check
    if mokutil --sb-state 2>/dev/null | grep -qi "enabled"; then
      c_yel "Secure Boot is ENABLED. If this is your first install, you must enroll the MOK key."
      c_yel "Run: mokutil --import /var/lib/shim-signed/mok/MOK.der, set a temporary password, reboot,"
      c_yel "then choose 'Enroll MOK' → 'Continue' → 'Yes' and enter the password. Re-run this script after reboot."
    fi
  else
    c_green "RTL8821AU driver already loaded."
  fi
}

# ---------- connect to SSID using nmcli ----------
connect_wifi() {
  local ifc="$1"
  log_header "Connecting $ifc to SSID '$SSID'"
  nmcli device set "$ifc" managed yes || true
  nmcli device disconnect "$ifc" || true
  nmcli device wifi rescan ifname "$ifc" || true
  sleep 2
  nmcli device wifi connect "$SSID" password "$PASSWORD" ifname "$ifc" || {
    c_yel "Connection via nmcli failed. Proceeding anyway; capture in monitor mode does not require association."
  }
  nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device | sed 's/^/  /'
}

# ---------- switch to monitor mode ----------
to_monitor() {
  local ifc="$1"
  log_header "Switching $ifc to MONITOR mode"
  ip link set "$ifc" down || true
  iw dev "$ifc" set type monitor
  ip link set "$ifc" up
  iw dev "$ifc" info | sed 's/^/  /'
  if [[ -n "$CHANNEL" ]]; then
    log_header "Locking to channel $CHANNEL (width $WIDTH MHz)"
    iw dev "$ifc" set channel "$CHANNEL" "HT$WIDTH" || true
  fi
}

# ---------- revert to managed ----------
to_managed() {
  local ifc="$1"
  log_header "Reverting $ifc to MANAGED mode"
  ip link set "$ifc" down || true
  iw dev "$ifc" set type managed || true
  ip link set "$ifc" up || true
}

# ---------- capture with tcpdump and generate traffic ----------
do_capture() {
  local ifc="$1"
  local outfile="$2"
  local duration="$3"
  log_header "Starting capture on $ifc → $outfile (duration ${duration}s)"
  # background traffic to encourage BFI
  ( ping -i 0.1 -w "$duration" "$ROUTER_IP" >/dev/null 2>&1 || true ) &
  PING_PID=$!
  # capture
  timeout --signal=INT "$duration" tcpdump -i "$ifc" -w "$outfile"
  wait "$PING_PID" || true
  c_green "Capture complete. File saved at: $outfile"
  ls -lh "$outfile" | sed 's/^/  /'
}

# ---------- main ----------
log_header "BFI capture helper — starting"

if [[ $DO_INSTALL -eq 1 ]]; then
  install_everything
else
  c_yel "Skipping package/driver installation (--no-install)."
fi

if [[ -z "$IFACE" ]]; then
  IFACE=$(detect_iface || true)
fi
if [[ -z "$IFACE" ]]; then
  c_red "Could not auto-detect the TP-Link USB interface. Use --iface <name>."
  iw dev || true
  exit 1
fi

c_green "Using wireless interface: $IFACE"

if [[ $DO_CONNECT -eq 1 ]]; then
  connect_wifi "$IFACE"
else
  c_yel "Skipping association (--no-connect)."
fi

# Ensure output dir exists
mkdir -p "$(dirname "$OUTFILE")"

# Clean up on exit
cleanup() {
  to_managed "$IFACE" || true
}
trap cleanup EXIT

to_monitor "$IFACE"
do_capture "$IFACE" "$OUTFILE" "$DURATION"

c_green "Done."
c_cya "Next: open in Wireshark → filter with: wlan.vht"
