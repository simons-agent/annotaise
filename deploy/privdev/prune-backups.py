"""Retention for backup.sh: prune old unlabelled dumps in one backup directory.

    python3 prune-backups.py <dir> <keep_daily> <keep_weekly>

Only files named exactly ``<YYYYmmddTHHMMSSZ>.dump`` take part in retention:
the newest of each of the ``keep_daily`` most recent days and of each of the
``keep_weekly`` most recent ISO weeks is kept, the rest are deleted.
Labelled dumps (``<stamp>-<label>.dump``, e.g. ``-predeploy``) are never
deleted, nor counted towards a day or week; other files are left alone.
"""

import datetime as dt
import pathlib
import re
import sys

STAMP = re.compile(r"\d{8}T\d{6}Z")
LABELLED = re.compile(r"\d{8}T\d{6}Z-[a-z0-9][a-z0-9-]*")

directory = pathlib.Path(sys.argv[1])
keep_daily, keep_weekly = int(sys.argv[2]), int(sys.argv[3])
dumps, labelled = [], 0
for path in directory.glob("*.dump"):
    if LABELLED.fullmatch(path.stem):
        labelled += 1
        continue  # labelled: never pruned
    if not STAMP.fullmatch(path.stem):
        continue  # not ours; leave it alone
    dumps.append((dt.datetime.strptime(path.stem, "%Y%m%dT%H%M%SZ"), path))
dumps.sort(reverse=True)  # newest first

keep, days, weeks = set(), [], []
for stamp, path in dumps:
    day = stamp.date()
    week = stamp.isocalendar()[:2]
    if day not in days and len(days) < keep_daily:
        days.append(day)
        keep.add(path)
    if week not in weeks and len(weeks) < keep_weekly:
        weeks.append(week)
        keep.add(path)

for _, path in dumps:
    if path not in keep:
        path.unlink()
        print(f"pruned {path.name}")
print(f"retained {len(keep)} dump(s) in {directory}; kept {labelled} labelled dump(s)")
