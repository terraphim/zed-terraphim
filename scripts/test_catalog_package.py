"""Real source and file regressions for the separate catalog package."""

from pathlib import Path
import shutil
import tempfile
import tomllib
import unittest

import catalog
import catalog_package
import marketplace
import package


class CatalogPackageTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in ["Cargo.toml", "Cargo.lock", "extension.toml", "LICENSE"]:
            shutil.copyfile(package.ROOT / name, root / name)
        shutil.copytree(
            package.ROOT / catalog_package.PATH,
            root / catalog_package.PATH,
            ignore=shutil.ignore_patterns("target", "extension.wasm"),
        )
        return root

    def test_shared_source_and_legacy_identity_are_preserved(self):
        manifest = catalog_package.validate_source(package.ROOT)
        self.assertEqual(manifest["id"], "terraphim-lsp")
        self.assertFalse(manifest.get("context_servers"))

    def test_catalog_entry_points_to_the_manifest_subdirectory(self):
        changed = catalog.registry_entry(
            "", "terraphim-lsp", "0.2.0", catalog_package.PATH
        )
        entry = tomllib.loads(changed)["terraphim-lsp"]
        self.assertEqual(entry["path"], catalog_package.PATH)
        self.assertEqual(entry["submodule"], "extensions/terraphim-lsp")
        self.assertEqual(
            catalog.registry_entry(
                changed, "terraphim-lsp", "0.2.0", catalog_package.PATH
            ),
            changed,
        )

    def test_subdirectory_rejects_traversal_and_absolute_paths(self):
        for value in [
            "../other",
            "/tmp/other",
            "catalog/../other",
            "catalog//other",
            "catalog\\other",
        ]:
            with self.subTest(value=value), self.assertRaises(marketplace.GateError):
                catalog.registry_entry("", "terraphim-lsp", "0.2.0", value)

    def test_catalog_can_add_only_passive_json_without_changing_legacy(self):
        root = self.fixture()
        legacy = (root / "extension.toml").read_bytes()
        manifest = root / catalog_package.PATH / "extension.toml"
        manifest.write_text(manifest.read_text().replace(
            'languages = ["Markdown"]',
            'languages = ["Markdown", "JSON", "JSONC"]\nlanguage_ids = { JSON = "json", JSONC = "jsonc" }'))
        catalog_package.validate_source(root)
        self.assertEqual((root / "extension.toml").read_bytes(), legacy)
        text = manifest.read_text()
        for changed in [text.replace('JSONC = "jsonc"', 'JSONC = "markdown"'),
                        text.replace('["Markdown", "JSON", "JSONC"]', '["Markdown", "JSON", "Python"]')]:
            manifest.write_text(changed)
            with self.assertRaisesRegex(marketplace.GateError, "only passive"):
                catalog_package.validate_source(root)

    def test_catalog_rejects_retargeting_an_existing_manifest_directory(self):
        text = '[terraphim-lsp]\nsubmodule = "extensions/terraphim-lsp"\npath = "other"\nversion = "0.2.0"\n'
        with self.assertRaisesRegex(
            marketplace.GateError, "different extension directory"
        ):
            catalog.registry_entry(text, "terraphim-lsp", "0.2.0", catalog_package.PATH)

    def test_catalog_refuses_extra_capabilities(self):
        root = self.fixture()
        path = root / catalog_package.PATH / "extension.toml"
        path.write_text(
            path.read_text()
            + '\n[[capabilities]]\nkind = "process:exec"\ncommand = "*"\nargs = ["**"]\n'
        )
        with self.assertRaisesRegex(marketplace.GateError, "capabilities"):
            catalog_package.validate_source(root)

    def test_symlink_cannot_escape_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "source"
            root.mkdir()
            (root / "catalog").symlink_to(root.parent, target_is_directory=True)
            with self.assertRaisesRegex(marketplace.GateError, "escapes"):
                marketplace.read_manifest(root, "catalog")

    def test_catalog_refuses_mcp_enablement(self):
        root = self.fixture()
        path = root / catalog_package.PATH / "Cargo.toml"
        path.write_text(
            path.read_text().replace(
                'default = ["public-catalog"]', 'default = ["mcp"]'
            )
        )
        with self.assertRaisesRegex(marketplace.GateError, "disable MCP"):
            catalog_package.validate_source(root)

    def test_catalog_refuses_a_separate_adapter_implementation(self):
        root = self.fixture()
        path = root / catalog_package.PATH / "Cargo.toml"
        path.write_text(path.read_text().replace("../../src/lib.rs", "src/lib.rs"))
        with self.assertRaisesRegex(marketplace.GateError, "existing adapter"):
            catalog_package.validate_source(root)

    def test_dependency_drift_is_refused(self):
        root = self.fixture()
        path = root / catalog_package.PATH / "Cargo.lock"
        path.write_text(path.read_text() + "\n")
        with self.assertRaisesRegex(marketplace.GateError, "lockfile"):
            catalog_package.validate_source(root)

    def test_manifest_version_mismatch_is_refused(self):
        root = self.fixture()
        path = root / catalog_package.PATH / "extension.toml"
        path.write_text(
            path.read_text().replace('version = "0.2.0"', 'version = "0.3.0"')
        )
        with self.assertRaisesRegex(marketplace.GateError, "versions"):
            catalog_package.validate_source(root)


if __name__ == "__main__":
    unittest.main()
