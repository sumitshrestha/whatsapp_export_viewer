# WhatsApp Export Viewer

Lightweight local viewer for WhatsApp exported ZIP archives. Run the simple built-in HTTP server and open the UI in your browser to browse and search chats and media.

## Features

- Parse WhatsApp exported `.zip` archives (the chat `.txt` and attached media).
- Serve a small web UI (plain Python stdlib HTTPServer) at `http://localhost:8000`.
- Search messages, view message context, and serve extracted media files.
- Infinite scroll with dynamic loading of message batches.
- Per-ZIP extraction caching for fast switching between chats.
- No external web framework required - pure Python standard library.

## Repository layout

- `whatsapp_export_viewer.py` — Main script. Runs a small HTTP server (default port 8000) and serves the UI.
- `templates/chat.html` — HTML template used to render chat pages.
- `static/chat.js` — Client-side JavaScript for pagination/search in the UI.
- `exports/` — Drop your WhatsApp `.zip` export files here.
- `scripts/inspect_exports.py` — Utility script(s) for inspecting/parsing exports (optional).
- `scripts/run_parse_test.py` — Small test/run helper (optional).
- `.cache/` — Created at runtime to cache parsed JSON for faster reloads.


## Prerequisites

- Python 3.6+ (the project uses only the standard library; no external packages required)
- Web browser with JavaScript enabled
- WhatsApp chat export ZIP file(s)

A virtual environment is recommended for isolation but not required:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # on Windows
source .venv/bin/activate     # on Linux/MacOS
```

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

- Add CLI flags for:
  - Custom host/port binding
  - Disable browser auto-open
  - Control cache cleanup age
- Add unit tests for parsing edge cases (timestamps, multiline messages, media markers)
- Add loading indicators during batch loads
- Add favicon to prevent 404 on browser requests

The project intentionally uses only Python standard library modules. See `requirements.txt` for the minimum Python version and list of stdlib modules used.

## License

Choose a license for your project (e.g., MIT). This repository currently has no explicit license.

---

## Contributing

Key files for development:
- `whatsapp_export_viewer.py` - Main server & parsing logic
- `templates/chat.html` - Core template with viewport & controls
- `static/chat.js` - Client-side logic for infinite scroll & UI

Development tips:
1. Use browser DevTools Network tab to watch for `/api/messages` requests during infinite scroll
2. Check browser Console for any JavaScript errors
3. Kill the server with Ctrl+C - it will clean up properly
4. The `.cache/` folder is safe to delete - it will be rebuilt on next run

Feel free to submit pull requests for any improvements!
