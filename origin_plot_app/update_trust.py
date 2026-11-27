"""update_trust.py - whose signature this copy of the app accepts on an update.

    TRUSTED_KEYS = {key id: the PUBLIC Ed25519 key, base64 of its 32 bytes}

Only public keys are written here. The private key never enters this repository, a release, a build log or a coding
agent: it stays with the person who publishes releases and is read from a file (or a secret of the release job) at the
moment a release is signed (tools/sign_release.py).

The table is EMPTY until the publisher adds the production key. With an empty table no signed update verifies, so:
  - a 'friends' build installs no update at all (it accepts signed updates only) - that is the safe state;
  - the 'owner' profile keeps updating from its own repository as before, and says that the update is not verified.

HOW THE PUBLISHER ADDS THE PRODUCTION KEY (once)
  1. On the publishing computer, outside any repository folder, create the key pair, for example:
         openssl genpkey -algorithm ed25519 -out ops_release_signing_key.pem
     Keep that file private (a password manager, or the secret store of the release job). Never commit it.
  2. Print its public half:
         python tools/sign_release.py public-key --private-key-file ops_release_signing_key.pem
     It prints one line like   "ops-release-2026a": "mX3...=",
  3. Paste that line between the braces below, commit, and publish the next release from a copy that holds it.
  Rotating: add the new line beside the old one, publish a release signed with the OLD key (so installed copies learn
  the new key), then sign later releases with the new key and remove the old line.

This file is replaced only by an update whose signature was verified with the keys that are in it NOW
(self_update.PROTECTED): an unsigned update, an imported project, a template or an AI repair cannot change it.
A key id that begins with "TEST-" is refused outside the tests (see update_verify.verify_manifest).
"""

TRUSTED_KEYS = {
}
