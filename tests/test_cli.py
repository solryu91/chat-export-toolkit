from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "examples" / "synthetic_export"


def run_python(*arguments: object) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, *(str(argument) for argument in arguments)],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def build_synthetic_archive(destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(FIXTURE_ROOT.iterdir()):
            if source.is_file():
                archive.write(source, source.name)


class CommandLineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temporary_directory.name)
        self.archive_path = self.temp_root / "synthetic-export.zip"
        build_synthetic_archive(self.archive_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_normalize_active_branch_without_disclosing_source_path(self) -> None:
        output = self.temp_root / "normalized"
        result = run_python("mine_chat_export.py", self.archive_path, output)

        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((output / "import_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_archive_name"], "synthetic-export.zip")
        self.assertNotIn("source_archive", manifest)
        self.assertEqual(manifest["conversation_count"], 1)
        self.assertEqual(manifest["active_branch_message_count"], 3)

        records = [
            json.loads(line)
            for line in (output / "conversations_index.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(records), 1)
        self.assertEqual([message["message_id"] for message in records[0]["messages"]], [
            "message-1",
            "message-2",
            "message-3",
        ])
        self.assertNotIn("alternate branch", json.dumps(records))

    def test_message_omission_blanks_bodies_and_excerpts(self) -> None:
        output = self.temp_root / "metadata-only"
        result = run_python(
            "mine_chat_export.py",
            self.archive_path,
            output,
            "--omit-message-text",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((output / "conversations_index.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(record["first_user_text"], "")
        self.assertEqual(record["last_user_text"], "")
        self.assertTrue(all(message["text"] == "" for message in record["messages"]))
        self.assertEqual(record["messages"][0]["attachments"], ["garden-notes.txt"])

    def test_inventory_finds_synthetic_attachment_without_extracting_it(self) -> None:
        output = self.temp_root / "inventory"
        result = run_python(
            "inventory_chat_assets.py",
            self.archive_path,
            output,
            "garden",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        inventory = json.loads((output / "ai_asset_inventory.json").read_text(encoding="utf-8"))
        self.assertEqual(len(inventory), 1)
        self.assertEqual(inventory[0]["attachment_id"], "file-synthetic-001")
        self.assertTrue(inventory[0]["zip_present"])
        expected_digest = hashlib.sha256(
            (FIXTURE_ROOT / "file-synthetic-001.dat").read_bytes()
        ).hexdigest()
        self.assertEqual(inventory[0]["sha256"], expected_digest)
        self.assertFalse((output / "file-synthetic-001.dat").exists())

    def test_review_selects_conversation_and_roles(self) -> None:
        output = self.temp_root / "review-source"
        normalize = run_python("mine_chat_export.py", self.archive_path, output)
        self.assertEqual(normalize.returncode, 0, normalize.stderr)

        review = run_python(
            "review_threads.py",
            output / "conversations_index.jsonl",
            "garden",
            "--roles",
            "assistant",
        )
        self.assertEqual(review.returncode, 0, review.stderr)
        self.assertIn("TITLE: Synthetic garden planning", review.stdout)
        self.assertIn("[ASSISTANT]", review.stdout)
        self.assertNotIn("[USER]", review.stdout)


if __name__ == "__main__":
    unittest.main()
