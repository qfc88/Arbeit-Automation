#!/usr/bin/env bash
#
# UFW rules for the VPS reverse-proxy. Run once as root:
#   sudo bash deploy/ufw-vps.sh
#
# Allows only SSH, HTTP/HTTPS, and the WireGuard UDP port. Everything else is
# denied.
#
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run as root." >&2
    exit 1
fi

ufw --force reset

ufw default deny incoming
ufw default allow outgoing

ufw allow 22/tcp       comment "ssh"
ufw allow 80/tcp       comment "http (redirect to https)"
ufw allow 443/tcp      comment "https"
ufw allow 51820/udp    comment "wireguard"

ufw --force enable
ufw status verbose
