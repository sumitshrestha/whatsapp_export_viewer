import zipfile
import os
base = os.path.join(os.path.dirname(__file__), '..', 'exports')
base = os.path.abspath(base)
print('Inspecting exports dir:', base)
for fn in sorted(os.listdir(base)):
    if fn.lower().endswith('.zip'):
        path = os.path.join(base, fn)
        print('\nZIP:', fn)
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                for n in zf.namelist():
                    print('  ', n)
                    if n.lower().endswith('.txt'):
                        data = zf.read(n).decode('utf-8', errors='replace')
                        print('\n---- First 20 lines of', n, '----')
                        for i, line in enumerate(data.splitlines()[:20], 1):
                            print(f'{i:02d}:', line)
                        print('---- END ----\n')
                        break
        except Exception as e:
            print('  Failed to read zip:', e)
