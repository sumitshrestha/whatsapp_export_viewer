import importlib.util
import sys
import os
from importlib.machinery import SourceFileLoader

script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Qwen_python_20251024_9n7pvuwta.py'))
loader = SourceFileLoader('whats_module', script_path)
mod = loader.load_module()

exports_dir = os.path.join(os.path.dirname(script_path), 'exports')
# choose first zip
zips = [f for f in os.listdir(exports_dir) if f.lower().endswith('.zip')]
if not zips:
    print('No zip files found in', exports_dir)
    sys.exit(1)
zip_file = zips[0]
zip_path = os.path.join(exports_dir, zip_file)
print('Using zip:', zip_file)
messages = mod.extract_and_parse(zip_path)
print('Parsed messages:', len(messages))
# print first 30 messages senders and is_system
for i, m in enumerate(messages[:30], 1):
    print(f"{i:02d}: sender={m.get('sender')!r}, is_system={m.get('is_system')}, text={m.get('text')[:60]!r}")
# print unique senders
senders = sorted({m['sender'] for m in messages if not m.get('is_system', False)})
print('\nUnique senders (count={}):'.format(len(senders)))
for s in senders:
    print(' -', s)
