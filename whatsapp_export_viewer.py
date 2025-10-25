import hashlib
import html
import json
import os
import re
import shutil
import urllib.parse
import webbrowser
import zipfile
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ----------------------------
# Configuration
# ----------------------------
BASE_DIR = os.path.dirname(__file__)
EXPORTS_DIR = os.path.join(BASE_DIR, 'exports')
CACHE_DIR = os.path.join(BASE_DIR, '.cache')
os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

BATCH_SIZE = 50


# ----------------------------
# Utilities
# ----------------------------

def get_zip_files():
    return sorted([f for f in os.listdir(EXPORTS_DIR) if f.lower().endswith('.zip')])


def find_chat_file_in_dir(root_dir):
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith('.txt') and ('chat' in f.lower() or 'whatsapp' in f.lower()):
                return os.path.join(dirpath, f)
    raise FileNotFoundError('No chat .txt found in extracted ZIP')


def compute_file_hash(filepath):
    hash_md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def parse_chat_streaming(chat_path, chat_dir):
    with open(chat_path, 'r', encoding='utf-8', errors='replace') as f:
        current_msg = None
        for line in f:
            line = line.rstrip('\n\r')
            line = line.lstrip('\ufeff\u200e\u200f')
            line = line.replace('\u202f', ' ').replace('\xa0', ' ')
            if not line.strip():
                continue

            match = re.match(r'^\[(?P<ts>[^\]]+)\]\s*(?P<content>.*)', line)
            if not match:
                match = re.match(r'^(?P<ts>[^-]+)\s*-\s*(?P<content>.*)', line)

            if match:
                if current_msg:
                    yield current_msg

                raw_ts = match.group('ts').strip()
                content = match.group('content')

                sender_match = re.match(r'^(.*?):\s*(.*)', content)
                if sender_match:
                    sender, text = sender_match.groups()
                    is_system = False
                else:
                    sender = 'System'
                    text = content
                    is_system = True

                is_media = False
                media_rel_path = None

                attached_match = re.search(r'<attached:\s*([^>]+)>', text, flags=re.I)
                if not attached_match:
                    attached_match = re.search(r'attached:\s*([^\n\r]+)', text, flags=re.I)

                if attached_match:
                    raw_group = attached_match.group(1)
                    fn_search = re.search(r'([^\s"\'=<>]+?\.(?:jpg|jpeg|png|gif|mp4|mov|3gp|mp3|opus|aac|wav))',
                                          raw_group, flags=re.I)
                    if fn_search:
                        fname = fn_search.group(1).strip().strip('"').strip("'")
                    else:
                        fname = raw_group.strip().strip('"').strip("'")
                    fname = fname.replace('\ufeff', '').replace('\u200e', '').replace('\u200f', '')

                    for root, _, files in os.walk(chat_dir):
                        for f in files:
                            if f.lower() == os.path.basename(fname).lower() or f.lower().endswith(
                                    os.path.basename(fname).lower()):
                                media_candidate = os.path.relpath(os.path.join(root, f), chat_dir)
                                media_rel_path = urllib.parse.quote(media_candidate.replace(os.sep, '/'))
                                is_media = True
                                break
                        if is_media:
                            break

                    text = re.sub(r'<attached:[^>]+>', '', text, flags=re.I)
                    text = re.sub(r'attached:\s*[^\n\r]+', '', text, flags=re.I)

                if not is_media:
                    if re.search(r'<media omitted>|<Media omitted>|<attached media omitted>', text, flags=re.I) or (
                            '<Media omitted>' in text):
                        is_media = True
                        for root, _, files in os.walk(chat_dir):
                            for f in files:
                                ext = os.path.splitext(f)[1].lower()
                                if ext in ('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.3gp', '.mov', '.mp3', '.opus',
                                           '.aac', '.wav'):
                                    media_candidate = os.path.relpath(os.path.join(root, f), chat_dir)
                                    media_rel_path = urllib.parse.quote(media_candidate.replace(os.sep, '/'))
                                    break
                            if media_rel_path:
                                break
                        text = re.sub(r'<[^>]+>', '', text)

                if is_media:
                    text = ''

                current_msg = {
                    'timestamp': raw_ts,
                    'sender': sender,
                    'text': text,
                    'is_media': is_media,
                    'media_path': media_rel_path,
                    'is_system': is_system
                }
            else:
                if current_msg:
                    current_msg['text'] += '\n' + line

        if current_msg:
            yield current_msg


def cache_chat(zip_path, messages):
    zip_hash = compute_file_hash(zip_path)
    cache_file = os.path.join(CACHE_DIR, f"{zip_hash}.json")
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False)
    return cache_file


