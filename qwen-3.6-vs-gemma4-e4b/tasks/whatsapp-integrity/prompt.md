backupwhatsapp.py sometimes exits with an unhelpful JSON parse error such as:

    Expecting value: line 1 column 1 (char 0)

A corrupted or accidentally contaminated backup JSONL file must never be silently skipped, partially repaired, or overwritten.

Improve this robustly:

- detect malformed backup JSONL before connecting to WhatsApp/CDP
- identify the exact file and line
- validate that stored rows belong to the conversation implied by the file
- report all corrupt backup files found, not merely the first
- never expose message text in the error
- never mutate damaged inputs
- add focused regression tests

Keep the implementation compact. Run the relevant tests. Do not commit. Do not inspect or modify files outside this repository.
