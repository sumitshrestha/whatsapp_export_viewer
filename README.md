# WhatsApp Export Viewer

Lightweight local viewer for WhatsApp exported ZIP archives. Run the simple built-in HTTP server and open the UI in your browser to browse and search chats and media.

## Features

- Parse WhatsApp exported `.zip` archives (the chat `.txt` and attached media).
- Serve a small web UI (plain Python stdlib HTTPServer) at `http://localhost:8000`.
- Search messages, view message context, and serve extracted media files.
- No external web framework required.

## Repository layout

- `whatsapp_export_viewer.py` — Main script. Runs a small HTTP server (default port 8000) and serves the UI.
- `templates/chat.html` — HTML template used to render chat pages.
- `static/chat.js` — Client-side JavaScript for pagination/search in the UI.
- `exports/` — Drop your WhatsApp `.zip` export files here.
- `scripts/inspect_exports.py` — Utility script(s) for inspecting/parsing exports (optional).
- `scripts/run_parse_test.py` — Small test/run helper (optional).
- `.cache/` — Created at runtime to cache parsed JSON for faster reloads.


## Prerequisites

- Python 3.8+ (the project uses only the standard library; no external packages required).

Optional: create a virtual environment for isolation.

## Quick start (Windows PowerShell)

Open PowerShell in the project directory and run:

```powershell
# (optional) create & activate venv
python -m venv .venv; .\.venv\Scripts\Activate.ps1

# run the viewer
python whatsapp_export_viewer.py
```

After the script starts it will print the local URL (usually `http://localhost:8000`) and attempt to open it in your default browser.

Usage notes:
- Place your exported WhatsApp `.zip` files in the `exports/` folder before loading them in the UI.
- The server extracts archives to `.cache/` and caches parsed messages to speed up subsequent loads.
- Default port: 8000. To change the port, edit the `main()` function in `whatsapp_export_viewer.py`.

## Troubleshooting

- If the browser doesn't open automatically, open the printed URL manually.
- If you see `Invalid or corrupted ZIP file`, confirm the zip is a valid WhatsApp export.
- If media doesn't display, check the ZIP contains media files and that they were extracted into the cache.

## Development / Next steps

- Add a small `requirements.txt` if you introduce external packages.
- Add a CLI flag to change host/port or disable auto-open.
- Add unit tests for parsing edge cases (timestamps, multiline messages, media markers).

## License

Choose a license for your project (e.g., MIT). This repository currently has no explicit license.

---

If you'd like, I can also:
- add a `requirements.txt` or `pyproject.toml` if you plan to add dependencies,
- add a short Dockerfile to run the viewer in a container,
- or add a CONTRIBUTING.md with steps to run tests.
