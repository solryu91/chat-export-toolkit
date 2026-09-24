from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


CONVERSATION_RE = re.compile(r"^conversations-\d+\.json$")


def iso_time(value: Any) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def text_from_part(part: Any) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, (int, float, bool)):
        return str(part)
    if isinstance(part, dict):
        # These are the most common text-bearing shapes in ChatGPT exports.
        for key in ("text", "content", "caption", "name", "title"):
            value = part.get(key)
            if isinstance(value, str):
                return value
        return ""
    return ""


def message_text(message: dict[str, Any] | None) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if isinstance(parts, list):
        return "\n".join(filter(None, (text_from_part(part).strip() for part in parts))).strip()
    text = content.get("text")
    return text.strip() if isinstance(text, str) else ""


def active_branch(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = conversation.get("mapping")
    current = conversation.get("current_node")
    if not isinstance(mapping, dict) or not isinstance(current, str):
        return []

    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    while isinstance(current, str) and current and current not in seen:
        seen.add(current)
        node = mapping.get(current)
        if not isinstance(node, dict):
            break
        nodes.append(node)
        current = node.get("parent")
    nodes.reverse()
    return nodes


def normalize_message(node: dict[str, Any]) -> dict[str, Any] | None:
    message = node.get("message")
    if not isinstance(message, dict):
        return None
    author = message.get("author")
    role = author.get("role") if isinstance(author, dict) else None
    if role not in {"user", "assistant", "system", "tool"}:
        role = str(role or "unknown")
    content = message.get("content")
    content_type = content.get("content_type") if isinstance(content, dict) else None
    text = message_text(message)
    metadata = message.get("metadata")
    attachments: list[str] = []
    if isinstance(metadata, dict):
        raw_attachments = metadata.get("attachments")
        if isinstance(raw_attachments, list):
            for attachment in raw_attachments:
                if isinstance(attachment, dict):
                    label = attachment.get("name") or attachment.get("id") or attachment.get("file_id")
                    if isinstance(label, str):
                        attachments.append(label)
    if not text and not attachments and role in {"system", "tool"}:
        return None
    return {
        "node_id": node.get("id"),
        "message_id": message.get("id"),
        "role": role,
        "content_type": content_type,
        "create_time": iso_time(message.get("create_time")),
        "text": text,
        "attachments": attachments,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_conversations(archive: zipfile.ZipFile, members: Iterable[str]) -> Iterable[tuple[str, dict[str, Any]]]:
    for member in members:
        with archive.open(member) as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            continue
        for conversation in payload:
            if isinstance(conversation, dict):
                yield member, conversation


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize a ChatGPT export for backlog analysis.")
    parser.add_argument("archive", type=Path, help="Path to the ChatGPT export ZIP")
    parser.add_argument("output_dir", type=Path, help="Directory for generated private analysis files")
    parser.add_argument(
        "--omit-message-text",
        action="store_true",
        help="Omit message bodies and first/last user excerpts from the JSONL index",
    )
    parser.add_argument(
        "--include-source-path",
        action="store_true",
        help="Record the full archive path in the manifest (off by default for privacy)",
    )
    args = parser.parse_args()

    if not args.archive.is_file():
        parser.error(f"archive does not exist or is not a file: {args.archive}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    index_path = args.output_dir / "conversations_index.jsonl"
    titles_path = args.output_dir / "conversation_titles.tsv"
    manifest_path = args.output_dir / "import_manifest.json"

    counts: Counter[str] = Counter()
    earliest: str | None = None
    latest: str | None = None
    title_rows: list[tuple[str, str, str, str, int, int]] = []

    with zipfile.ZipFile(args.archive) as archive, index_path.open("w", encoding="utf-8") as index_file:
        members = sorted(name for name in archive.namelist() if CONVERSATION_RE.match(name))
        for source_member, conversation in iter_conversations(archive, members):
            normalized_messages = []
            for node in active_branch(conversation):
                normalized = normalize_message(node)
                if normalized is not None:
                    normalized_messages.append(normalized)

            user_messages = [m for m in normalized_messages if m["role"] == "user" and m["text"]]
            assistant_messages = [m for m in normalized_messages if m["role"] == "assistant" and m["text"]]
            created = iso_time(conversation.get("create_time"))
            updated = iso_time(conversation.get("update_time"))
            if created and (earliest is None or created < earliest):
                earliest = created
            if updated and (latest is None or updated > latest):
                latest = updated

            record = {
                "conversation_id": conversation.get("conversation_id") or conversation.get("id"),
                "title": conversation.get("title") or "Untitled",
                "created_at": created,
                "updated_at": updated,
                "archived": bool(conversation.get("is_archived")),
                "starred": bool(conversation.get("is_starred")),
                "pinned_at": iso_time(conversation.get("pinned_time")),
                "model": conversation.get("default_model_slug"),
                "source_member": source_member,
                "active_branch_message_count": len(normalized_messages),
                "user_message_count": len(user_messages),
                "assistant_message_count": len(assistant_messages),
                "first_user_text": user_messages[0]["text"] if user_messages else "",
                "last_user_text": user_messages[-1]["text"] if user_messages else "",
                "messages": normalized_messages,
            }
            if args.omit_message_text:
                record["first_user_text"] = ""
                record["last_user_text"] = ""
                for message in record["messages"]:
                    message["text"] = ""
            index_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            title_rows.append(
                (
                    str(record["title"]).replace("\t", " ").replace("\n", " "),
                    created or "",
                    updated or "",
                    str(record["conversation_id"] or ""),
                    len(user_messages),
                    len(assistant_messages),
                )
            )
            counts["conversations"] += 1
            counts["messages"] += len(normalized_messages)
            counts["user_messages"] += len(user_messages)
            counts["assistant_messages"] += len(assistant_messages)
            counts["archived"] += int(record["archived"])
            counts["starred"] += int(record["starred"])

    title_rows.sort(key=lambda row: (row[2], row[0]), reverse=True)
    with titles_path.open("w", encoding="utf-8", newline="") as title_file:
        title_file.write("title\tcreated_at\tupdated_at\tconversation_id\tuser_messages\tassistant_messages\n")
        for row in title_rows:
            title_file.write("\t".join(map(str, row)) + "\n")

    manifest = {
        "source_archive_name": args.archive.name,
        "source_sha256": sha256_file(args.archive),
        "normalized_at": dt.datetime.now(tz=dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "conversation_members": members,
        "conversation_count": counts["conversations"],
        "active_branch_message_count": counts["messages"],
        "user_message_count": counts["user_messages"],
        "assistant_message_count": counts["assistant_messages"],
        "archived_count": counts["archived"],
        "starred_count": counts["starred"],
        "earliest_created_at": earliest,
        "latest_updated_at": latest,
        "notes": [
            "Only the active branch ending at each conversation's current_node was imported.",
            "Raw attachments were not extracted; attachment labels, when present, were retained in message metadata.",
            "The original ZIP archive was read-only and was not modified.",
            "The full source archive path was omitted unless --include-source-path was requested.",
        ],
    }
    if args.include_source_path:
        manifest["source_archive"] = str(args.archive.resolve())
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
