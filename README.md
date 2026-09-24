# Chat Export Toolkit

Small, dependency-free Python utilities for inspecting a ChatGPT data export locally:

- `mine_chat_export.py` reconstructs each conversation's active branch and creates a JSON Lines index, a title table, and an import manifest.
- `inventory_chat_assets.py` inventories attachment metadata for conversations selected by title.
- `review_threads.py` prints selected conversations from a previously generated index.

This is an independent utility and is not an official OpenAI product.

## Privacy first

A ChatGPT export can contain highly sensitive personal data. The generated indexes are usually **more searchable than the original archive**, so treat them as confidential.

- Work on a trusted local device.
- Put the export and all generated output outside this repository.
- Do not commit, upload, paste, or attach real exports or generated reports to issues.
- Delete generated plaintext when you no longer need it, using a method appropriate for your storage system and backup policy.
- Review terminal scrollback and shell history after using `review_threads.py`; displayed conversation text may remain there.

`mine_chat_export.py` omits the full source path from its manifest by default. It still records the archive's filename and SHA-256 digest. `--omit-message-text` removes message bodies from the JSONL output, but it does **not** anonymize titles, conversation IDs, attachment labels, timestamps, or other metadata.

No real conversation export, normalized index, attachment inventory, or archive manifest is included in this repository. The example under `examples/synthetic_export/` is entirely fictional.

## Requirements

- Python 3.10 or newer
- No third-party Python packages

## Quick start

Keep the export and output in private folders outside the cloned repository:

```text
python mine_chat_export.py PATH_TO_EXPORT.zip PATH_TO_PRIVATE_OUTPUT
python review_threads.py PATH_TO_PRIVATE_OUTPUT/conversations_index.jsonl "garden|planning"
python inventory_chat_assets.py PATH_TO_EXPORT.zip PATH_TO_PRIVATE_ASSET_OUTPUT "garden|planning"
```

Use `--help` on any script for the complete options.

### Create a lower-content index

```text
python mine_chat_export.py PATH_TO_EXPORT.zip PATH_TO_PRIVATE_OUTPUT --omit-message-text
```

This retains structural metadata and attachment labels while blanking message bodies and the first/last user excerpts. It is a data-minimization option, not a de-identification guarantee.

### Deliberately include the source path

The full source path is excluded because it can expose usernames or folder names. Include it only when provenance requirements outweigh that risk:

```text
python mine_chat_export.py PATH_TO_EXPORT.zip PATH_TO_PRIVATE_OUTPUT --include-source-path
```

## Outputs

`mine_chat_export.py` creates:

- `conversations_index.jsonl`: normalized active-branch messages and metadata.
- `conversation_titles.tsv`: searchable title, timestamp, ID, and message-count table.
- `import_manifest.json`: archive name and digest, source member names, counts, timestamps, and processing notes.

`inventory_chat_assets.py` creates:

- `ai_asset_inventory.json`
- `ai_asset_inventory.tsv`

The inventory records metadata and SHA-256 digests. It does not extract attachment contents.

`review_threads.py` writes to standard output and does not modify the index.

## Important behavior and limits

- Only the active branch ending at a conversation's `current_node` is normalized. Alternate branches are ignored.
- Attachment labels are retained when present. Raw attachments are not extracted.
- Conversation titles and IDs may be sensitive even when message text is omitted.
- The utilities reflect the export structures they know about. Export formats may change.
- A malformed or extremely large archive can consume significant memory, disk space, or processing time. Use only archives you trust.
- The tools perform local parsing; they do not make network requests.

## Synthetic example and tests

The committed fixture is a miniature, fictional export layout. Tests package it into a temporary ZIP and exercise all three commands:

```text
python -m unittest discover -s tests -v
```

You can also check syntax without processing any private data:

```text
python -m compileall -q mine_chat_export.py inventory_chat_assets.py review_threads.py tests
```

## License status

The included `LICENSE` reserves all rights while the owner chooses a long-term license. Public visibility alone does not grant permission to copy, modify, or redistribute the code.

## Contributing safely

Use only synthetic fixtures in commits and pull requests. Never submit real export fragments, identifiers, filenames, hashes, screenshots, or generated reports. See `SECURITY.md` for private vulnerability reporting guidance.
