#!/usr/bin/env bash
# Keep the public deployment's containers off the LAN and off the host (Sprint 128).
#
# compose.public.yaml gives the application and its Cloudflare sidecar their own
# Docker networks to reach the internet: akasha_egress (bridge br-akasha-eg,
# 172.30.11.0/24) and akasha_tunnel (br-akasha-cf, 172.30.12.0/24). A Docker
# bridge can reach everything the host can — the router's admin page, the NAS,
# other containers' published ports, the Tailscale network, the host's own
# services. This script narrows that to what each container needs:
#
#   - to private, Tailscale (CGNAT), link-local, multicast and reserved
#     addresses: refused, whichever port;
#   - to the public internet: the application gets HTTPS (and HTTP, which every
#     provider immediately redirects) plus DNS; the sidecar gets what
#     Cloudflare's tunnel uses (443, 7844 TCP and UDP) plus DNS; anything else
#     is refused;
#   - to the host itself, from any of the three Akasha bridges: new
#     connections refused (replies to connections the host opened still flow).
#
# The point is the day the application is compromised: code running as the
# application can then talk to the internet on 80/443 — which it must, to fetch
# metadata — but not to anything in the house.
#
# Usage (as root, on the Docker host):
#   sudo scripts/akasha-egress-firewall.sh            apply (idempotent)
#   sudo scripts/akasha-egress-firewall.sh --dry-run  print the commands only
#   sudo scripts/akasha-egress-firewall.sh --remove   take every rule out again
#
# Idempotent: each run rebuilds two chains of its own (AKASHA-EGRESS,
# AKASHA-HOST) and makes sure exactly one jump to each exists. Rules do not
# survive a reboot; the runbook shows a systemd unit that reapplies them after
# Docker starts.
#
# Requirements and limits:
#   - Docker's iptables firewall backend (the default), which provides the
#     DOCKER-USER chain. With Docker's nftables backend, or with firewalld or
#     ufw managing the host, translate the rules rather than run this.
#   - IPv4 only. compose.public.yaml disables IPv6 on all three networks
#     (enable_ipv6: false); keep it that way, or these rules have a hole
#     the size of the IPv6 internet and your IPv6 LAN.
#   - The subnets below must match compose.public.yaml.

set -euo pipefail

# --- Settings: must match compose.public.yaml --------------------------------
APP_SUBNET="${AKASHA_EGRESS_SUBNET:-172.30.11.0/24}"
TUNNEL_SUBNET="${AKASHA_TUNNEL_SUBNET:-172.30.12.0/24}"
BRIDGES=(br-akasha-in br-akasha-eg br-akasha-cf)

# Never reachable from these containers, on any port.
BLOCKED_DESTINATIONS=(
  0.0.0.0/8        # "this network"
  10.0.0.0/8       # RFC 1918 private
  100.64.0.0/10    # CGNAT: Tailscale and some ISPs
  127.0.0.0/8      # loopback (never routed, listed for completeness)
  169.254.0.0/16   # link-local, including cloud metadata 169.254.169.254
  172.16.0.0/12    # RFC 1918 private, including every Docker bridge
  192.0.0.0/24     # IETF protocol assignments
  192.168.0.0/16   # RFC 1918 private: most home LANs
  198.18.0.0/15    # benchmarking
  224.0.0.0/4      # multicast (mDNS, SSDP/UPnP)
  240.0.0.0/4      # reserved, and broadcast
)
# --------------------------------------------------------------------------------

DRY_RUN=0
REMOVE=0
for argument in "$@"; do
  case "$argument" in
    --dry-run) DRY_RUN=1 ;;
    --remove) REMOVE=1 ;;
    -h | --help)
      sed -n '2,40p' "$0"
      exit 0
      ;;
    *)
      echo "unknown argument: $argument (expected --dry-run or --remove)" >&2
      exit 2
      ;;
  esac
done

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf 'iptables -w %s\n' "$*"
  else
    iptables -w "$@"
  fi
}

# `iptables -C` answers whether a rule exists; in a dry run, assume it does not.
exists() {
  [ "$DRY_RUN" -eq 0 ] && iptables -w "$@" 2>/dev/null
}

