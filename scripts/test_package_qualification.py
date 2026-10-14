"""Real Git, deterministic archives and filesystem publication binding tests.

Preflight fixtures are parser inputs, not claims of a network/publication run.
The minimal WASM tests packaging integrity, not native runtime acceptance.
"""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

import marketplace
import package
import package_qualification as qualification
import publish_github


VERSION = package.read_version((package.ROOT / "extension.toml").read_text())


class Fixture:
    def __init__(self, case, tag=None, extension_path=""):
        temporary = tempfile.TemporaryDirectory()
        case.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "source"
        self.root.mkdir()
        for name in package.FILES:
            (self.root / name).write_bytes((package.ROOT / name).read_bytes())
        self.extension_path = extension_path
        if extension_path:
            nested = self.root / extension_path
            nested.mkdir(parents=True)
            for name in package.FILES:
                (nested / name).write_bytes((package.ROOT / extension_path / name).read_bytes())
        (self.root / "build-source.rs").write_text("// Tracked non-packaged source\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.commit("fixture baseline")
        self.source = self.git("rev-parse", "HEAD")
        self.version = package.read_version((self.root / extension_path / "extension.toml").read_text())
        self.tag = tag or f"v{self.version}"
        self.git("tag", self.tag)
        self.artifacts = self.base / "artifacts"
        (self.artifacts / "public-preflight").mkdir(parents=True)
        self.proof = {
            "status": "PASS", "source": self.source, "tag": self.tag,
            "version": self.version, "extensionId": "terraphim-lsp" if extension_path else "terraphim",
            "extensionPath": extension_path, "catalog": bool(extension_path),
            "repository": "example/zed-terraphim",
        }
        if extension_path:
            # Parser fixtures only: these declarations do not attest to a native run.
            native = {
                "schema": 1, "status": "PASS", "scope": "stock-zed-source",
                "qualifiedCommit": self.source, "extensionId": "terraphim-lsp",
                "extensionPath": extension_path, "version": self.version,
                "sourceInstallWasm": {"sha256": "1" * 64, "bytes": 562871},
                "server": {"releaseTag": "terraphim_lsp-v1.22.0-rc.7",
                           "sha256": "2" * 64, "bytes": 13000000},
                "checks": {name: "PASS" for name in marketplace.NATIVE_CHECKS},
                "savedOutputs": [{"name": "saved-fixture.md", "sha256": "3" * 64, "bytes": 73}],
            }
            self.native_data = json.dumps(native).encode()
            self.native_path = self.artifacts / "public-preflight/native-qualification.json"
            self.native_path.write_bytes(self.native_data)
            self.proof["qualificationUrl"] = "https://raw.githubusercontent.com/example/zed-terraphim/" + "a" * 40 + "/docs/native.json"
            self.proof["publicLsp"] = {"tag": native["server"]["releaseTag"]}
            self.proof["assets"] = [{"sha256": native["server"]["sha256"], "bytes": native["server"]["bytes"]}]
            self.proof["nativeQualification"] = marketplace.native_evidence_record(
                self.native_data, self.proof["qualificationUrl"], self.proof["repository"],
                self.source, {"version": self.version}, self.proof["publicLsp"], self.proof["assets"])
        self.preflight = self.artifacts / "public-preflight/preflight.json"
        self.preflight.write_text(json.dumps(self.proof))
        self.wasm = self.base / "ci-built.wasm"
        self.wasm.write_bytes(b"\x00asm\x01\x00\x00\x00")
        self.packaged = package.package(
            self.root, self.wasm, self.artifacts / "release-dist", self.tag,
            **({"extension_path": extension_path} if extension_path else {})
        )
        self.receipt = self.artifacts / "release-dist" / qualification.RECEIPT

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def commit(self, message):
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", message)

    def qualify(self):
        return qualification.qualify(self.root, self.artifacts, self.tag, self.wasm,
                                     **({"extension_path": self.extension_path} if self.extension_path else {}))

    def verify(self):
        return publish_github.verify_package(
            self.artifacts, self.tag, self.source, root=self.root,
            **({"extension_path": self.extension_path} if self.extension_path else {})
        )

    def refresh_checksum(self):
        digest = hashlib.sha256(self.packaged.tarball.read_bytes()).hexdigest()
        self.packaged.sums.write_text(f"{digest}  {self.packaged.tarball.name}\n")

    def repack(self, name, data):
        staged = self.packaged.tarball.parent / f"terraphim-zed-{self.version}"
        (staged / name).write_bytes(data)
        package.write_tarball(staged, self.packaged.tarball)
        self.refresh_checksum()


class PackageQualification(unittest.TestCase):
    def test_exact_ci_wasm_source_and_both_tags_are_bound(self):
        for tag in [f"v{VERSION}", f"v{VERSION}-rc.1"]:
            with self.subTest(tag=tag):
                fixture = Fixture(self, tag)
                result = fixture.qualify()
                preflight, files = fixture.verify()
                self.assertEqual(result["source"], fixture.source)
                self.assertIs(result["sourceTreeDirty"], False)
                self.assertEqual(preflight, fixture.proof)
                self.assertEqual(files[-1], fixture.receipt)
                self.assertEqual(result["archive"]["sha256"], hashlib.sha256(
                    fixture.packaged.tarball.read_bytes()).hexdigest())
                self.assertEqual(result["entries"]["extension.wasm"],
                                 qualification.record(fixture.wasm.read_bytes()))
                for name in package.FILES:
                    self.assertEqual(result["entries"][name],
                                     qualification.record((fixture.root / name).read_bytes()))

    def test_repacked_wrong_id_with_matching_checksums_is_rejected(self):
        fixture = Fixture(self)
        fixture.qualify()
        original = (fixture.root / "extension.toml").read_bytes()
        replacement = original.replace(b'id = "terraphim"', b'id = "different-extension"', 1)
        self.assertNotEqual(original, replacement)
        fixture.repack("extension.toml", replacement)
        with self.assertRaisesRegex(marketplace.GateError, "Packaged source.*extension.toml"):
            fixture.verify()
        # Even issuance cannot bless a changed source file by recomputing hashes.
        fixture.receipt.unlink()
        with self.assertRaisesRegex(marketplace.GateError, "Packaged source"):
            fixture.qualify()
        self.assertFalse(fixture.receipt.exists())

    def test_repacked_readme_or_license_cannot_be_requalified(self):
        for name in ["README.md", "LICENSE"]:
            with self.subTest(name=name):
                fixture = Fixture(self)
                fixture.repack(name, b"Unrelated package contents\n")
                with self.assertRaisesRegex(marketplace.GateError, "Packaged source"):
                    fixture.qualify()
                self.assertFalse(fixture.receipt.exists())

    def test_changed_wasm_and_self_consistent_sums_do_not_reuse_ci_receipt(self):
        fixture = Fixture(self)
        original_receipt = fixture.qualify()
        # A second valid minimal module, with an empty custom section.
        fixture.repack("extension.wasm", b"\x00asm\x01\x00\x00\x00\x00\x01\x00")
        with self.assertRaisesRegex(marketplace.GateError, "CI qualification"):
            fixture.verify()
        self.assertEqual(json.loads(fixture.receipt.read_bytes()), original_receipt)
        fixture.receipt.unlink()
        with self.assertRaisesRegex(marketplace.GateError, "tested CI module"):
            fixture.qualify()
        self.assertFalse(fixture.receipt.exists())

    def test_tracked_runtime_source_change_is_rejected(self):
        fixture = Fixture(self)
        fixture.qualify()
        (fixture.root / "build-source.rs").write_text("// Unqualified runtime change\n")
        with self.assertRaisesRegex(marketplace.GateError, "clean tracked source"):
            fixture.verify()

    def test_head_and_local_tag_must_still_match_receipt(self):
        fixture = Fixture(self)
        fixture.qualify()
        (fixture.root / "build-source.rs").write_text("// Another revision\n")
        fixture.git("add", ".")
        fixture.commit("another fixture revision")
        with self.assertRaisesRegex(marketplace.GateError, "Local tag"):
            fixture.verify()
        # Moving only this disposable fixture's tag still cannot reuse old evidence.
        fixture.git("tag", "-f", fixture.tag)
        with self.assertRaisesRegex(marketplace.GateError, "publication source"):
            fixture.verify()

    def test_preflight_identity_and_exact_bytes_must_match(self):
        for key, value in [("source", "a" * 40), ("tag", f"v{VERSION}-rc.1"),
                           ("version", f"{VERSION}-rc.1"), ("extensionId", "another-id")]:
            with self.subTest(key=key):
                fixture = Fixture(self)
                fixture.qualify()
                changed = {**fixture.proof, key: value}
                fixture.preflight.write_text(json.dumps(changed))
                with self.assertRaises(marketplace.GateError):
                    fixture.verify()
        fixture = Fixture(self)
        fixture.qualify()
        fixture.preflight.write_text(json.dumps(fixture.proof, indent=2))
        with self.assertRaisesRegex(marketplace.GateError, "CI qualification"):
            fixture.verify()

    def test_missing_or_altered_qualification_fails_and_cannot_be_overwritten(self):
        fixture = Fixture(self)
        with self.assertRaises(FileNotFoundError):
            fixture.verify()
        fixture.qualify()
        original = fixture.receipt.read_bytes()
        with self.assertRaises(FileExistsError):
            fixture.qualify()
        self.assertEqual(fixture.receipt.read_bytes(), original)
        changed = json.loads(original)
        changed["sourceTreeDirty"] = True
        fixture.receipt.write_text(json.dumps(changed))
        with self.assertRaisesRegex(marketplace.GateError, "CI qualification"):
            fixture.verify()

    def test_archive_rejects_symlink_duplicate_and_wrong_root_type(self):
        for mutation in ["symlink", "duplicate", "root-file"]:
            with self.subTest(mutation=mutation):
                fixture = Fixture(self)
                fixture.qualify()
                data = fixture.packaged.tarball.read_bytes()
                with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as old:
                    entries = [(member, old.extractfile(member).read() if member.isfile() else None)
                               for member in old.getmembers()]
                with tarfile.open(fixture.packaged.tarball, "w:gz") as changed:
                    for member, content in entries:
                        if mutation == "symlink" and member.name.endswith("README.md"):
                            member.type = tarfile.SYMTYPE
                            member.linkname = "/etc/passwd"
                            member.size = 0
                            content = None
                        if mutation == "root-file" and member.isdir():
                            member.type = tarfile.REGTYPE
                        changed.addfile(member, io.BytesIO(content) if content is not None else None)
                    if mutation == "duplicate":
                        member, content = entries[-1]
                        changed.addfile(member, io.BytesIO(content))
                fixture.refresh_checksum()
                with self.assertRaisesRegex(marketplace.GateError, "layout"):
                    fixture.verify()

    def test_publisher_snapshot_keeps_verified_bytes_if_original_changes(self):
        fixture = Fixture(self)
        fixture.qualify()
        original = fixture.packaged.tarball.read_bytes()
        with publish_github.qualified_snapshot(
            fixture.artifacts, fixture.tag, fixture.source, fixture.root
        ) as (_, files):
            fixture.packaged.tarball.write_bytes(b"subsequent build output")
            fixture.receipt.unlink()
            self.assertEqual(files[0].read_bytes(), original)
            publish_github.verify_package(files[0].parent.parent, fixture.tag,
                                          fixture.source, fixture.root)
            snapshot_path = files[0]
        self.assertFalse(snapshot_path.exists())


if __name__ == "__main__":
    unittest.main()
