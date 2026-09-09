#!/bin/bash
# Makes a dev certificate authority and a certificate for the review sandbox
# host, into the directory given (default web/certs, gitignored). Trust the CA
# once on the phone; keep the directory so the trust survives restarts.
#   web/devcerts.sh [dir] [host]
set -e
DIR="${1:-$(dirname "$0")/certs}"; HOST="${2:-turin.local}"
mkdir -p "$DIR" && cd "$DIR"
[ -f dev-ca.key ] || openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -keyout dev-ca.key -out dev-ca.crt \
  -subj "/CN=Family Diagram Dev CA" -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign"
openssl req -newkey rsa:2048 -nodes -keyout "$HOST.key" -out "$HOST.csr" -subj "/CN=$HOST"
printf "subjectAltName=DNS:%s,DNS:localhost,IP:127.0.0.1\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n" "$HOST" > ext.cnf
openssl x509 -req -in "$HOST.csr" -CA dev-ca.crt -CAkey dev-ca.key -CAcreateserial -days 825 -out "$HOST.crt" -extfile ext.cnf
rm -f "$HOST.csr" ext.cnf dev-ca.srl
echo "certificates in $DIR"
