from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import release_audit  # noqa: E402


class ReleaseAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def codes(self) -> set[str]:
        return {item.code for item in release_audit.audit_tree(self.root)}

    def test_clean_tree_passes(self) -> None:
        (self.root / "module.py").write_text("print('clean')\n", encoding="utf-8")
        self.assertEqual([], release_audit.audit_tree(self.root))

    def test_absolute_windows_paths_are_rejected(self) -> None:
        private_path = "D:" + "\\" + "private" + "\\" + "result.json"
        (self.root / "note.txt").write_text(private_path, encoding="utf-8")
        self.assertIn("absolute_path", self.codes())

    def test_private_material_names_are_rejected(self) -> None:
        prohibited = "sealed" + "_query" + ".csv"
        (self.root / prohibited).write_text("id\n", encoding="utf-8")
        self.assertIn("sealed_or_evaluator_material", self.codes())

    def test_token_and_private_key_are_rejected(self) -> None:
        token = "ghp" + "_" + ("A" * 36)
        key = "-----BEGIN " + "PRIVATE KEY-----"
        (self.root / ".env").write_text(token + "\n" + key, encoding="utf-8")
        codes = self.codes()
        self.assertIn("github_token", codes)
        self.assertIn("private_key", codes)

    def test_oversized_file_is_rejected(self) -> None:
        (self.root / "large.txt").write_bytes(b"x" * 32)
        findings = release_audit.audit_tree(self.root, max_bytes=16)
        self.assertIn("oversized_file", {item.code for item in findings})

    def test_suspicious_artifact_and_third_party_directory_are_rejected(self) -> None:
        vendor = self.root / "vendor"
        vendor.mkdir()
        (vendor / "weights.pt").write_bytes(b"model")
        codes = self.codes()
        self.assertIn("suspicious_third_party_directory", codes)
        self.assertIn("suspicious_artifact_extension", codes)

    def test_legal_and_citation_text_are_content_scan_exempt(self) -> None:
        example = "C:" + "\\" + "Users" + "\\" + "example"
        (self.root / "LICENSE").write_text(example, encoding="utf-8")
        (self.root / "CITATION.cff").write_text(example, encoding="utf-8")
        self.assertEqual([], release_audit.audit_tree(self.root))


if __name__ == "__main__":
    unittest.main()
