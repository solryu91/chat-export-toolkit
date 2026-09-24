from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any


CONVERSATION_RE = re.compile(r"^conversations-\d+\.json$")


def digest_entry(archive: zipfile.ZipFile, entry_name: str) -> str:
    digest = hashlib.sha256()
    with archive.open(entry_name) as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory ChatGPT-export attachments for selected conversations.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("title_pattern", help="Case-insensitive regex matched against conversation titles")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    title_pattern = re.compile(args.title_pattern, re.IGNORECASE)
    rows: list[dict[str, Any]] = []

    with zipfile.ZipFile(args.archive) as archive:
        names = set(archive.namelist())
        member_info = {info.filename: info for info in archive.infolist()}
        filename_map: dict[str, str] = {}
        if "conversation_asset_file_names.json" in names:
            with archive.open("conversation_asset_file_names.json") as handle:
                raw_map = json.load(handle)
            if isinstance(raw_map, dict):
                filename_map = {str(k): str(v) for k, v in raw_map.items()}

        conversations: list[dict[str, Any]] = []
        for member in sorted(name for name in names if CONVERSATION_RE.match(name)):
            with archive.open(member) as handle:
                payload = json.load(handle)
            if isinstance(payload, list):
                conversations.extend(item for item in payload if isinstance(item, dict))

        for conversation in conversations:
            title = str(conversation.get("title") or "Untitled")
            if not title_pattern.search(title):
                continue
            mapping = conversation.get("mapping")
            if not isinstance(mapping, dict):
                continue
            seen: set[tuple[str, str]] = set()
            for node in mapping.values():
                if not isinstance(node, dict):
                    continue
                message = node.get("message")
                if not isinstance(message, dict):
                    continue
                metadata = message.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                attachments = metadata.get("attachments")
                if not isinstance(attachments, list):
                    continue
                for attachment in attachments:
                    if not isinstance(attachment, dict):
                        continue
                    attachment_id = str(attachment.get("id") or attachment.get("file_id") or "")
                    original_name = str(attachment.get("name") or "")
                    key = (attachment_id, original_name)
                    if key in seen:
                        continue
                    seen.add(key)
                    expected_entry = f"{attachment_id}.dat" if attachment_id else ""
                    present = expected_entry in names
                    info = member_info.get(expected_entry)
                    rows.append(
                        {
                            "conversation_title": title,
                            "conversation_id": conversation.get("conversation_id") or conversation.get("id"),
                            "updated_at_epoch": conversation.get("update_time"),
                            "message_id": message.get("id"),
                            "role": ((message.get("author") or {}).get("role") if isinstance(message.get("author"), dict) else None),
                            "attachment_id": attachment_id,
                            "attachment_name": original_name,
                            "mime_type": attachment.get("mime_type"),
                            "declared_size": attachment.get("size"),
                            "zip_entry": expected_entry,
                            "zip_present": present,
                            "export_mapped_name": filename_map.get(expected_entry),
                            "zip_size": info.file_size if info else None,
                            "sha256": digest_entry(archive, expected_entry) if present else None,
                        }
                    )

    rows.sort(key=lambda row: (str(row["conversation_title"]), str(row["attachment_name"])))
    json_path = args.output_dir / "ai_asset_inventory.json"
    tsv_path = args.output_dir / "ai_asset_inventory.tsv"
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    fieldnames = list(rows[0]) if rows else ["conversation_title", "conversation_id", "attachment_name", "zip_present"]
    with tsv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({
        "selected_assets": len(rows),
        "present_in_export": sum(1 for row in rows if row["zip_present"]),
        "missing_from_export": sum(1 for row in rows if not row["zip_present"]),
        "json": str(json_path),
        "tsv": str(tsv_path),
    }, indent=2))


if __name__ == "__main__":
    main()
