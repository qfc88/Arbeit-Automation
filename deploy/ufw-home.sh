#!/usr/bin/env bash
#
# UFW rules for the home server. Run once as root:
#   sudo bash deploy/ufw-home.sh
#
# Result:
#   - Default deny inbound from the public interface.
#   - SSH allowed only from ZeroTier (zt+) and WireGuard (wg0).
#   - HTTP/HTTPS allowed only from the WireGuard peer (VPS) and ZeroTier.
#   - Scraper outbound is unrestricted (needed for arbeitsagentur.de / 2captcha).
#
# Assumes:
#   - ZeroTier interface starts with "zt" (default naming).
#   - WireGuard interface is "wg0" (matches deploy/wireguard/home-wg0.conf.example).
#   - Docker bridge does its own NAT; we do not try to firewall between
#     containers here.
#
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run as root." >&2
    exit 1
fi

# Clean slate
ufw --force reset

ufw default deny incoming
ufw default allow outgoing

# SSH: only via admin tunnels
ufw allow in on zt+ to any port 22 proto tcp
ufw allow in on wg0 to any port 22 proto tcp

# Web: only from VPS tunnel and ZT admins
ufw allow in on wg0 to any port 80 proto tcp
ufw allow in on wg0 to any port 443 proto tcp
ufw allow in on zt+ to any port 80 proto tcp

# WireGuard handshake — needed so the home peer can reach the VPS endpoint
# (outbound is already allowed; no inbound rule required here).

# Explicitly block common admin ports on the public interface as belt-and-braces
# in case the Docker bind policy slips.
ufw deny in on any to any port 5432 proto tcp     # postgres
ufw deny in on any to any port 8000 proto tcp     # scraper
ufw deny in on any to any port 8080 proto tcp     # adminer
ufw deny in on any to any port 9000 proto tcp     # monitor

ufw --force enable
ufw status verbose
