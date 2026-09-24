# Security and privacy policy

## Supported versions

Until a stable release policy exists, only the newest revision on the default branch is intended to receive security fixes.

## Reporting a vulnerability

After this repository is published, use GitHub's private security-advisory feature when available. Do not open a public issue containing exploit details, personal information, or any portion of a real ChatGPT export. If private advisories are not enabled, open a minimal public issue asking the maintainer to establish a private contact channel; include no sensitive details.

Please report issues such as:

- unintended network access or data transmission;
- path disclosure beyond documented behavior;
- unsafe archive handling;
- output written outside the requested directory;
- accidental retention of message content when an omission option is selected; or
- a committed fixture that appears to contain real personal data.

## Handling sample data

Reproduce issues with synthetic data only. Replace names, conversation IDs, file IDs, timestamps, filenames, hashes, and message bodies. A digest or identifier can itself be sensitive and must not be shared merely because it is not human-readable.

## Local safety notes

These tools make private data easier to search. Generated JSONL, TSV, JSON, terminal output, backups, and temporary files can all disclose conversation content or metadata. Store them outside the repository with access controls appropriate to the data. `--omit-message-text` reduces retained content but is not anonymization.

The scripts do not extract attachment contents or make network requests. They do parse ZIP and JSON input, so process only archives you trust and keep sufficient free disk space.
