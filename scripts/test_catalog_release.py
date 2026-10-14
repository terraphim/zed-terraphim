"""Cross-variant regressions using actual files, Git and archive processing.

Minimal modules are archive parser inputs; these tests never attest to native
execution or network publication.
"""
import json
import unittest

import catalog_package
import marketplace
import package
import package_qualification
import publish_github
from test_package_qualification import Fixture

CATALOG = "catalog/terraphim-lsp"


class CatalogRelease(unittest.TestCase):
    def test_catalog_archive_is_distinct_and_bound_to_nested_source(self):
        fixture = Fixture(self, extension_path=CATALOG)
        report = fixture.qualify()
        self.assertEqual(report["extensionId"], "terraphim-lsp")
        self.assertEqual(report["extensionPath"], CATALOG)
        self.assertEqual(report["archive"]["name"], "terraphim-lsp-0.2.0.tar.gz")
        fixture.verify()
        second = package.package(fixture.root, fixture.wasm, fixture.base / "again",
                                 fixture.tag, extension_path=CATALOG)
        self.assertEqual(second.tarball.read_bytes(), fixture.packaged.tarball.read_bytes())
        members = package_qualification.inspect_archive(
            second.tarball.read_bytes(), "0.2.0", extension_path=CATALOG)
        for name in package.FILES:
            self.assertEqual(members[name], (fixture.root / CATALOG / name).read_bytes())
        self.assertNotIn("build-receipt.json", members)

    def test_actual_compiled_catalog_wasm_cannot_be_replaced_with_legacy(self):
        fixture = Fixture(self, extension_path=CATALOG)
        catalog_wasm = package.ROOT / CATALOG / "target/wasm32-wasip2/release/zed_terraphim_lsp.wasm"
        legacy_wasm = package.ROOT / "target/wasm32-wasip2/release/zed_terraphim.wasm"
        self.assertNotEqual(catalog_wasm.read_bytes(), legacy_wasm.read_bytes())
        fixture.wasm.write_bytes(catalog_wasm.read_bytes())
        fixture.packaged = package.package(fixture.root, fixture.wasm,
            fixture.artifacts / "release-dist", fixture.tag, extension_path=CATALOG)
        report = fixture.qualify()
        self.assertGreater(report["entries"]["extension.wasm"]["bytes"], 100_000)
        fixture.verify()
        fixture.receipt.unlink()
        with self.assertRaisesRegex(marketplace.GateError, "tested CI module"):
            package_qualification.qualify(fixture.root, fixture.artifacts, fixture.tag,
                                         legacy_wasm, extension_path=CATALOG)

    def test_catalog_stage_archives_actual_checked_module_and_keeps_receipt_separate(self):
        fixture = Fixture(self, extension_path=CATALOG)
        wasm = package.ROOT / CATALOG / "target/wasm32-wasip2/release/zed_terraphim_lsp.wasm"
        output = fixture.base / "catalog-stage"
        result = catalog_package.release(package.ROOT, wasm, output, "v0.2.0")
        staged = json.loads((output / "catalog-build-receipt.json").read_bytes())
        self.assertEqual(staged["extensionId"], "terraphim-lsp")
        self.assertIs(staged["nativeQualified"], False)
        members = package_qualification.inspect_archive(result.tarball.read_bytes(),
                                                         "0.2.0", CATALOG)
        self.assertEqual(members["extension.wasm"], wasm.read_bytes())
        self.assertEqual(set(members), {*package.FILES, "extension.wasm"})
        self.assertEqual(staged["files"]["extension.wasm"],
                         package_qualification.record(wasm.read_bytes())["sha256"])

    def test_release_workflow_routes_only_catalog_bytes_and_original_artifact(self):
        workflow = (package.ROOT / ".github/workflows/release.yml").read_text()
        verify, publish = workflow.split("\n  publish:\n", 1)
        for program in ["catalog_package.py", "package_qualification.py", "marketplace.py"]:
            self.assertIn(f"scripts/{program}", verify)
        self.assertNotIn("scripts/package.py", verify)
        self.assertNotIn("/release/zed_terraphim.wasm", verify)
        self.assertIn("--extension-path catalog/terraphim-lsp", verify)
        self.assertIn("--release-publish \"$PUBLISH_REQUESTED\"", verify)
        self.assertIn("--qualified-commit \"$QUALIFIED_COMMIT\"", verify)
        self.assertIn("--qualification-url \"$QUALIFICATION_URL\"", verify)
        self.assertIn("artifact-id: ${{ steps.package-upload.outputs.artifact-id }}", verify)
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.publish", publish)
        self.assertIn("environment: zed-release", publish)
        self.assertIn("artifact-ids: ${{ needs.verify.outputs.artifact-id }}", publish)
        self.assertIn("--extension-path catalog/terraphim-lsp", publish)
        self.assertNotIn("contents: write", verify)
        self.assertEqual(publish.count("contents: write"), 1)
        self.assertNotRegex(publish, r"(?m)^\s+run:.*(?:cargo|package_qualification|catalog_package)")

    def test_legacy_preflight_cannot_authorize_catalog_upload(self):
        fixture = Fixture(self, extension_path=CATALOG)
        fixture.qualify()
        for changed in [dict(extensionId="terraphim"), dict(extensionPath=""),
                        dict(catalog=False)]:
            fixture.preflight.write_text(json.dumps({**fixture.proof, **changed}))
            with self.subTest(changed=changed), self.assertRaises(marketplace.GateError):
                fixture.verify()

    def test_catalog_cannot_be_relabelled_from_legacy_archive(self):
        fixture = Fixture(self, extension_path=CATALOG)
        legacy = package.package(fixture.root, fixture.wasm, fixture.base / "legacy", fixture.tag)
        fixture.packaged.tarball.write_bytes(legacy.tarball.read_bytes())
        fixture.refresh_checksum()
        with self.assertRaisesRegex(marketplace.GateError, "layout"):
            fixture.qualify()

    def test_catalog_rejects_other_tested_module(self):
        fixture = Fixture(self, extension_path=CATALOG)
        fixture.wasm.write_bytes(b"\x00asm\x01\x00\x00\x00\x00\x01\x00")
        with self.assertRaisesRegex(marketplace.GateError, "tested CI module"):
            fixture.qualify()
        self.assertFalse(fixture.receipt.exists())

    def test_unsupported_path_or_wrong_identity_is_rejected(self):
        fixture = Fixture(self, extension_path=CATALOG)
        for path in ["../other", "/tmp/other", "catalog/../other", "catalog/other"]:
            with self.subTest(path=path), self.assertRaises(package.PackageError):
                package.package(fixture.root, fixture.wasm, fixture.base / "bad", fixture.tag,
                                extension_path=path)
        manifest = fixture.root / CATALOG / "extension.toml"
        manifest.write_text(manifest.read_text().replace('id = "terraphim-lsp"', 'id = "terraphim"'))
        with self.assertRaisesRegex(package.PackageError, "identity"):
            package.package(fixture.root, fixture.wasm, fixture.base / "bad", fixture.tag,
                            extension_path=CATALOG)

    def test_tag_build_can_qualify_without_native_claim_but_cannot_publish(self):
        fixture = Fixture(self, extension_path=CATALOG)
        fixture.proof["catalog"] = False
        fixture.preflight.write_text(json.dumps(fixture.proof))
        report = fixture.qualify()
        self.assertEqual(report["scope"], "Package integrity after CI; native Zed acceptance is separate")
        with self.assertRaisesRegex(marketplace.GateError, "does not authorize catalog"):
            fixture.verify()

    def test_manual_publish_requires_matching_tag_context(self):
        self.assertFalse(marketplace.release_admission("push", "refs/tags/v0.2.0", "v0.2.0", False))
        self.assertTrue(marketplace.release_admission("workflow_dispatch", "refs/tags/v0.2.0", "v0.2.0", True))
        for event, ref in [("push", "refs/tags/v0.2.0"),
                           ("workflow_dispatch", "refs/heads/main"),
                           ("workflow_dispatch", "refs/tags/v0.2.1")]:
            with self.subTest(event=event, ref=ref), self.assertRaises(marketplace.GateError):
                marketplace.release_admission(event, ref, "v0.2.0", True)

    def test_native_receipt_url_is_same_repo_full_commit_json(self):
        good = "https://raw.githubusercontent.com/example/zed-terraphim/" + "a" * 40 + "/docs/native.json"
        self.assertEqual(marketplace.immutable_qualification_url(good, "example/zed-terraphim"), good)
        for changed in [good.replace("a" * 40, "main"), good.replace("example/", "other/"),
                        good.replace("https://", "http://"), good + "?download=1",
                        good.replace("/docs/", "/../"), good.replace(".json", ".md")]:
            with self.subTest(url=changed), self.assertRaises(marketplace.GateError):
                marketplace.immutable_qualification_url(changed, "example/zed-terraphim")

    def test_native_receipt_checks_source_variant_server_and_required_outputs(self):
        fixture = Fixture(self, extension_path=CATALOG)
        original = json.loads(fixture.native_data)
        changes = [("qualifiedCommit", "b" * 40), ("scope", "stock-zed-released-package"),
                   ("extensionId", "terraphim"), ("extensionPath", ""),
                   ("version", "0.3.0"), ("status", "FAIL"),
                   ("sourceInstallWasm", {"sha256": "bad", "bytes": 562871}),
                   ("server", {**original["server"], "sha256": "4" * 64}),
                   ("server", {**original["server"], "releaseTag": "another-version"}),
                   ("checks", {**original["checks"], "dirtyJsonRefusal": "FAIL"}),
                   ("savedOutputs", []),
                   ("savedOutputs", [{"name": "/private/local.md", "sha256": "3" * 64, "bytes": 73}])]
        for key, value in changes:
            changed = {**original, key: value}
            with self.subTest(key=key, value=value), self.assertRaises(marketplace.GateError):
                marketplace.validate_native_qualification(json.dumps(changed).encode(),
                    fixture.source, {"version": "0.2.0"}, fixture.proof["publicLsp"], fixture.proof["assets"])
        for malformed in [b"[]", b"null", b"{}"]:
            with self.subTest(malformed=malformed), self.assertRaises(marketplace.GateError):
                marketplace.validate_native_qualification(malformed, fixture.source,
                    {"version": "0.2.0"}, fixture.proof["publicLsp"], fixture.proof["assets"])

    def test_native_receipt_bytes_are_frozen_separately_from_ci_module(self):
        fixture = Fixture(self, extension_path=CATALOG)
        report = fixture.qualify()
        self.assertNotEqual(report["entries"]["extension.wasm"]["sha256"],
                            fixture.proof["nativeQualification"]["sourceInstallWasm"]["sha256"])
        fixture.verify()
        # Semantically identical JSON has different bytes and cannot reuse proof.
        fixture.native_path.write_text(json.dumps(json.loads(fixture.native_data), indent=2))
        with self.assertRaisesRegex(marketplace.GateError, "receipt differs"):
            fixture.verify()
        fixture.native_path.unlink()
        with self.assertRaises(FileNotFoundError):
            fixture.verify()

    def test_actual_rust_contract_selects_public_catalog_without_changing_legacy(self):
        public = marketplace.release_contract(package.ROOT, CATALOG)
        legacy = marketplace.release_contract(package.ROOT, "")
        self.assertEqual(public["tag"], legacy["tag"])
        self.assertEqual(public["assets"], legacy["assets"])
        self.assertEqual(len(public["assets"]), 6)
        self.assertTrue(legacy["gitea"].startswith("https://git.terraphim.cloud/"))
        self.assertIs(legacy["path_fallback"], True)
        self.assertEqual(legacy["github_discovery"], "api_listing")

    def test_catalog_snapshot_freezes_exact_qualified_bytes(self):
        fixture = Fixture(self, extension_path=CATALOG)
        fixture.qualify()
        original = fixture.packaged.tarball.read_bytes()
        with publish_github.qualified_snapshot(fixture.artifacts, fixture.tag,
                fixture.source, fixture.root, extension_path=CATALOG) as (_, files):
            fixture.packaged.tarball.write_bytes(b"other")
            self.assertEqual(files[0].name, "terraphim-lsp-0.2.0.tar.gz")
            self.assertEqual(files[0].read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
