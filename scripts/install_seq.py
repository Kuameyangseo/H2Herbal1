import sys
import subprocess
from pathlib import Path

req_file = Path(__file__).resolve().parents[1] / 'requirements.txt'
if not req_file.exists():
    print('requirements.txt not found at', req_file)
    sys.exit(1)

with open(req_file, 'r', encoding='utf-8') as f:
    lines = [l.strip() for l in f if l.strip() and not l.strip().startswith('#')]

for line in lines:
    print('\n=== Installing:', line, '===\n')
    try:
        completed = subprocess.run([sys.executable, '-m', 'pip', 'install', line], check=False)
        if completed.returncode != 0:
            print(f'Installation failed for {line} with return code {completed.returncode}')
            sys.exit(completed.returncode)
    except Exception as e:
        print('Exception while installing', line)
        print(e)
        sys.exit(1)

print('\nAll packages installed (or skipped)')
