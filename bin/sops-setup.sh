#!/bin/bash
# Make this checkout able to read the encrypted files under private/, and make
# `git diff` show what changed in them instead of a wall of ciphertext.
#
#   bin/sops-setup.sh /path/to/your.agekey
#
# The key is never copied into the repo. Put its path in SOPS_AGE_KEY_FILE in
# your shell profile as well, so the app can read the prompts when it runs.
set -e

KEY="${1:?usage: bin/sops-setup.sh /path/to/your.agekey}"
[ -f "$KEY" ] || { echo "no key at $KEY"; exit 1; }

command -v sops >/dev/null || { echo "install sops first: brew install sops age"; exit 1; }

git config diff.sops.textconv "sops -d"
git config diff.sops.cachetextconv false

echo "git diff will now decrypt private/ files (see .gitattributes)"
echo "add this to your shell profile:"
echo "  export SOPS_AGE_KEY_FILE=$KEY"
