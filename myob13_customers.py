#!/usr/bin/env python3
"""Build a customer/supplier master from a MYOB v13 company file.

Card master data lives in record class 6 (the per-card detail records) and
class 22 (the card header). Each class-6 record carries the card name, the
contact, the postal address, and a free-text card block that in practice
contains the ABN and phone numbers.

Emits ERPNext Customer / Supplier rows.
"""
import csv
import json
import re
import sys

from myob13_extract import scan

ADDR_RE = re.compile(r'[A-Z]{2,3}\s+\d{4}')
ABN_RE = re.compile(r'\b\d{2}\s?\d{3}\s?\d{3}\s?\d{3}\s?\d{3}\b|\b\d{11}\s\d{4}\b')
PH_RE = re.compile(r'(?:PH\.?|Tel\.?|Mob\.?|Fax)\s*[.:]?\s*([0-9][0-9 \-()]{6,})', re.I)
EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
WEB_RE = re.compile(r'(?:www\.|https?://)[\w./-]+')
TRANSACTION_RE = re.compile(r'^(Sale|Purchase|Invoice|Receipt|Payment|Bill|Cheque)\s*;\s*')


def _first(rx, text):
    m = rx.search(text or '')
    return m.group(0) if m else ''


def parts(blob, hdr):
    return [p for p in blob.split(b'\x00')
            if p and all(32 <= b < 127 or b in (13, 10) for b in p)]


def card_records(data, cls):
    """Yield the decoded text parts of every record in a class."""
    for off, l1, l2, c in scan(data):
        if c != cls:
            continue
        best = None
        for hdr in (0x18, 0x1c, 0x20, 0x24, 0x28):
            p = parts(data[off + hdr:off + hdr + l2], hdr)
            score = sum(len(x) for x in p)
            if best is None or score > best[0]:
                best = (score, p)
        yield off, l2, best[1]


NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ,.'&()/-]{3,60}$")


def header_cards(data):
    """Class 22 records are the authoritative card headers (fixed 352 bytes).

    Each yields Name, Search_Name, Card_ID and a trailing auto-numbered
    little-endian card ID."""
    out = {}
    for off, l1, l2, c in scan(data):
        if c != 22:
            continue
        best = None
        for hdr in (0x18, 0x1c, 0x20, 0x24, 0x28):
            ps = parts(data[off + hdr:off + hdr + l2], hdr)
            strs = [p.decode('latin-1').strip() for p in ps
                    if all(32 <= b < 127 for b in p)]
            good = [t for t in strs if NAME_OK.match(t)]
            if best is None or len(good) > len(best):
                best = good
        if not best:
            continue
        out[best[0]] = {'offset': hex(off)}
    return out


def build(path):
    data = open(path, 'rb').read()
    cards = {n: {'contact': '', 'address': '', 'abn': '', 'phone': '',
                 'email': '', 'website': '', 'notes': ''}
             for n in header_cards(data)}

    for off, l2, ps in card_records(data, 6):
        texts = [p.decode('latin-1').strip() for p in ps]
        texts = [t for t in texts if len(t) > 1]
        if not texts:
            continue
        head = texts[0]
        m = TRANSACTION_RE.match(head)
        name = TRANSACTION_RE.sub('', head).strip() or head
        if not NAME_OK.match(name) or name not in cards:
            continue
        rest = texts[1:]

        address = next((t for t in rest if ADDR_RE.search(t)), '')
        contact = ''
        notes = ''
        for t in rest:
            if t is address:
                continue
            if not contact and '\r' not in t and '\n' not in t and len(t) < 40:
                contact = t
            elif '\r' in t or '\n' in t or len(t) > 40:
                notes = (notes + ' ' + t).strip()
                if not contact and '\n' not in t:
                    contact = t.split('\r')[0].split('\n')[0].strip()

        blob = ' '.join(rest)
        cards[name].update({
            'contact': contact,
            'address': address.replace('\r\n', ', ').strip(' ,'),
            'abn': _first(ABN_RE, notes),
            'phone': ' '.join(dict.fromkeys(PH_RE.findall(notes))),
            'email': ' '.join(dict.fromkeys(EMAIL_RE.findall(notes))),
            'website': ' '.join(dict.fromkeys(WEB_RE.findall(notes))),
            'notes': re.sub(r'\s+', ' ', notes)[:400],
        })

    print(f'{path}: {len(cards):,} cards from class 6')
    with_abn = sum(1 for v in cards.values() if v['abn'])
    with_addr = sum(1 for v in cards.values() if v['address'])
    with_ph = sum(1 for v in cards.values() if v['phone'])
    print(f'  with address {with_addr:,}   with ABN {with_abn:,}   with phone {with_ph:,}')

    rows = []
    for name, v in sorted(cards.items()):
        rows.append({
            'doctype': 'Customer',
            'customer_name': name,
            'contact_person': v['contact'],
            'address': v['address'],
            'abn': v['abn'],
            'phone': v['phone'],
            'email': v['email'],
            'website': v['website'],
            'notes': v['notes'],
        })

    out = path.rsplit('.', 1)[0]
    with open(out + '_customers.json', 'w') as fh:
        json.dump(rows, fh, indent=2)
    with open(out + '_customers.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f'  wrote {out}_customers.json / .csv')
    return rows


if __name__ == '__main__':
    rows = build(sys.argv[1])
    for r in rows[:8]:
        print('  ', json.dumps(r, ensure_ascii=False)[:190])
