"""Snapshot files before an edit and put them back if the edit fails its own check.

Several scripts here write the schematic, then export a netlist and compare it against
what the edit was supposed to do. Printing the comparison is not enough: by the time it
prints, the schematic and `review/unused-pins.json` have already been overwritten, and a
script that reports a regression and then exits 0 leaves a corrupted sheet looking like a
successful run. That is the failure this class exists to prevent.

Usage:

    guard = Rollback(SCH, UNUSED_PINS)
    with guard:
        SCH.write_text(...)
        UNUSED_PINS.write_text(...)
        after = export_and_partition()
        guard.require(not regressions, 'surviving nets changed: %s' % regressions)

Leaving the `with` block normally commits. `require(False, ...)` or any exception raised
inside restores every snapshotted file and exits non-zero.
"""
import sys


class RollbackError(Exception):
    """Raised by require() so the context manager can restore before exiting."""


class Rollback:
    def __init__(self, *paths):
        self.paths = [p for p in paths if p is not None]
        self.saved = {p: (p.read_bytes() if p.exists() else None) for p in self.paths}

    def restore(self):
        for p, blob in self.saved.items():
            if blob is None:
                if p.exists():
                    p.unlink()
            else:
                p.write_bytes(blob)
        return [p.name for p in self.saved]

    def require(self, ok, why):
        if not ok:
            raise RollbackError(why)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            return False
        names = self.restore()
        if exc_type is RollbackError:
            print('\n!! CHECK FAILED: %s' % exc)
        else:
            print('\n!! %s: %s' % (exc_type.__name__, exc))
        print('restored, nothing kept: %s' % ', '.join(names))
        sys.exit(1)