ensure_chain() {
  if [ "$DRY_RUN" -eq 1 ] || ! iptables -w -n -L "$1" >/dev/null 2>&1; then
    run -N "$1"
  fi
  run -F "$1"
}

ensure_jump() { # chain, then the rule spec
  local chain="$1"
  shift
  if ! exists -C "$chain" "$@"; then
    run -I "$chain" 1 "$@"
  fi
}

remove_jump() {
  local chain="$1"
  shift
  while exists -C "$chain" "$@"; do
    run -D "$chain" "$@"
  done
  if [ "$DRY_RUN" -eq 1 ]; then
    run -D "$chain" "$@"
  fi
}

if [ "$DRY_RUN" -eq 0 ]; then
  if [ "$(id -u)" -ne 0 ]; then
    echo "run as root (sudo), or with --dry-run to see the commands" >&2
    exit 1
  fi
  if ! iptables -w -n -L DOCKER-USER >/dev/null 2>&1; then
    echo "no DOCKER-USER chain: is Docker running with its iptables backend?" >&2
    exit 1
  fi
fi

if [ "$REMOVE" -eq 1 ]; then
  for subnet in "$APP_SUBNET" "$TUNNEL_SUBNET"; do
    remove_jump DOCKER-USER -s "$subnet" -j AKASHA-EGRESS
  done
  for bridge in "${BRIDGES[@]}"; do
    remove_jump INPUT -i "$bridge" -j AKASHA-HOST
  done
  for chain in AKASHA-EGRESS AKASHA-HOST; do
    if [ "$DRY_RUN" -eq 1 ] || iptables -w -n -L "$chain" >/dev/null 2>&1; then
      run -F "$chain"
      run -X "$chain"
    fi
  done
  exit 0
fi

# --- Forwarded traffic: what the containers may reach beyond the host ----------
ensure_chain AKASHA-EGRESS
# Replies to connections already allowed.
run -A AKASHA-EGRESS -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
for destination in "${BLOCKED_DESTINATIONS[@]}"; do
  run -A AKASHA-EGRESS -d "$destination" -j REJECT --reject-with icmp-admin-prohibited
done
# DNS, to the public resolvers compose.public.yaml names (the private ones were
# refused above).
for subnet in "$APP_SUBNET" "$TUNNEL_SUBNET"; do
  run -A AKASHA-EGRESS -s "$subnet" -p udp --dport 53 -j RETURN
  run -A AKASHA-EGRESS -s "$subnet" -p tcp --dport 53 -j RETURN
done
# The application: metadata providers and cover hosts, over HTTPS (HTTP only to
# be redirected to it).
run -A AKASHA-EGRESS -s "$APP_SUBNET" -p tcp -m multiport --dports 80,443 -j RETURN
# The sidecar: Cloudflare's edge (7844, QUIC or HTTP/2) and its API (443).
run -A AKASHA-EGRESS -s "$TUNNEL_SUBNET" -p tcp -m multiport --dports 443,7844 -j RETURN
run -A AKASHA-EGRESS -s "$TUNNEL_SUBNET" -p udp --dport 7844 -j RETURN
# Everything else from these subnets.
run -A AKASHA-EGRESS -p tcp -j REJECT --reject-with tcp-reset
run -A AKASHA-EGRESS -j REJECT --reject-with icmp-admin-prohibited

# RETURN hands allowed traffic back to DOCKER-USER and on to Docker's own rules.
for subnet in "$APP_SUBNET" "$TUNNEL_SUBNET"; do
  ensure_jump DOCKER-USER -s "$subnet" -j AKASHA-EGRESS
done

# --- Traffic to the host itself (any of its addresses) --------------------------
ensure_chain AKASHA-HOST
run -A AKASHA-HOST -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
run -A AKASHA-HOST -j REJECT --reject-with icmp-admin-prohibited
for bridge in "${BRIDGES[@]}"; do
  ensure_jump INPUT -i "$bridge" -j AKASHA-HOST
done

if [ "$DRY_RUN" -eq 0 ]; then
  echo "Akasha egress rules applied. Check with: iptables -L AKASHA-EGRESS -n -v"
fi
