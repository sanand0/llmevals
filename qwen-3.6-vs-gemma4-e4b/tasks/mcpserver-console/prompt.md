Improve the console logging in mcpserver.py.

When tools are called, I want the terminal output to be rapidly scannable while logs are flashing past.

Show the request and response, but tailor them per tool rather than dumping generic JSON. For example, file_info should emphasize the requested path and the response should emphasize useful things like size, line count, and human-readable modified time rather than MIME type, access metadata, or hashes.

For larger outputs, show enough of the beginning and end to understand what happened, truncating the middle clearly.

Use intuitive terminal formatting/color where appropriate.

Do not reduce the information stored in persistent file logs. This change is about console UX.

Keep it simple and maintainable. Add/update focused tests and run them. Do not commit. Do not inspect or modify files outside this repository.
