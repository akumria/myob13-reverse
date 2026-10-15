#!/usr/bin/env python3
"""MYOB v13 company file -> JSON/CSV, and an ERPNext import payload.

The .dat file is unencrypted, so this reads it directly. Records are located by
their c-tree VMS `FA FA` mark; the payload begins after a per-record-class
header (the header carries the index key, whose length varies by class, so it
is auto-tuned), and fields inside are NUL-terminated strings interleaved with
fixed binary values.

Outputs:
  <out>.json        every record with its harvested strings and numbers
  <out>.csv         flat string dump, one row per record
  <out>_erpnext.json  doctype-tagged records for ERPNext Data Import
"""
import csv
import json
import re
import struct
import sys
from collections import defaultdict

MARK = b'\xfa\xfa'
CANDIDATE_HDR = (0x18, 0x1c, 0x20, 0x24, 0x28)
STR_RE = re.compile(rb'[ -~]{2,}')
NUM_RE = re.compile(rb'-?\$?\d[\d,]*\.?\d*')
AMOUNT_RE = re.compile(rb'-?\$[\d,]+\.\d{2}')
DOC_RE = re.compile(rb'(Sale|Purchase|Invoice|Receipt|Payment|Bill|Cheque|Quote|Order)\s*#\s*(\w+)')
ID_RE = re.compile(rb'ID\s*#\s*(\w+)')


def scan(data):
    for m in re.finditer(re.escape(MARK), data):
        off = m.start()
        if off + 0x30 + 14 > len(data):
            continue
        l1, l2, l3 = struct.unpack_from('<III', data, off + 2)
        if not (0 < l2 < (1 << 20)) or l1 < l2 or l1 > (1 << 24):
            continue
        if off + 0x30 + l2 > len(data):
            continue
        yield off, l1, l2, l3


def complete_strings(blob):
    """NUL-terminated strings only - excludes a leading partial fragment."""
    out = []
    for part in blob.split(b'\x00'):
        if len(part) >= 2 and all(32 <= b < 127 for b in part):
            s = part.decode('latin-1').strip()
            if s:
                out.append(s)
    return out


def tune_header(data, samples):
    """Pick the payload offset that yields the most complete strings."""
    best, best_score = 0x28, -1
    for hdr in CANDIDATE_HDR:
        score = 0
        for off, l1, l2, l3 in samples:
            blob = data[off + hdr:off + hdr + l2]
            ss = complete_strings(blob)
            # a correctly aligned payload starts on a string boundary
            if ss and blob[:1] and 32 <= blob[0] < 127:
                score += len(ss)
        if score > best_score:
            best, best_score = hdr, score
    return best


def load(path):
    data = open(path, 'rb').read()
    by_class = defaultdict(list)
    for rec in scan(data):
        by_class[rec[3]].append(rec)
    return data, by_class


def class_records(data, cls, limit=None):
    """Yield (offset, strings, numbers, amounts) for one record class."""
    recs = [(o, l1, l2, l3) for (o, l1, l2, l3) in _cls_cache[id(cls)]]
    hdr = tune_header(data, recs[:400])
    for off, l1, l2, l3 in (recs if limit is None else recs[:limit]):
        blob = data[off + hdr:off + hdr + l2]
        yield (off,
               complete_strings(blob),
               [m.group().decode('latin-1') for m in NUM_RE.finditer(blob)],
               [m.group().decode('latin-1') for m in AMOUNT_RE.finditer(blob)],
               blob)


_cls_cache = {}


def run(path, out_prefix, limit_per_class=0):
    data, by_class = load(path)

    doc = {'source': path, 'record_classes': {}}
    rows = []
    erp = []

    for cls, recs in sorted(by_class.items(), key=lambda kv: -len(kv[1])):
        _cls_cache[id(cls)] = recs
        sample = [(o, l1, l2, c) for (o, l1, l2, c) in recs[:400]]
        hdr = tune_header(data, sample)
        entries = []
        for off, ss, nums, amts, blob in class_records(data, cls, limit_per_class or None):
            entries.append({'offset': hex(off), 'strings': ss,
                            'numbers': nums, 'amounts': amts})
            if ss:
                rows.append({'class': cls, 'offset': hex(off),
                             'text': ' | '.join(ss), 'amounts': ' '.join(amts)})
            for t in erp_from(ss, amts, cls):
                erp.append(t)
        doc['record_classes'][str(cls)] = {
            'count': len(recs), 'header_offset': hex(hdr),
            'payload_len_range': [min(r[2] for r in recs), max(r[2] for r in recs)],
            'sample_strings': [e['strings'][:6] for e in entries[:3]],
        }
        print(f'  class {cls:<4} {len(recs):>7,} records  hdr={hdr:#x}  '
              f'payload {min(r[2] for r in recs)}..{max(r[2] for r in recs)}')

    with open(out_prefix + '.json', 'w') as fh:
        json.dump(doc, fh, indent=2)
    with open(out_prefix + '.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['class', 'offset', 'amounts', 'text'])
        w.writeheader()
        w.writerows(rows)
    with open(out_prefix + '_erpnext.json', 'w') as fh:
        json.dump(erp, fh, indent=2)
    print(f'\n{len(rows):,} records -> {out_prefix}.csv / .json')
    print(f'{len(erp):,} tagged records -> {out_prefix}_erpnext.json')


DOC_MAP = {'Sale': 'Sales Invoice', 'Invoice': 'Sales Invoice',
           'Quote': 'Quotation', 'Purchase': 'Purchase Invoice',
           'Bill': 'Purchase Invoice', 'Receipt': 'Payment Entry',
           'Payment': 'Payment Entry'}


def erp_from(strings, amounts, cls):
    """Best-effort doctype tagging. Heuristic - review before import."""
    out = []
    for s in strings:
        m = DOC_RE.search(s.encode('latin-1'))
        if m:
            out.append({
                'doctype': DOC_MAP.get(m.group(1).decode(), 'Sales Invoice'),
                'reference': m.group(2).decode(),
                'raw': s,
                'amounts': amounts,
                'source_class': cls,
            })
            continue
        m = ID_RE.search(s.encode('latin-1'))
        if m and amounts:
            kind = 'Received' if s.startswith('Received') else \
                   'Paid' if s.startswith('Paid') else 'Other'
            out.append({
                'doctype': 'Payment Entry',
                'payment_kind': kind,
                'reference': m.group(1).decode(),
                'amount': amounts[0],
                'raw': s,
                'source_class': cls,
            })
    return out


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 0)
