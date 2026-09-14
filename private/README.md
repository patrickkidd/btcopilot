# private/ — the files only this project's machines can read

Everything here is encrypted in place with sops and an age key. The committed
bytes are ciphertext; the working copy is ciphertext too, and only the running
app and the tools decrypt it.

| what | where |
|---|---|
| the coach's real wording, the scribe's, the naming of groups, the tool meanings | `prompts/` |
| the owner's rulings, the evidence behind them, the store's own spec | `oracle/` |
| the text every prompt produced before it became a file, kept so a change is caught | `goldens.json` |

## Reading and writing

    export SOPS_AGE_KEY_FILE=/path/to/your.agekey    # never inside a repo
    sops private/prompts/agent.prompty                # opens decrypted, saves encrypted
    sops -d private/oracle/rulings.md                 # read it out

`bin/sops-setup.sh /path/to/your.agekey` also teaches `git diff` to decrypt, so
a change to a ruling reads as the changed line rather than a changed blob.

## Running without a key

Nothing is decrypted when a module loads — a prompt is read the first time it is
asked for. So the app, the migration chain and the test run all start on a
machine with no key at all. A test run with no key uses the open-source prompts
and says so on stderr; the tests that assert the private wording skip.

The app itself never falls back. Ask it for a prompt it cannot decrypt and it
fails, loudly, rather than quietly coaching with the wrong words.

## Which key opens it

`.sops.yaml` names the public keys that may read these files, one per machine.
Adding a machine means adding its public key there and running
`sops updatekeys` over the tree. Removing one means taking the key out and
rotating anything it could have read.

Today there is one key and it is a throwaway for development, kept outside every
repo in the sandbox folder. Patrick's own key and the new box's key replace it.

## The rule this exists for

No real names, emails, case identifiers or clinical content in any repo. Files
that hold those do not belong here either, encrypted or not — they live in
`fd-corpus/private`, outside every repo. `btcopilot/tests/chat/test_noprivatepeople.py`
fails if one arrives.
