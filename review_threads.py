from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path


def compact(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("index", type=Path)
    parser.add_argument("pattern", help="Case-insensitive regex matched against title or conversation ID")
    parser.add_argument("--roles", default="user,assistant")
    parser.add_argument("--message-limit", type=int, default=1800)
    parser.add_argument("--max-conversations", type=int, default=25)
    parser.add_argument("--max-messages", type=int, default=0, help="Limit printed messages per conversation; 0 means all")
    parser.add_argument("--tail", action="store_true", help="Take the last messages when used with --max-messages")
    parser.add_argument("--message-pattern", help="Only show messages matching this regex, plus optional context")
    parser.add_argument("--context", type=int, default=0)
    args = parser.parse_args()

    pattern = re.compile(args.pattern, re.IGNORECASE)
    roles = {role.strip() for role in args.roles.split(",") if role.strip()}
    matches = []
    with args.index.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            haystack = f"{record.get('title', '')}\n{record.get('conversation_id', '')}"
            if pattern.search(haystack):
                matches.append(record)

    matches.sort(key=lambda record: record.get("updated_at") or "", reverse=True)
    for record in matches[: args.max_conversations]:
        print("=" * 100)
        print(f"TITLE: {record.get('title')}")
        print(f"ID: {record.get('conversation_id')}")
        print(f"CREATED: {record.get('created_at')}  UPDATED: {record.get('updated_at')}")
        print(f"MESSAGES: {record.get('active_branch_message_count')}")
        print("-" * 100)
        all_messages = record.get("messages", [])
        selected_indices = [index for index, message in enumerate(all_messages) if message.get("role") in roles]
        if args.message_pattern:
            message_pattern = re.compile(args.message_pattern, re.IGNORECASE)
            matched = []
            for index, message in enumerate(all_messages):
                haystack = f"{message.get('text') or ''}\n{' '.join(map(str, message.get('attachments') or []))}"
                if message_pattern.search(haystack):
                    matched.extend(range(max(0, index - args.context), min(len(all_messages), index + args.context + 1)))
            selected_indices = sorted(set(matched))
        selected_messages = [all_messages[index] for index in selected_indices]
        if args.max_messages > 0:
            selected_messages = selected_messages[-args.max_messages :] if args.tail else selected_messages[: args.max_messages]
        for message in selected_messages:
            role = message.get("role")
            attachments = message.get("attachments") or []
            content = compact(message.get("text") or "", args.message_limit)
            if not content and not attachments:
                continue
            suffix = f" [attachments: {', '.join(map(str, attachments))}]" if attachments else ""
            print(f"[{role.upper()}]{suffix} {content}")
            print()


if __name__ == "__main__":
    main()
