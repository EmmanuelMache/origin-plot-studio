"""sign_release.py - the publisher's side of a signed release (the app's side is origin_plot_app/update_verify.py).

    python tools/sign_release.py make-manifest <zip> --version 5.59.0 --key-id ops-release-2026a
          writes manifest.json beside the zip: schema, version, artifact name, SHA-256, size, systems, minimum Python,
          date, key id - as canonical JSON (sorted keys, no spaces, one line feed at the end).
    python tools/sign_release.py sign <manifest.json> --private-key-file <path>
          writes manifest.sig beside it: base64 of the Ed25519 signature over the exact bytes of manifest.json.
          Without --private-key-file the key is taken from the environment variable OPS_RELEASE_SIGNING_KEY
          (the key itself as PEM or as base64 of its 32 bytes, or the path of a file that holds it).
    python tools/sign_release.py verify <folder>
          checks manifest.json, manifest.sig and the zip in that folder exactly as the app will
          (with the keys in origin_plot_app/update_trust.py; --public-key <base64> checks against one given key instead).
    python tools/sign_release.py bundle <folder>
          packs the three files into ONE signed bundle zip, for people who get the update as a file by hand
          (Help > 'Install an update from a zip file' accepts it).
    python tools/sign_release.py public-key --private-key-file <path> [--key-id NAME]
          prints the PUBLIC half as the line to paste into origin_plot_app/update_trust.py. Prints nothing private.
    python tools/sign_release.py gen-test-key <folder>
          FOR TESTS ONLY: writes a throw-away key pair (key id TEST-...). The app refuses TEST- keys outside the tests.

THE PRIVATE KEY is read from a file or the environment at the moment of signing. It is never written by this tool
(except the throw-away test key), never printed, never put into the repository, a release or a log. Keep it out of
the reach of coding agents and of ordinary pull-request jobs: only the release job (or you, by hand) signs.
A release on GitHub carries the three files as assets named exactly manifest.json, manifest.sig and the zip.
"""
import os, sys, json, base64, argparse, datetime, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "origin_plot_app"))
import update_verify as uv

ENV_KEY = "OPS_RELEASE_SIGNING_KEY"


def _crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        return Ed25519PrivateKey, serialization
    except Exception:
        raise SystemExit("The Python package 'cryptography' is needed to sign a release:  python -m pip install cryptography")


def make_manifest(zip_path, version, key_id, platform=("windows",), min_python="3.9", created=None, notes="", tag=""):
    """The manifest of a release zip as a dict (see update_verify.check_fields for what each field must look like)."""
    zip_path = str(zip_path)
    m = {"schema": uv.SCHEMA, "version": str(version).lstrip("vV"), "artifact": os.path.basename(zip_path), "sha256": uv.sha256_file(zip_path), "size": os.path.getsize(zip_path),
         "platform": list(platform), "min_python": str(min_python), "created": created or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "key_id": str(key_id)}
    if notes: m["notes"] = str(notes)[:4000]
    if tag: m["tag"] = str(tag)
    uv.check_fields(m); uv.check_archive(zip_path)                 # what the app would refuse is refused here already
    return m


def load_private_key(path=None):
    """The signing key from a file, or from OPS_RELEASE_SIGNING_KEY (the key, or the path of its file). PEM (PKCS#8, as
    'openssl genpkey -algorithm ed25519' writes it) or base64 of the 32 key bytes."""
    Ed25519PrivateKey, serialization = _crypto()
    if path: data = Path(path).read_bytes()
    else:
        v = os.environ.get(ENV_KEY, "")
        if not v.strip(): raise SystemExit(f"No signing key: give --private-key-file <path>, or set the environment variable {ENV_KEY}.")
        data = Path(v.strip()).read_bytes() if (len(v) < 1000 and "\n" not in v.strip() and os.path.isfile(v.strip())) else v.encode("utf-8")
    try:
        if b"-----BEGIN" in data:
            pw = os.environ.get(ENV_KEY + "_PASSWORD")
            key = serialization.load_pem_private_key(data, password=pw.encode("utf-8") if pw else None)
        else:
            raw = base64.b64decode(data.strip(), validate=True)
            if len(raw) != 32: raise ValueError("not 32 bytes")
            key = Ed25519PrivateKey.from_private_bytes(raw)
    except Exception as e:
        raise SystemExit(f"The signing key could not be read ({type(e).__name__}). It must be an Ed25519 private key (PEM or base64).")      # never the content
    if not isinstance(key, Ed25519PrivateKey): raise SystemExit("The signing key is not an Ed25519 key.")
    return key


