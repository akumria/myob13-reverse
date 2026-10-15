# Identifying and obtaining MYOB v13 (Australia) — matching the About dialog

## 1. What the screenshot is

| About-box field | Value |
|---|---|
| Window title | `About MYOB Accounting for Windows` |
| Product | `MYOB Accounting for Windows` |
| Version | `13` |
| Release | `7.0.1C` |
| Market | `Australia Release` |
| Tax Table Revision Date | `1/07/2002` |
| Copyright | `© 1989-2003 MYOB Technology Pty Ltd` |
| Portions | `© 1984-1997 FairCom Corp.` |
| Portions | `© Streetwise Software` |
| Images | `© PhotoDisc, Inc.` |
| Portions | `© 1999-2000 The Apache Software Foundation` |

This is the **final Australian service release of MYOB Accounting v13**, built **Feb–Mar 2003**
and carrying the **2002–03 year PAYG tax tables** (effective 1 July 2002).

> Note: the *Plus* product in this era also branded its About box `MYOB Accounting for
> Windows` — there is no separate "Plus" string in the dialog. See §3.

## 2. Where to get it

**Internet Archive item `myob-accounting-plus-v13`** — the only complete, freely
downloadable v13 AU build I could locate.

| | |
|---|---|
| Item page | <https://archive.org/details/myob-accounting-plus-v13> |
| Direct download | <https://archive.org/download/myob-accounting-plus-v13/MYOB%20Accounting%20Plus%20v13.zip> |
| Size | 60,454,660 bytes |
| SHA-256 | `08b70f69522824949e8b2be22bbcfb87ee10d92b5923c53dfe6fb778a732d8c1` |
| MD5 | `0cae4af82e4ea596081e9f1e39befbe2` |
| Published | 2024-04-14, uploader `(email omitted)` |
| Build date | MSI + cab stamped `2003-03-21` |

### Zip contents

```
54,795,465  2003-03-21  Data1.cab                        <- application payload
 2,680,072  2003-03-21  MYOB Accounting Plus v13.msi     <- installer
         0              update/
   995,991  2009-11-10  update/AccPlus_v13_TaxTable_Update.exe
       384  2006-11-19  update/list.txt
 4,389,256  2009-11-10  setup.exe                        <- InstallShield bootstrapper
   163,840  2009-11-10  autorun.exe
    46,080  2008-03-26  ftoolapp.exe
       766  1999-10-19  MYOB.ico
        44  1999-12-24  autorun.inf
        62             MYOB Serial.txt
```

Inner hashes:

```
8628c20bfa2b04f069f11afd3ec0e62c96025adf2982b7c6fd24d8ab15d23f73  MYOB Accounting Plus v13.msi
602168cb7d2f0f193c798a84a433db2e02a1f28d4f0917262d82b8220b41d593  update/AccPlus_v13_TaxTable_Update.exe
f53e2190872c3d2f8046b7384139a80002939bf0e71e137d7eaf68d7cf539c35  Data1.cab -> myob.exe
```

## 3. Proof it is the exact build

### 3a. PE version resource of `Data1.cab → myob.exe`

Parsed with `pefile` (`Data1.cab` expands to 6,361 files; `myob.exe` is 6,692,864 bytes, `2003-02-19`):

```
CompanyName      = MYOB Australia, Pty Ltd.
FileDescription  = MYOB Accounting Application File
FileVersion      = 7.0.1C                 <-- matches "Release 7.0.1C"
InternalName     = MYOBP
LegalCopyright   = (c) MYOB Limited, 2002
ProductName      = MYOB Accounting for Windows
ProductVersion   = 13 Australia           <-- "Version 13" + "Australia Release"
OriginalFilename = myob.exe
```

`ProductVersion = 13 Australia` is exactly what the dialog renders as
**Version 13 / Australia Release**.

### 3b. About-form string table (UTF-16LE, `myob.exe`)

```bash
strings -a -el myob.exe | sed -n '660,700p'
```

```
About MYOB Accounting for Windows        <-- dialog title (matches screenshot)
MYOB Accounting for Windows
Version 13
Release 7.0.1C
Copyright  1989-2003 MYOB Technology Pty Ltd
Portions Copyright  1984-1997 FairCom Corp., All Rights Reserved
Portions Copyright  Streetwise Software
Some Images  PhotoDisc, Inc.
Portions Copyright  1999-2000 The Apache Software Foundation, All Rights Reserved
MYOB is a registered trademark of MYOB Technology Pty Ltd.
```

Line-for-line identical to the screenshot, including the `1989-2003` and
`1999-2000` copyright ranges.

### 3c. Runtime tax-table date

The label lives in the VB6 form resource, with a runtime substitution token:

```
Myobres.res:23353  Tax Table Revision Date:  ^0
Myobres.res:23354  Preferences	MYOBP.INI
```

