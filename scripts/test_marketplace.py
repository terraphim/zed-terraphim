"""Real file and Git tests for publication guards; no mocked network calls."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

import marketplace
import catalog
import publish_github


class MarketplaceGuards(unittest.TestCase):
    def test_checksums_are_exact_and_duplicates_fail_closed(self):
        sha = hashlib.sha256(b"content").hexdigest()
        self.assertEqual(marketplace.checksums(f"{sha}  server\n"), {"server": sha})
        for text in [
            f"{sha}  server\n{sha}  server\n",
            "bad  server\n",
            f"{sha}  ../server\n",
            "",
        ]:
            with self.subTest(text=text), self.assertRaises(marketplace.GateError):
                marketplace.checksums(text)

    def test_raw_binary_hash_and_magic_are_required(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "binary"
            # Read a real installed Mach-O/ELF executable, not a pretend binary.
            source = Path("/bin/sh").resolve()
            path.write_bytes(source.read_bytes())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertGreater(marketplace.verify_binary(path, digest)["bytes"], 0)
            with self.assertRaises(marketplace.GateError):
                marketplace.verify_binary(path, "0" * 64)
            path.write_bytes(b"<html>download failed</html>")
            with self.assertRaises(marketplace.GateError):
                marketplace.verify_binary(
                    path, hashlib.sha256(path.read_bytes()).hexdigest()
                )

    def test_catalog_rejects_mixed_mcp_and_lsp_and_rc(self):
        manifest = {
            "id": "terraphim",
            "version": "0.2.0",
            "language_servers": {"lsp": {}},
            "context_servers": {"terraphim": {}},
        }
        with self.assertRaisesRegex(marketplace.GateError, "MCP"):
            marketplace.catalog_manifest(manifest, "v0.2.0")
        manifest.pop("context_servers")
        manifest["id"] = "terraphim-lsp"
        marketplace.catalog_manifest(manifest, "v0.2.0")
        with self.assertRaisesRegex(marketplace.GateError, "stable"):
            marketplace.catalog_manifest(manifest, "v0.2.0-rc.1")

    def test_source_ancestry_requires_exact_base_and_public_repo(self):
        sha = "a" * 40
        marketplace.source_ancestry(
            {"private": False},
            {"merge_base_commit": {"sha": sha}, "status": "ahead"},
            sha,
        )
        for repo, compare in [
            ({"private": True}, {}),
            (
                {"private": False},
                {"merge_base_commit": {"sha": "b" * 40}, "status": "ahead"},
            ),
            (
                {"private": False},
                {"merge_base_commit": {"sha": sha}, "status": "diverged"},
            ),
        ]:
            with self.assertRaises(marketplace.GateError):
                marketplace.source_ancestry(repo, compare, sha)

    def test_stale_qualification_does_not_authorize_catalog(self):
        with self.assertRaises(marketplace.GateError):
            marketplace.qualification("a" * 40, "b" * 40, "https://example.com/proof")
        with self.assertRaises(marketplace.GateError):
            marketplace.qualification("a" * 40, "a" * 40, "file:///private/proof")
        marketplace.qualification("a" * 40, "a" * 40, "https://example.com/proof")

    def test_receipt_cannot_be_reused_for_another_source_or_tag(self):
        receipt = {
            "status": "PASS",
            "source": "a" * 40,
            "tag": "v0.2.0",
            "catalog": True,
        }
        marketplace.validate_receipt(receipt, "a" * 40, "v0.2.0", catalog=True)
        for sha, tag in [("b" * 40, "v0.2.0"), ("a" * 40, "v0.2.1")]:
            with self.assertRaises(marketplace.GateError):
                marketplace.validate_receipt(receipt, sha, tag, catalog=True)
        receipt["catalog"] = False
        with self.assertRaises(marketplace.GateError):
            marketplace.validate_receipt(receipt, "a" * 40, "v0.2.0", catalog=True)


class CatalogEdits(unittest.TestCase):
    def test_insert_update_and_no_unrelated_table_change(self):
        text = '[alpha]\nsubmodule = "extensions/alpha"\nversion = "1.0.0"\n\n[zulu]\nsubmodule = "extensions/zulu"\nversion = "2.0.0"\n'
        changed = catalog.registry_entry(text, "terraphim-lsp", "0.2.0")
        self.assertIn(
            '[terraphim-lsp]\nsubmodule = "extensions/terraphim-lsp"\nversion = "0.2.0"',
            changed,
        )
        self.assertTrue(changed.startswith("[alpha]"))
        self.assertLess(changed.index("[terraphim-lsp]"), changed.index("[zulu]"))
        self.assertEqual(
            catalog.registry_entry(changed, "terraphim-lsp", "0.2.0"), changed
        )
        self.assertIn(
            'version = "0.3.0"',
            catalog.registry_entry(changed, "terraphim-lsp", "0.3.0"),
        )

    def test_rejects_existing_entry_with_conflicting_path(self):
        with self.assertRaises(marketplace.GateError):
            catalog.registry_entry(
                '[terraphim]\nsubmodule="extensions/other"\nversion="0.2.0"\n',
                "terraphim",
                "0.3.0",
            )

    def test_real_git_catalog_diff_is_exactly_one_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def git(*args):
                return subprocess.check_output(
                    ["git", *args], cwd=root, text=True
                ).strip()

            git("init", "-q")
            (root / "extensions.toml").write_text(
                '[alpha]\nsubmodule = "extensions/alpha"\nversion = "1.0.0"\n'
            )
            (root / ".gitmodules").write_text(
                '[submodule "extensions/alpha"]\n\tpath = extensions/alpha\n\turl = https://github.com/example/alpha\n'
            )
            git("add", ".")
            git(
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "baseline",
            )
            source = git("rev-parse", "HEAD")
            catalog.prepare(
                root, "terraphim-lsp", "0.2.0", "terraphim/zed-terraphim", source
            )
            self.assertEqual(
                set(git("diff", "--cached", "--name-only").splitlines()),
                {".gitmodules", "extensions.toml", "extensions/terraphim-lsp"},
            )
            self.assertIn(
                "160000 " + source,
                git("ls-files", "--stage", "extensions/terraphim-lsp"),
            )
            with self.assertRaisesRegex(marketplace.GateError, "clean"):
                catalog.prepare(
                    root, "terraphim-lsp", "0.2.0", "terraphim/zed-terraphim", source
                )


class ReleaseArtifactGuards(unittest.TestCase):
    def test_published_package_binding_and_tamper_refusal(self):
        from test_package_qualification import Fixture

        fixture = Fixture(self)
        fixture.qualify()
        fixture.verify()
        with self.assertRaises(marketplace.GateError):
            publish_github.verify_package(
                fixture.artifacts, fixture.tag, "b" * 40, root=fixture.root
            )
        fixture.packaged.tarball.write_bytes(b"changed")
        with self.assertRaises(marketplace.GateError):
            fixture.verify()

    def test_retired_autonomous_submission_refuses_before_remote_actions(self):
        result = subprocess.run(
            [
                "python3",
                str(marketplace.ROOT / "scripts/submit_catalog.py"),
                "--tag",
                "v0.2.0",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("human maintainer", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
