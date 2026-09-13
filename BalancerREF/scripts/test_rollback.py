"""Prove the Rollback guard actually restores. Run: python scripts/test_rollback.py

A safeguard that is never exercised is the same problem as one that only prints, so
these cases run the real class against real files in a temp directory: a passing check
must commit, a failing check must put every byte back, an unexpected exception must put
every byte back, and a file that did not exist before must not survive a failure.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

CASE = r'''
import sys
sys.path.insert(0, r"{here}")
from pathlib import Path
from rollback import Rollback

a, b, fresh = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
mode = sys.argv[4]
with Rollback(a, b, fresh) as guard:
    a.write_text("EDITED-A")
    b.write_text("EDITED-B")
    fresh.write_text("BRAND-NEW")
    if mode == "fail":
        guard.require(False, "deliberate check failure")
    if mode == "raise":
        raise ValueError("deliberate crash")
    guard.require(True, "unused")
print("COMMITTED")
'''


def run(mode):
    tmp = Path(tempfile.mkdtemp())
    a, b, fresh = tmp / 'a.txt', tmp / 'b.txt', tmp / 'fresh.txt'
    a.write_text('ORIGINAL-A')
    b.write_text('ORIGINAL-B')
    script = tmp / 'case.py'
    script.write_text(CASE.format(here=str(HERE)))
    p = subprocess.run([sys.executable, str(script), str(a), str(b), str(fresh), mode],
                       capture_output=True, text=True)
    return p, a, b, fresh


fails = []


def check(label, ok, detail=''):
    print('  %-58s %s' % (label, 'ok' if ok else 'FAIL ' + detail))
    if not ok:
        fails.append(label)


print('pass: a satisfied check commits the edit')
p, a, b, fresh = run('pass')
check('exit code is 0', p.returncode == 0, str(p.returncode))
check('edits kept', a.read_text() == 'EDITED-A' and b.read_text() == 'EDITED-B')
check('new file kept', fresh.exists() and fresh.read_text() == 'BRAND-NEW')

print('fail: require(False) restores every file and exits non-zero')
p, a, b, fresh = run('fail')
check('exit code is 1', p.returncode == 1, str(p.returncode))
check('a.txt restored byte-for-byte', a.read_text() == 'ORIGINAL-A', a.read_text())
check('b.txt restored byte-for-byte', b.read_text() == 'ORIGINAL-B', b.read_text())
check('file that did not exist is removed again', not fresh.exists())
check('did not print COMMITTED', 'COMMITTED' not in p.stdout)
check('reported the reason', 'deliberate check failure' in p.stdout, p.stdout)

print('raise: an unexpected exception restores too')
p, a, b, fresh = run('raise')
check('exit code is 1', p.returncode == 1, str(p.returncode))
check('a.txt restored byte-for-byte', a.read_text() == 'ORIGINAL-A', a.read_text())
check('b.txt restored byte-for-byte', b.read_text() == 'ORIGINAL-B', b.read_text())
check('file that did not exist is removed again', not fresh.exists())
check('named the exception', 'ValueError' in p.stdout, p.stdout)

print()
if fails:
    print('FAIL: %d check(s) failed: %s' % (len(fails), fails))
    sys.exit(1)
print('PASS: Rollback commits on success and restores on failure, including new files.')