def load_cached_chat(zip_path):
    zip_hash = compute_file_hash(zip_path)
    cache_file = os.path.join(CACHE_DIR, f"{zip_hash}.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def extract_and_parse(zip_path):
    try:
        cached = load_cached_chat(zip_path)
        if cached is not None:
            return cached

        extract_dir = os.path.join(CACHE_DIR, 'tmp_extract')
        if os.path.exists(extract_dir):
            try:
                shutil.rmtree(extract_dir)
            except Exception:
                pass
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        chat_file = find_chat_file_in_dir(extract_dir)
        chat_dir = os.path.dirname(chat_file)
        messages = list(parse_chat_streaming(chat_file, chat_dir))
        cache_chat(zip_path, messages)
        return messages
    except zipfile.BadZipFile:
        raise ValueError('Invalid or corrupted ZIP file')


def highlight_text(text, query):
    if not query or not text:
        return html.escape(text).replace('\n', '<br>')
    escaped = html.escape(text)
    highlighted = re.sub(f'({re.escape(query)})',
                         r"<mark style=\"background:#005c4b;color:white;padding:0 2px;border-radius:2px;\">\1</mark>",
                         escaped, flags=re.IGNORECASE)
    return highlighted.replace('\n', '<br>')


def render_message_html_with_highlight(messages, query):
    out = ''
    for msg in messages:
        if msg.get('is_system'):
            out += f"<div class=\"system\">{html.escape(msg.get('text', ''))}</div>"
            continue

        is_match = msg.get('_is_match', False)
        bubble_class = 'bubble' + (' match-bubble' if is_match else '')
        sender = html.escape(msg.get('sender', ''))
        index_attr = f' id="msg-{msg.get("_index")}" data-index="{msg.get("_index")}"' if '_index' in msg else ''
        out += f'<div class="message received" data-sender="{sender}"{index_attr}>'
        out += f'<div class="{bubble_class}">'
        out += f'<div class="sender">{sender}</div>'

        if msg.get('is_media') and msg.get('media_path'):
            ext = os.path.splitext(msg['media_path'])[1].lower()
            src = '/exports/' + msg['media_path']
            if ext in ('.jpg', '.jpeg', '.png', '.gif'):
                out += f'<img src="{src}" class="media" alt="Media">'
            elif ext in ('.mp4', '.mov', '.3gp'):
                out += f'<video controls class="media"><source src="{src}" type="video/mp4">Video</video>'
            else:
                out += f'<a href="{src}" style="color:#00a884;">📎 Media</a>'
        else:
            text_str = msg.get('text', '') or ''
            escaped_html = html.escape(text_str).replace('\n', '<br>')
            out += f'<div class="message-text">{escaped_html}</div>'
            if query:
                out += highlight_text(msg.get('text', ''), query)

        if msg.get('_is_match'):
            idx = msg.get('_index', '')
            if idx != '':
                out += f'<div style="margin-top:6px;font-size:12px;"><a href="#" onclick="goToMessage({idx});return false;" style="color:#00a884;">View in chat</a></div>'

        out += '</div></div>'

        try:
            for fmt in ['%m/%d/%y, %I:%M:%S %p', '%d/%m/%Y, %H:%M', '%d/%m/%y, %I:%M %p']:
                try:
                    dt = datetime.strptime(msg['timestamp'], fmt)
                    time_str = dt.strftime('%I:%M %p')
                    break
                except Exception:
                    continue
            else:
                time_str = msg['timestamp']
        except Exception:
            time_str = msg['timestamp']
        out += f'<div class="timestamp">{html.escape(str(time_str))}</div>'

    return out


def render_file_selector(zip_files):
    options = ''.join(f'<option value="{urllib.parse.quote(f)}">{f}</option>' for f in zip_files)
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>WhatsApp Viewer</title>
        <style>
            body {{ background: #121b22; color: #e6e6e6; font-family: sans-serif; padding: 40px; }}
            select, button {{ padding: 10px; font-size: 16px; margin: 5px; }}
            h1 {{ text-align: center; }}
        </style>
    </head>
    <body>
        <h1>📁 WhatsApp Export Viewer</h1>
        <form method="GET" action="/view">
            <select name="file" required>{options}</select>
            <button type="submit">Load Chat</button>
        </form>
        <p>Place your WhatsApp .zip exports in the <code>exports/</code> folder.</p>
        <p>Found {len(zip_files)} export(s).</p>
    </body>
    </html>
    """


def render_chat_page(display_name, zip_filename, total_messages, current_page, search_query=""):
    template_path = os.path.join(BASE_DIR, 'templates', 'chat.html')
    if not os.path.exists(template_path):
        return f"<html><body><h1>Template missing</h1><p>Place templates/chat.html in the project.</p></body></html>"

    with open(template_path, 'r', encoding='utf-8') as f:
        tpl = f.read()

    js_config = {
        'chatName': display_name,
        'totalMessages': total_messages,
        'currentPage': current_page,
        'searchQuery': search_query,
        'encodedFile': urllib.parse.quote(zip_filename),
        'batchSize': BATCH_SIZE
    }

    page = tpl.replace('{display_name}', html.escape(display_name))
    page = page.replace('{search_query}', html.escape(search_query))
    page = page.replace('{batch_size}', str(BATCH_SIZE))
    page = page.replace('{js_config}', json.dumps(js_config, ensure_ascii=False))
    return page


# ----------------------------
# HTTP Handler
# ----------------------------

class Handler(BaseHTTPRequestHandler):
    def add_cors_headers(self):
        """Add CORS headers for the debug endpoint to work from dev tools"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        """Handle preflight CORS requests"""
        self.send_response(200)
        self.add_cors_headers()
        self.end_headers()

    def render_javascript(self, **kwargs):
        """Render JavaScript with proper escaping of template variables"""
        js_vars = {
            'chatName': kwargs.get('display_name', ''),
            'totalMessages': kwargs.get('total_messages', 0),
            'currentPage': kwargs.get('current_page', 0),
            'searchQuery': kwargs.get('search_query', ''),
            'encodedFile': kwargs.get('encoded_file', ''),
            'batchSize': BATCH_SIZE
        }
        return f"window.chatConfig = {json.dumps(js_vars)};"

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        query = parse_qs(url.query)

        if path == '/':
            zip_files = get_zip_files()
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(render_file_selector(zip_files).encode('utf-8'))

        elif path == '/view':
            file_name = query.get('file', [None])[0]
            if not file_name:
                self.send_error(400, "No file selected")
                return

            try:
                file_name = urllib.parse.unquote(file_name)
                zip_path = os.path.join(EXPORTS_DIR, file_name)
                if not os.path.exists(zip_path):
                    self.send_error(404, "File not found")
                    return

                messages = extract_and_parse(zip_path)
                total = len(messages)
                display_name = os.path.splitext(file_name)[0].replace('_', ' ')
                page = int(query.get('page', [0])[0])
                search_query = query.get('q', [''])[0]

                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(render_chat_page(display_name, file_name, total, page, search_query).encode('utf-8'))
            except Exception as e:
                self.send_error(500, str(e))

        elif path == '/api/messages':
            file_name = query.get('file', [None])[0]
            if not file_name:
                self.send_error(400, "No file")
                return

            try:
                file_name = urllib.parse.unquote(file_name)
                zip_path = os.path.join(EXPORTS_DIR, file_name)
                messages = extract_and_parse(zip_path)

                page = int(query.get('page', [0])[0])
                search_query = query.get('query', [''])[0]
                batch_size = int(query.get('batch_size', [BATCH_SIZE])[0])

                # Collect all unique senders for dropdown
                all_senders = set()
                for msg in messages:
                    if not msg.get('is_system', False):
                        all_senders.add(msg['sender'])
                senders_list = sorted(all_senders)

                if search_query.strip():
                    query_clean = search_query.strip()
                    match_indices = []
                    for i, msg in enumerate(messages):
                        text_content = (msg.get('text', '') + ' ' + msg.get('sender', '')).lower()
                        if query_clean.lower() in text_content:
                            match_indices.append(i)

                    context_indices = set()
                    for i in match_indices:
                        for j in range(max(0, i - 2), min(len(messages), i + 3)):
                            context_indices.add(j)
                    context_indices = sorted(context_indices)

                    enriched = []
                    for idx in context_indices:
                        msg = messages[idx].copy()
                        msg['_is_match'] = (idx in match_indices)
                        msg['_index'] = idx
                        enriched.append(msg)

                    total_matches = len(match_indices)
                    start = page * batch_size
                    end = start + batch_size
                    batch = enriched[start:end]
                    html = render_message_html_with_highlight(batch, query_clean)

                else:
                    total_matches = len(messages)
                    start = page * batch_size
                    end = start + batch_size
                    # include global indices for each message so the client can link back to them
                    batch = []
                    for i in range(start, min(end, len(messages))):
                        m = messages[i].copy()
                        m['_index'] = i
                        batch.append(m)
                    html = render_message_html_with_highlight(batch, "")

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'html': html,
                    'total_matches': total_matches,
                    'senders': senders_list
                }).encode('utf-8'))

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

        elif path == '/api/debug':
            # Debug endpoint to inspect message parsing
            file_name = query.get('file', [None])[0]
            msg_id = query.get('id', [None])[0]

            if not file_name or msg_id is None:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.add_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Missing file or message ID'}).encode('utf-8'))
                return

            try:
                msg_id = int(msg_id)
                file_name = urllib.parse.unquote(file_name)
                zip_path = os.path.join(EXPORTS_DIR, file_name)
                messages = extract_and_parse(zip_path)

                if msg_id < 0 or msg_id >= len(messages):
                    self.send_response(404)
                    self.send_header('Content-type', 'application/json')
                    self.add_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'Message not found'}).encode('utf-8'))
                    return

                msg = messages[msg_id]
                debug_info = {
                    'message': msg,
                    'raw_text': msg.get('text', ''),
                    'text_length': len(msg.get('text', '')),
                    'has_media_marker': bool(re.search(r'<media|<attached|attached:', msg.get('text', ''), flags=re.I)),
                    'media_info': {
                        'is_media': msg.get('is_media', False),
                        'media_path': msg.get('media_path', None)
                    },
                    'parsed_timestamp': msg.get('timestamp', ''),
                    'is_system_message': msg.get('is_system', False)
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.add_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(debug_info, ensure_ascii=False, indent=2).encode('utf-8'))

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.add_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

        elif path == '/api/find':
            # Find first message index that matches the query (simple contains on text+sender)
            file_name = query.get('file', [None])[0]
            q = query.get('q', [''])[0]
            if not file_name:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.add_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'No file'}).encode('utf-8'))
                return
            try:
                file_name = urllib.parse.unquote(file_name)
                zip_path = os.path.join(EXPORTS_DIR, file_name)
                messages = extract_and_parse(zip_path)
                q_clean = q.strip().lower()
                found = -1
                if q_clean:
                    for i, msg in enumerate(messages):
                        text_content = (msg.get('text', '') + ' ' + msg.get('sender', '')).lower()
                        if q_clean in text_content:
                            found = i
                            break

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'index': found}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

        elif path == '/api/debug_message':
            # Return the parsed message object for a given global index (for debugging)
            file_name = query.get('file', [None])[0]
            idx = query.get('index', [None])[0]
            if not file_name or idx is None:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'missing file or index'}).encode('utf-8'))
                return
            try:
                file_name = urllib.parse.unquote(file_name)
                idx = int(idx)
                zip_path = os.path.join(EXPORTS_DIR, file_name)
                messages = extract_and_parse(zip_path)
                if idx < 0 or idx >= len(messages):
                    self.send_response(404)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'index out of range'}).encode('utf-8'))
                    return
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(messages[idx], ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

        elif path.startswith('/exports/'):
            rel_path = urllib.parse.unquote(path[len('/exports/'):])

            # Try to serve from the exports folder first (user may have placed media there)
            candidate = os.path.join(EXPORTS_DIR, rel_path)
            if os.path.exists(candidate):
                serve_path = candidate
            else:
                # Fallback: search the cache extraction tree for the requested relative path.
                serve_path = None
                for root, _, files in os.walk(CACHE_DIR):
                    for f in files:
                        full = os.path.join(root, f)
                        # normalize and compare the tail of the path to allow matching nested media paths
                        rel = os.path.relpath(full, CACHE_DIR).replace('\\', '/')
                        if rel.endswith(rel_path) or os.path.basename(full) == os.path.basename(rel_path):
                            serve_path = full
                            break
                    if serve_path:
                        break

            if not serve_path or not os.path.exists(serve_path):
                self.send_error(404)
                return

            # determine content-type
            self.send_response(200)
            ext = os.path.splitext(serve_path)[1].lower()
            ct = 'application/octet-stream'
            if ext in ('.jpg', '.jpeg'):
                ct = 'image/jpeg'
            elif ext == '.png':
                ct = 'image/png'
            elif ext == '.gif':
                ct = 'image/gif'
            elif ext in ('.mp4', '.mov', '.3gp'):
                ct = 'video/mp4'
            elif ext in ('.mp3', '.opus'):
                ct = 'audio/mpeg'
            self.send_header('Content-type', ct)
            self.end_headers()
            with open(serve_path, 'rb') as f:
                self.wfile.write(f.read())

        else:
            self.send_error(404)


# ----------------------------
# Main Entry Point
# ----------------------------

def main():
    port = 8000
    server = HTTPServer(('localhost', port), Handler)
    url = f'http://localhost:{port}'
    print(f"✅ WhatsApp Viewer running at {url}")
    print(f"📁 Place your WhatsApp .zip exports in: {os.path.abspath(EXPORTS_DIR)}")
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
        server.server_close()  # Ensure proper cleanup

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass  # Handle Ctrl+C gracefully at the top level
