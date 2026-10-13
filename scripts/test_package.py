#!/usr/bin/env python3
"""Tests for scripts/package.py and the pure parts of scripts/publish.py.

Run from the repository root:

    python3 -m unittest discover -s scripts -p 'test_*.py'

The tests use real files in temporary directories and a small fixture in
place of the built wasm, so they need neither cargo nor the network.
"""
import contextlib
import hashlib
import io
import pathlib
import shutil
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import package  # noqa: E402
import publish  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAKE_WASM = b"\x00asm\x01\x00\x00\x00 fixture standing in for the built extension"


class ReadVersion(unittest.TestCase):
    def test_reads_top_level_version(self):
        text = 'id = "terraphim"\nversion = "1.2.3"\n\n[lib]\nversion = "9.9.9"\n'
        self.assertEqual(package.read_version(text), "1.2.3")

    def test_ignores_version_inside_a_table(self):
        text = 'id = "terraphim"\n[lib]\nversion = "9.9.9"\n'
        with self.assertRaises(package.PackageError):
            package.read_version(text)

    def test_repository_manifest_matches_cargo_version(self):
        manifest = package.read_version((ROOT / "extension.toml").read_text())
        cargo = package.read_version((ROOT / "Cargo.toml").read_text(), table="package")
        self.assertEqual(manifest, cargo)


class CheckTag(unittest.TestCase):
    def test_final_tag(self):
        self.assertFalse(package.check_tag("v0.2.0", "0.2.0"))

    def test_rc_tag_is_prerelease(self):
        self.assertTrue(package.check_tag("v0.2.0-rc.1", "0.2.0"))
        self.assertTrue(package.check_tag("v0.2.0-rc.12", "0.2.0"))

    def test_rejects_mismatched_version(self):
        with self.assertRaisesRegex(package.PackageError, "does not match"):
            package.check_tag("v0.2.1", "0.2.0")

    def test_rejects_malformed_tags(self):
        for tag in ["0.2.0", "v0.2", "v0.2.0-beta.1", "v0.2.0-rc", "v0.2.0-rc.1x", "v0.2.0 "]:
            with self.subTest(tag=tag), self.assertRaises(package.PackageError):
                package.check_tag(tag, "0.2.0")


