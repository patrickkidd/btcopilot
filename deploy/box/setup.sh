#!/bin/sh
# One-time box changes for the laptop's monitoring link (doc/MONITORING.md),
# run as root from /var/www/btcopilot/deploy with the laptop key's public half:
#   sh box/setup.sh "ssh-ed25519 AAAA... fd-laptop"
# Safe to run again: each step replaces its own earlier result.
set -eu
key="$1"
here="$(dirname "$0")"
tag="fd-laptop"
ports="18428,14318"

install -m 0755 "$here/fd-logpull" /usr/local/bin/fd-logpull

keys=/root/.ssh/authorized_keys
touch "$keys"
grep -v " $tag\$" "$keys" > "$keys.new" || true
echo "restrict,port-forwarding,permitopen=\"127.0.0.1:5432\",permitlisten=\"172.17.0.1:18428\",permitlisten=\"172.17.0.1:14318\",command=\"/usr/local/bin/fd-logpull\" $(echo "$key" | cut -d" " -f1,2) $tag" >> "$keys.new"
chmod 600 "$keys.new"
mv "$keys.new" "$keys"

# -R may bind docker0's address, and a link dropped by a sleeping laptop frees
# its ports in 90 seconds.
cat > /etc/ssh/sshd_config.d/fd-laptop.conf <<CONF
GatewayPorts clientspecified
ClientAliveInterval 30
ClientAliveCountMax 3
CONF
sshd -t
systemctl reload ssh

subnet="$(docker network inspect familydiagram_default -f '{{(index .IPAM.Config 0).Subnet}}')"
ufw allow proto tcp from "$subnet" to 172.17.0.1 port "$ports" comment "$tag"
