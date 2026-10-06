#!/bin/sh
# One-time box changes for the laptop's monitoring link (doc/MONITORING.md),
# run as root from /var/www/btcopilot/deploy with the laptop key's public half:
#   sh box/setup.sh "ssh-ed25519 AAAA... fd-laptop"
# Safe to run again: each step replaces its own earlier result. Root's own
# ssh access and settings are left as they are: the link signs in as fdlink.
set -eu
key="$(echo "$1" | cut -d" " -f1,2)"
here="$(dirname "$0")"
user=fdlink
ports="18428,14318"
dropin=/etc/ssh/sshd_config.d/fd-laptop.conf

install -m 0755 "$here/fd-logpull" /usr/local/bin/fd-logpull

# A user with no password whose only use is the link; systemd-journal lets
# fd-logpull read the whole journal.
id "$user" >/dev/null 2>&1 || useradd --system --create-home --shell /bin/sh "$user"
usermod -aG systemd-journal "$user"
home="$(getent passwd "$user" | cut -d: -f6)"
install -d -m 700 -o "$user" -g "$user" "$home/.ssh"
echo "restrict,port-forwarding,permitopen=\"127.0.0.1:5432\",permitlisten=\"172.17.0.1:18428\",permitlisten=\"172.17.0.1:14318\",command=\"/usr/local/bin/fd-logpull\" $key fd-laptop" > "$home/.ssh/authorized_keys"
chown "$user:$user" "$home/.ssh/authorized_keys"
chmod 600 "$home/.ssh/authorized_keys"

# For fdlink only: -R may bind docker0's address, and a link dropped by a
# sleeping laptop frees its ports in 90 seconds. The closing "Match all"
# keeps the block from capturing the main file's lines that follow the include.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/fd-laptop.conf" <<CONF
Match User $user
    GatewayPorts clientspecified
    ClientAliveInterval 30
    ClientAliveCountMax 3
Match all
CONF
sed "s#^Include /etc/ssh/sshd_config.d/\*\.conf\$#& $tmp/fd-laptop.conf#" /etc/ssh/sshd_config > "$tmp/sshd_config"
grep -q " $tmp/fd-laptop.conf\$" "$tmp/sshd_config"
sshd -t -f "$tmp/sshd_config"
sshd -T -f "$tmp/sshd_config" -C "user=$user,host=laptop,addr=127.0.0.1" | grep -qx "gatewayports clientspecified"
sshd -T -f "$tmp/sshd_config" -C "user=root,host=laptop,addr=127.0.0.1" | grep -qx "gatewayports no"
install -m 644 "$tmp/fd-laptop.conf" "$dropin"
sshd -t
systemctl reload ssh

subnet="$(docker network inspect familydiagram_default -f '{{(index .IPAM.Config 0).Subnet}}')"
ufw allow proto tcp from "$subnet" to 172.17.0.1 port "$ports" comment fd-laptop