def public_b64(private_key):
    _, serialization = _crypto()
    return base64.b64encode(private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode("ascii")


def sign_bytes(manifest_bytes, private_key):
    """base64 signature (with a line feed) over the exact manifest bytes."""
    return base64.b64encode(private_key.sign(bytes(manifest_bytes))) + b"\n"


def write_bundle(folder, out=None):
    """One zip with manifest.json, manifest.sig and the artifact at its top level (stored, not compressed again)."""
    folder = Path(folder); mb = (folder / uv.MANIFEST_NAME).read_bytes(); m = json.loads(mb.decode("utf-8"))
    art = folder / m["artifact"]
    out = Path(out) if out else folder / (Path(m["artifact"]).stem + "_signed_bundle.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        z.writestr(uv.MANIFEST_NAME, mb); z.writestr(uv.SIG_NAME, (folder / uv.SIG_NAME).read_bytes()); z.write(art, m["artifact"])
    return out


def verify_folder(folder, public_key=None, current_version="0.0"):
    """Verify a release folder the way the app does. Returns the manifest; raises update_verify.VerifyError."""
    folder = Path(folder); mb = (folder / uv.MANIFEST_NAME).read_bytes(); sb = (folder / uv.SIG_NAME).read_bytes()
    trusted = None
    if public_key:
        trusted = {json.loads(mb.decode("utf-8")).get("key_id", ""): public_key}
    m = uv.verify_manifest(mb, sb, trusted=trusted)
    # the release may be for another system and another Python than the one this tool runs on: only the fields and the version are judged here
    uv.check_compat(m, current_version, platform=m["platform"][0] if "any" not in m["platform"] else None, python=tuple(int(x) for x in m["min_python"].split(".")))
    uv.verify_artifact(str(folder / m["artifact"]), m); uv.check_archive(str(folder / m["artifact"]))
    return m


def gen_test_key(folder):
    """A throw-away key pair for tests. Refused inside this repository, so it cannot be committed by accident."""
    Ed25519PrivateKey, serialization = _crypto()
    folder = Path(folder).resolve()
    if folder == ROOT or ROOT in folder.parents: raise SystemExit("A test key is not written inside the repository. Choose a folder outside it (a temporary folder).")
    folder.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate(); kid = "TEST-" + os.urandom(4).hex()
    priv = folder / "TEST_ONLY_private_key.pem"
    priv.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    try: os.chmod(priv, 0o600)
    except OSError: pass
    (folder / "TEST_ONLY_public_key.json").write_text(json.dumps({"key_id": kid, "public_key": public_b64(key)}, indent=1), encoding="utf-8")
    return kid, priv, public_b64(key)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make, sign and check the manifest of a release of Origin Plot Studio.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("make-manifest"); a.add_argument("zip"); a.add_argument("--version", required=True); a.add_argument("--key-id", required=True)
    a.add_argument("--platform", nargs="+", default=["windows"], choices=list(uv.PLATFORMS)); a.add_argument("--min-python", default="3.9"); a.add_argument("--notes", default=""); a.add_argument("--tag", default=""); a.add_argument("--out", default="")
    a = sub.add_parser("sign"); a.add_argument("manifest"); a.add_argument("--private-key-file", default="")
    a = sub.add_parser("verify"); a.add_argument("folder"); a.add_argument("--public-key", default="")
    a = sub.add_parser("bundle"); a.add_argument("folder"); a.add_argument("--out", default="")
    a = sub.add_parser("public-key"); a.add_argument("--private-key-file", default=""); a.add_argument("--key-id", default="")
    a = sub.add_parser("gen-test-key"); a.add_argument("folder")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "make-manifest":
            m = make_manifest(args.zip, args.version, args.key_id, args.platform, args.min_python, notes=args.notes, tag=args.tag)
            out = Path(args.out) if args.out else Path(args.zip).resolve().parent / uv.MANIFEST_NAME
            out.write_bytes(uv.canonical(m)); print(f"Wrote {out}  (version {m['version']}, {m['size']} bytes, sha256 {m['sha256'][:16]}..., key id {m['key_id']})")
        elif args.cmd == "sign":
            mp = Path(args.manifest); mb = mp.read_bytes(); m = uv.check_fields(json.loads(mb.decode("utf-8")))
            if mb != uv.canonical(m): raise SystemExit("manifest.json is not in its canonical form (it was edited by hand?). Make it again with make-manifest.")
            key = load_private_key(args.private_key_file or None); pub = public_b64(key)
            (mp.parent / uv.SIG_NAME).write_bytes(sign_bytes(mb, key))
            known = uv.trusted_keys().get(m["key_id"])
            print(f"Wrote {mp.parent / uv.SIG_NAME}")
            if known is None: print(f"NOTE: the key id '{m['key_id']}' is not in origin_plot_app/update_trust.py yet. No installed app accepts this release until it is (see that file).")
            elif known.strip() != pub: raise SystemExit(f"STOP: the key you signed with is not the key update_trust.py lists as '{m['key_id']}'. Installed apps will refuse this release.")
        elif args.cmd == "verify":
            m = verify_folder(args.folder, args.public_key or None)
            print(f"OK: version {m['version']} ({m['artifact']}) carries a valid signature of the key '{m['key_id']}'" + (" given on the command line." if args.public_key else " that update_trust.py trusts."))
        elif args.cmd == "bundle":
            print(f"Wrote {write_bundle(args.folder, args.out or None)}")
        elif args.cmd == "public-key":
            key = load_private_key(args.private_key_file or None)
            kid = args.key_id or "ops-release-" + datetime.date.today().strftime("%Y") + "a"
            print("Paste this line into TRUSTED_KEYS of origin_plot_app/update_trust.py (it is the PUBLIC key; the private key stays with you):")
            print(f'    "{kid}": "{public_b64(key)}",')
        elif args.cmd == "gen-test-key":
            kid, priv, pub = gen_test_key(args.folder)
            print("=" * 78 + "\nTEST KEY - NOT FOR RELEASES. Never sign a published release with it, never add it to\nupdate_trust.py, never commit it. The app refuses 'TEST-' keys outside its tests.\n" + "=" * 78)
            print(f"key id {kid}\nprivate key file {priv}\npublic key {pub}")
    except uv.VerifyError as e:
        print("NOT ACCEPTED: " + str(e)); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
