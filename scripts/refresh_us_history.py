"""Build historical factors in bounded batches, retaining dated last-good entries."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from investment.data.us_history_cache import PATH, FIELDS, read_cache
from investment.data.us_universe import read_us_snapshot
from investment.data.foreign_live_history import enrich_foreign_history


def main(limit=0):
    snapshot = read_us_snapshot()
    items = read_cache()
    # Process oldest/missing entries first so partial runs advance coverage.
    rows = sorted(snapshot['rows'], key=lambda r: items.get(r['ticker'], {}).get('history_as_of', ''))
    if limit:
        rows = rows[:limit]
    updated = 0
    for offset in range(0, len(rows), 120):
        for row in enrich_foreign_history(rows[offset:offset+120], limit=120):
            if all(row.get(f'change_{n}d') is not None for n in (5, 20, 60)) and row.get('history_as_of'):
                items[row['ticker']] = {k: row[k] for k in FIELDS if k in row}
                updated += 1
        temporary = PATH.with_suffix('.tmp')
        temporary.write_text(json.dumps({'version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
                                        'items': items}, separators=(',', ':')), encoding='utf-8')
        temporary.replace(PATH)
        print(f'Processed {min(offset+120,len(rows))}/{len(rows)}; updated {updated}', flush=True)
    if not updated:
        raise RuntimeError('No historical factors refreshed; retained last-good entries')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    if args.limit < 0:
        parser.error('--limit must be non-negative')
    main(args.limit)
