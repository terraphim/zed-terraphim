"""Real Git patch generation and refusal tests for human catalog handoff."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import catalog
import marketplace
import prepare_catalog
from test_package_qualification import Fixture


class CatalogHandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.root = self.directory / "catalog"
        self.root.mkdir()
        self.git("init", "-q")
        (self.root / ".gitmodules").write_text("")
        (self.root / "extensions.toml").write_text("")
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "empty catalog",
        )
        self.source = self.git("rev-parse", "HEAD")
        self.receipt = {
            "status": "PASS",
            "catalog": True,
            "source": self.source,
            "tag": "v0.2.0",
            "extensionId": "terraphim-lsp",
            "extensionPath": "catalog/terraphim-lsp",
            "repository": "terraphim/zed-terraphim",
            "version": "0.2.0",
            "qualificationUrl": "https://example.invalid/fixture-only",
        }

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def prepare(self):
        catalog.prepare(
            self.root,
            "terraphim-lsp",
            "0.2.0",
            "terraphim/zed-terraphim",
            self.source,
            "catalog/terraphim-lsp",
        )

    def test_actual_patch_applies_to_clean_catalog_without_any_remote_mutation(self):
        self.prepare()
        before_refs = self.git("show-ref")
        output = self.directory / "handoff"
        result = prepare_catalog.write_handoff(self.root, self.receipt, output)
        self.assertEqual(result["status"], "HUMAN_SUBMISSION_REQUIRED")
        self.assertFalse(result["remoteMutationPerformed"])
        self.assertEqual(self.git("show-ref"), before_refs)
        self.assertEqual(
            result["changedFiles"],
            [".gitmodules", "extensions.toml", "extensions/terraphim-lsp"],
        )
        patch = (output / "catalog.patch").read_bytes()
        self.assertEqual(result["patchSha256"], hashlib.sha256(patch).hexdigest())
        self.assertEqual(json.loads((output / "submission.json").read_text()), result)
        clone = self.directory / "human-fork"
        subprocess.run(["git", "clone", "-q", str(self.root), str(clone)], check=True)
        subprocess.run(
            ["git", "apply", "--index", str(output / "catalog.patch")],
            cwd=clone,
            check=True,
        )
        self.assertEqual(
            (clone / "extensions.toml").read_bytes(),
            (self.root / "extensions.toml").read_bytes(),
        )
        self.assertFalse((output / "pr-body.md").exists())

    def test_release_identity_uses_explicit_tagged_source_not_tooling_checkout(self):
        self.git("tag", "v0.2.0")
        self.assertEqual(prepare_catalog.validate_release_source(
            self.root, self.receipt, "v0.2.0"), self.source)
        (self.root / "extensions.toml").write_text("changed source")
        with self.assertRaisesRegex(marketplace.GateError, "clean tagged"):
            prepare_catalog.validate_release_source(self.root, self.receipt, "v0.2.0")
        self.git("checkout", "--", "extensions.toml")
        (self.root / "later.txt").write_text("tooling may follow release")
        self.git("add", "later.txt")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "later tooling")
        with self.assertRaisesRegex(marketplace.GateError, "tagged"):
            prepare_catalog.validate_release_source(self.root, self.receipt, "v0.2.0")

    def test_locked_upstream_inputs_fail_closed_and_preserve_exact_bytes(self):
        with self.assertRaisesRegex(marketplace.GateError, "lockfile"):
            prepare_catalog.locked_inputs(self.root)
        manifest = self.root / "package.json"
        lock = self.root / "pnpm-lock.yaml"
        manifest.write_text(json.dumps({"volta": {"node": "24.21.0"}}))
        lock.write_text("lockfileVersion: '9.0'\n")
        saved = prepare_catalog.locked_inputs(self.root)
        prepare_catalog.verify_locked_inputs(self.root, saved)
        lock.write_text("lockfileVersion: '10.0'\n")
        with self.assertRaisesRegex(marketplace.GateError, "changed"):
            prepare_catalog.verify_locked_inputs(self.root, saved)
        lock.unlink()
        lock.symlink_to(manifest)
        with self.assertRaisesRegex(marketplace.GateError, "regular"):
            prepare_catalog.locked_inputs(self.root)

    def test_actual_release_archive_and_receipt_are_required(self):
        fixture = Fixture(self, extension_path="catalog/terraphim-lsp")
        fixture.qualify()
        data = [fixture.packaged.tarball.read_bytes(), fixture.packaged.sums.read_bytes(),
                fixture.receipt.read_bytes()]
        result = prepare_catalog.validate_released_package(
            fixture.root, fixture.proof, fixture.tag, *data)
        self.assertEqual(result["archive"]["name"], fixture.packaged.tarball.name)
        for index in range(3):
            changed = list(data)
            if index == 2:
                value = json.loads(changed[index]); value["source"] = "f" * 40
                changed[index] = json.dumps(value).encode()
            else:
                changed[index] += b"changed"
            with self.subTest(index=index), self.assertRaises(marketplace.GateError):
                prepare_catalog.validate_released_package(
                    fixture.root, fixture.proof, fixture.tag, *changed)

    def test_runtime_declaration_change_requires_tooling_review(self):
        (self.root / "package.json").write_text(json.dumps({"volta": {"node": "25.0.0"}}))
        (self.root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
        with self.assertRaisesRegex(marketplace.GateError, "runtime"):
            prepare_catalog.locked_inputs(self.root)

    def test_unrelated_staged_changes_are_refused(self):
        self.prepare()
        (self.root / "unrelated.txt").write_text("must not submit")
        self.git("add", "unrelated.txt")
        with self.assertRaisesRegex(marketplace.GateError, "unrelated"):
            prepare_catalog.write_handoff(
                self.root, self.receipt, self.directory / "handoff"
            )

    def test_existing_handoff_is_not_overwritten(self):
        self.prepare()
        output = self.directory / "handoff"
        prepare_catalog.write_handoff(self.root, self.receipt, output)
        with self.assertRaisesRegex(marketplace.GateError, "fresh"):
            prepare_catalog.write_handoff(self.root, self.receipt, output)


if __name__ == "__main__":
    unittest.main()
