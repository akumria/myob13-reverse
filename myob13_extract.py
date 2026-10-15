#!/usr/bin/env python3
"""Extract records from a MYOB v13 / c-tree Plus VMS company file.

The file is unencrypted - the MYOB company password is an application-level
gate, not a key over the records - so this reads the data directly.

Layout (c-tree VMS variable-length data file):
  <FA FA> <len1:u32> <len2:u32> <len3:u32> ... 48 bytes of header ...
  <payload: len2 bytes>

`FA FA` is the data-record mark (`FE FE` is used for resource records). `len1`
is the record's stored length, `len2` the payload length and `len3` a record
class discriminator. Records with the same (len1, len2, len3) triple are the
same MYOB record type, so the triple doubles as a type key.

Fields inside the payload are a mix of fixed binary values and NUL-terminated
strings, so strings are harvested positionally and numbers reported alongside.
"""
import json
import re
import struct
import sys
from collections import Counter, defaultdict

MARK = b'\xfa\xfa'
HEADER = 0x28          # payload starts this far after the mark (verified)
STR_RE = re.compile(rb'[\x20-\x7e]{2,}')


def scan(data):
    """Yield (offset, len1, len2, len3) for every well-formed data record."""
    for m in re.finditer(re.escape(MARK), data):
        off = m.start()
        if off + HEADER + 14 > len(data):
            continue
        len1, len2, len3 = struct.unpack_from('<III', data, off + 2)
        if not (0 < len2 < 1 << 20) or len1 < len2 or len1 > (1 << 24):
            continue
        if off + HEADER + len2 > len(data):
            continue
        yield off, len1, len2, len3


def payload(data, off, len2):
    return data[off + HEADER:off + HEADER + len2]


def strings(blob):
    """Ordered list of printable strings in the payload, CR/LF collapsed."""
    out = []
    for m in STR_RE.finditer(blob):
        s = m.group().decode('latin-1').strip()
        if s:
            out.append((m.start(), s))
    return out


def numbers(blob):
    """Numeric tokens (amounts, dates, ids) with their offset."""
    out = []
    for m in re.finditer(rb'-?\$?\d[\d,]*\.?\d*', blob):
        out.append((m.start(), m.group().decode('latin-1')))
    return out


def classify(recs):
    """Label record classes by their most common leading strings."""
    prof = {}
    for (l1, l2, l3), items in recs.items():
        bag = Counter()
        for _, _, blob in items:
            ss = [s for _, s in strings(blob)]
            bag[ss[0] if ss else ''] += 1
        prof[(l1, l2, l3)] = bag.most_common(4)
    return prof


def extract(path, out, sample=0):
    data = open(path, 'rb').read()
    recs = defaultdict(list)
    for off, l1, l2, l3 in scan(data):
        recs[(l1, l2, l3)].append((off, l1, payload(data, off, l2)))

    total = sum(len(v) for v in recs.values())
    print(f'{path}: {len(data):,} bytes, {total:,} records in {len(recs)} classes')

    doc = {'file': path, 'record_classes': {}}
    for key in sorted(recs, key=lambda k: -len(recs[k])):
        items = recs[key]
        prof = classify({key: items})[key]
        doc['record_classes'][str(key)] = {
            'count': len(items),
            'common_first_strings': [p[0] for p in prof],
            'payload_len': key[1],
            'class_field': key[2],
        }
        print(f'  {str(key):<20} {len(items):>7,}  {[p[0][:40] for p in prof]}')

    if sample:
        key = max(recs, key=lambda k: len(recs[k]))
        print(f'\n--- sample records from class {key} ---')
        for off, _, blob in recs[key][:sample]:
            print(f'  @{off:#x}')
            for o, s in strings(blob):
                print(f'     +{o:<5} {s!r}')
            print(f'     nums: {[n for _, n in numbers(blob)][:12]}')

    with open(out, 'w') as fh:
        json.dump(doc, fh, indent=2)
    print(f'\nwrote {out}')
    return recs


if __name__ == '__main__':
    extract(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 0)