class Package(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wasm = pathlib.Path(self.tmp.name) / "built.wasm"
        self.wasm.write_bytes(FAKE_WASM)

    def run_package(self, name):
        out = pathlib.Path(self.tmp.name) / name
        return package.package(ROOT, self.wasm, out)

    def test_two_runs_give_identical_bytes(self):
        first = self.run_package("a")
        second = self.run_package("b")
        self.assertEqual(first.tarball.read_bytes(), second.tarball.read_bytes())
        self.assertEqual(first.sums.read_bytes(), second.sums.read_bytes())

    def test_each_tag_is_deterministic_and_named_after_the_tag(self):
        version = package.read_version((ROOT / "extension.toml").read_text())
        for tag in [f"v{version}-rc.1", f"v{version}"]:
            with self.subTest(tag=tag):
                first = package.package(ROOT, self.wasm, pathlib.Path(self.tmp.name) / f"{tag}-a", tag=tag)
                second = package.package(ROOT, self.wasm, pathlib.Path(self.tmp.name) / f"{tag}-b", tag=tag)
                self.assertEqual(first.tarball.name, f"terraphim-zed-{tag[1:]}.tar.gz")
                self.assertEqual(first.tarball.read_bytes(), second.tarball.read_bytes())
                self.assertEqual(first.sums.read_bytes(), second.sums.read_bytes())
                digest = hashlib.sha256(first.tarball.read_bytes()).hexdigest()
                self.assertEqual(first.sums.read_text(), f"{digest}  {first.tarball.name}\n")
                # The directory inside stays terraphim-zed-<version>/: it is
                # stripped on install, and Zed reads the version from extension.toml.
                with tarfile.open(first.tarball) as tar:
                    self.assertEqual(tar.getnames()[0], f"terraphim-zed-{version}")

    def test_gzip_header_has_no_timestamp_or_name(self):
        data = self.run_package("a").tarball.read_bytes()
        self.assertEqual(data[:2], b"\x1f\x8b")
        self.assertEqual(data[4:8], b"\x00\x00\x00\x00", "gzip MTIME must be zero")
        self.assertEqual(data[3] & 0x08, 0, "gzip header must not carry a file name")

    def test_archive_layout_and_contents(self):
        result = self.run_package("a")
        version = package.read_version((ROOT / "extension.toml").read_text())
        top = f"terraphim-zed-{version}"
        self.assertEqual(result.tarball.name, f"{top}.tar.gz")
        with tarfile.open(result.tarball) as tar:
            members = tar.getmembers()
            names = [m.name for m in members]
            self.assertEqual(
                names,
                [top] + [f"{top}/{n}" for n in ["LICENSE", "README.md", "extension.toml", "extension.wasm"]],
            )
            for m in members:
                self.assertEqual((m.uid, m.gid, m.uname, m.gname), (0, 0, "", ""), m.name)
                self.assertEqual(m.mtime, package.FIXED_MTIME, m.name)
                self.assertEqual(m.mode, 0o755 if m.isdir() else 0o644, m.name)
            self.assertEqual(tar.extractfile(f"{top}/extension.wasm").read(), FAKE_WASM)
            for name in ["LICENSE", "README.md", "extension.toml"]:
                self.assertEqual(tar.extractfile(f"{top}/{name}").read(), (ROOT / name).read_bytes(), name)
        staged = result.tarball.parent / top
        self.assertEqual(
            sorted(p.name for p in staged.iterdir()),
            ["LICENSE", "README.md", "extension.toml", "extension.wasm"],
        )

    def test_sha256sums_verifies_the_tarball(self):
        result = self.run_package("a")
        digest = hashlib.sha256(result.tarball.read_bytes()).hexdigest()
        self.assertEqual(result.sums.read_text(), f"{digest}  {result.tarball.name}\n")

    def test_tag_mismatch_fails_before_writing(self):
        out = pathlib.Path(self.tmp.name) / "c"
        with self.assertRaises(package.PackageError):
            package.package(ROOT, self.wasm, out, tag="v9.9.9")
        self.assertFalse(out.exists())

    def test_rejects_wasm_that_is_not_wasm(self):
        self.wasm.write_bytes(b"not wasm")
        with self.assertRaisesRegex(package.PackageError, "not a WebAssembly"):
            self.run_package("a")


class PackageCli(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.wasm = self.tmp / "built.wasm"
        self.wasm.write_bytes(FAKE_WASM)
        self.version = package.read_version((ROOT / "extension.toml").read_text())

    def test_packages_a_given_wasm_for_a_matching_rc_tag(self):
        out = self.tmp / "out"
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = package.main(["--tag", f"v{self.version}-rc.1", "--wasm", str(self.wasm), "--out-dir", str(out)])
        self.assertEqual(code, 0)
        self.assertTrue((out / f"terraphim-zed-{self.version}-rc.1.tar.gz").is_file())
        self.assertIn(f"terraphim-zed-{self.version}-rc.1.tar.gz", stdout.getvalue())

    def test_mismatched_tag_exits_non_zero_without_output(self):
        out = self.tmp / "out"
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = package.main(["--tag", "v0.0.1", "--wasm", str(self.wasm), "--out-dir", str(out)])
        self.assertEqual(code, 1)
        self.assertIn("does not match", stderr.getvalue())
        self.assertFalse(out.exists())


class PublishTags(unittest.TestCase):
    API_TAGS = (
        {"name": "v0.2.0-rc.1", "commit": {"sha": "abc"}},
        {"name": "v0.2.0", "commit": {"sha": "abc"}},
        {"name": "v0.2.0-rc.10", "commit": {"sha": "abc"}},
        {"name": "v0.2.0-rc.2", "commit": {"sha": "abc"}},
        {"name": "v0.1.0", "commit": {"sha": "old"}},
        {"name": "experiment", "commit": {"sha": "abc"}},
    )

    def test_selects_release_tags_at_commit(self):
        self.assertEqual(
            publish.release_tags_at("abc", self.API_TAGS, "0.2.0"),
            ["v0.2.0-rc.1", "v0.2.0-rc.2", "v0.2.0-rc.10", "v0.2.0"],
        )

    def test_ignores_tags_for_another_version(self):
        self.assertEqual(publish.release_tags_at("old", self.API_TAGS, "0.2.0"), [])

    def test_multipart_body_carries_file(self):
        body, content_type = publish.multipart("attachment", "SHA256SUMS", b"abc  x\n")
        boundary = content_type.split("boundary=", 1)[1]
        self.assertTrue(content_type.startswith("multipart/form-data; boundary="))
        self.assertIn(b'name="attachment"; filename="SHA256SUMS"', body)
        self.assertIn(b"\r\n\r\nabc  x\n\r\n", body)
        self.assertTrue(body.endswith(f"--{boundary}--\r\n".encode()))

    def test_asset_plan(self):
        names = ["a.tar.gz", "SHA256SUMS"]
        self.assertEqual(publish.asset_plan([], names), ([], names))
        both = [{"id": 1, "name": "a.tar.gz"}, {"id": 2, "name": "SHA256SUMS"}]
        self.assertEqual(publish.asset_plan(both, names), ([], []))
        # A partial upload is replaced as a whole so the checksum file always
        # describes the tarball next to it.
        self.assertEqual(publish.asset_plan(both[:1], names), ([1], names))


if __name__ == "__main__":
    unittest.main()