`^0` is filled at runtime from the installed tax-table set / company file — it is
**not** a compiled-in literal, so `1/07/2002` cannot be grepped out of the
payload. For this Feb-2003 AU build the stock tables are the 2002–03 set
(effective 1 July 2002), which is consistent with the screenshot. I did **not**
independently verify this one field at runtime; everything else in §3a/§3b is
verified byte-for-byte.

## 4. Installing

This is a 2003 32-bit MSI. The uploader's included guide says it was tested on
**Windows 10 22.04** and gives these steps.

1. Extract the zip.
2. Right-click `setup.exe` → **Properties** → **Compatibility** → tick
   *Run this program in compatibility mode for:* → **Windows XP**.
   (Bypass this if you install the `.msi` directly with `msiexec`.)
3. Run `setup.exe` and follow the prompts.
4. Create a new company file (record creation walks you through it).
5. **Help → Register Now** is required before you can *write* to a company file;
   unregistered, v13 opens files read-only.
6. Check **Help → About** — you should see `Version 13 / Release 7.0.1C /
   Australia Release`.

### Keeping the About box identical to the screenshot

**Do not run `update/AccPlus_v13_TaxTable_Update.exe`.** It ships newer PAYG tables
and will change the Tax Table Revision Date away from `1/07/2002`.

### Licensing

The archive item bundles a serial (`MYOB Serial.txt` / `update/list.txt`) that is
a well-known warez serial, **not** a legitimate licence. MYOB dropped support for
v13 long ago — MYOB's current policy is that they no longer support any version
more than 3 years old. Treat this as an unsupported read/convert environment:
fine for opening legacy files and extracting data, not for producing anything
you intend to lodge or rely on for PAYG figures.

## 5. What I checked and ruled out

| Source | Result |
|---|---|
| `myob.com/au/support/downloads` (current) | AccountRight 2013+ only; nothing pre-v16. Page explicitly says no install help for unsupported products. |
| Wayback CDX, `myob.com.au` 2001–2004 | Only **update** patches archived, never a full Accounting v13 installer. Closest: `downloads2.myob.com.au/MYOB_AccPlus_v13_Update.exe` (2003-08-01), a service patch that needs a base install. |
| Wayback CDX, `downloads.myob.com.au` / `downloads2.myob.com.au` | Full directory listings; tax-table updates, `MYOBTax2002v531_WebUpdate.exe`, `Premier v7 Update`, etc. No v13 Accounting base. |
| Wayback, `help.myob.com.au/acct13/win/*` | v13 help site is archived (intro pages, PDFs, help topics) but contains **no release-notes page**, so "7.0.1C" isn't corroborated there. |
| Wayback, `myob.com.au/products/testdrives/accounting/download.shtml` | Test-drive page archived; Accounting v13 test-drive `.exe` was never captured. (`AccPlus_v13TD.exe` for *Plus* was.) |
| archive.org software corpus (34 MYOB items) | Only `myob-accounting-plus-v13` matches v13. Others: `myob_last` (Premier v7), `myob-td-2007.7z`, `myob-account-edge-v-5`, `myob-account-edge-v-6`, `account-right-plus-v-19`, `setup_20260214` (AccountEdge Pro 13 **for Mac** — unrelated). |
| software.informer `myob-accounting-v13` | Index page exists (exe `Myob.exe`, versions "13" / "13.0") but the download button just redirects to `myob.com.au`. No direct binary. |
| Search for a standalone **non-Plus** "MYOB Accounting v13" | **Nothing found.** Given §3a/§3b the Plus build's About box is byte-identical to the screenshot, so this gap is cosmetic (`InternalName = MYOBP`), not functional. |

### Related reference material

- **Third-party tax tables for v13** — <http://www.frasergroup.org/myob.htm>.
  Confirms **v13 is the last MYOB version with a plain-text, user-amendable tax
  table** (v14+ obfuscated it). Paid, AU$52. Would break the `1/07/2002` match.
- **MYOB ODBC driver mapping** — v13-era AU driver is `MYOB_ODBC_AUS7`
  (Premier v11 / Accounting Plus v17); older pairing `MYOB_ODBC` v6.0.14 for
  Accounting Plus v16 / Premier v10. Useful if the goal is scripted data
  extraction rather than the GUI.

## 6. Reproducing the verification

```bash
mkdir -p /tmp/myob13 && cd /tmp/myob13
curl -LO "https://archive.org/download/myob-accounting-plus-v13/MYOB%20Accounting%20Plus%20v13.zip"
sha256sum "MYOB Accounting Plus v13.zip"
# 08b70f69522824949e8b2be22bbcfb87ee10d92b5923c53dfe6fb778a732d8c1

unzip -q "MYOB Accounting Plus v13.zip"
7z x -y -ocab Data1.cab

strings -a -el cab/myob.exe | sed -n '660,700p'   # About-box string table
python3 -c "import pefile;pe=pefile.PE('cab/myob.exe');[print(k.decode(),'=',v.decode()) for e in pe.FileInfo for t in e.StringTable for st in t.StringTable for k,v in st.entries.items()]"
```
