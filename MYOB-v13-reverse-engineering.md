# MYOB Accounting v13 (Australia) — reverse engineering notes

Working dir for binaries: `tools/myob13-installer/` (gitignored, local only). The
6,361 installer files are **not** kept extracted — unpack them from the preserved
archive with `scripts/extract.sh`, which yields `tools/myob13-installer/cab/`.
Source: Internet Archive `myob-accounting-plus-v13`, see `MYOB-v13-finder.md`.

Verified identity: `myob.exe` = FileVersion `7.0.1C`, ProductVersion `13 Australia`,
ProductName `MYOB Accounting for Windows`. Matches the About dialog line-for-line.

---

## 1. Architecture

`myob.exe` is a **Borland C++ Builder / Delphi** binary. PE section names are one per
compilation unit and map directly onto business areas:

```
Analysis  .text  Analysis  ARAP1Cod  ARAP2Cod  ARAP3Cod  ARAP4Cod
CardCode  ChartCod  CheckCod  InvCodeS  PayrollD  PayrollE  PayrollE
PayrollW  .rdata  .data  .rsrc
```

- `ARAP1..4` — Accounts Receivable / Payable (four modules)
- `CardCode` — Cards file (customers / suppliers / employees)
- `ChartCod` — Chart of accounts
- `CheckCod` — Cheques / bank reconciliation
- `InvCodeS` — Inventory
- `PayrollD/E/W` — Payroll (detail / employee / wage)

Borland toolchain is confirmed by the `LZ32.dll` import (Borland LZ runtime) plus
`MFC42.dll` and `MSVCRT.dll` for the mixed third-party components.

### Component map

| File | FileDescription | FileVersion | ProductVersion | Role |
|---|---|---|---|---|
| `myob.exe` | MYOB Accounting Application File | 7.0.1.0 | 13 Australia | Main UI app |
| `MYOBSp32.dll` | MYOB Data Support File | 6.5.0.0 | — | **Data Manager (DM) record API** |
| `ctmyob32.dll` | MYOB Record Manager File | 4.0.0.0 | — | **FairCom c-tree Plus VMS engine** |
| `MYOBIn32.dll` | MYOB INI 32-bit dll | 2.0.0.0 | — | INI / preferences |
| `myobsbt.dll` | MYOB Data - SBCM Filter | 2.4.0.0 | — | Record filter |
| `FtoP.dll` | MYOB Data Upgrade File | 7.0.1B | **12 Australia** | v12 → v13 data converter |
| `PtoP.dll` | MYOB Data Upgrade File | 7.0.1B | — | Premier data converter |
| `MtoM.dll` | MYOB Version 8 Data Upgrade | 8.2.1 | — | v8 → v13 converter |
| `MtoP.dll` | MYOB AccountEdge Data Upgrade | 7.0.1B | **3 Australia** | v3 → v13 converter |
| `MYOBUpg.exe` | MYOB Accounting Data Upgrade | 7.0.0.0 | — | Upgrade orchestrator |
| `MyobPOpt.exe` | MYOB Accounting Data Optimiser | 7.0.0.0 | — | Compacts company file |
| `TemplatesUpgrader.exe` | Templates Upgrader for MYOB | 3.0.3.0 | — | Form templates |
| `BASlink*.dll/.exe/.ocx` | MYOB BASlink v4 (VB6, `MSVBVM60.DLL`) | 4.0.0.x | — | ODBC / data access layer |
| `*.frm` | binary print templates | — | — | e.g. "Tax Inclusive Pre-Printed Invoice" |

The `*toP` / `*toM` DLLs are worth keeping: they are *readers for older company-file
formats* plus writers for v13, so each one is a reference implementation of two formats.

---

## 2. Storage: FairCom c-tree Plus VMS

`ctmyob32.dll` is a **complete c-tree Plus runtime**. Evidence:

- Its 208 exports are c-tree's own API — `ctree`, `ctuseg`, `cttseg`, `ctcatend`,
  `ctgetnod`, `cttestfunc`, `ctrt_filcmp`, `ViewCtreeError`, `ctREG_DEF_ID`,
  `InitCtreeGV` / `SetCtreeGV` / `FreeCtreeGV` / `GetCtreeGV`,
  `ctgetseginfo`, `ctlfsegget`, `ctlfsegput`, `ctSETENCRYPT`.
- Record ops: `WRTREC`, `REDREC`, `ADDREC`, `DELREC`, `NEWREC`, `LSTREC`,
  `NXTREC`, `PRVREC`, `GTEREC`, `LTEREC`, `ESTKEY`, `FRCKEY`, `ORDKEY`.
- File ops: `OPNFIL`, `CLSFIL`, `CREIFIL`, `OPNIFIL`, `DELFIL`, `GETFIL`.
- Index ops: `GETCIDX`, `CREIDX`, `RBLIIDX`, `RBLIFIL`.
- Built-in copyright: `Copyright (c) 1984-1998 FairCom Corporation`,
  `c-tree Plus(R)`.
- It carries c-tree's **own header-dump and rebuild diagnostics**, which enumerate
  the on-disk header fields (see §5).

"ct" is literally c-tree. This also explains the About dialog crediting
FairCom Corp.

### The MYOB layer above it

`MYOBSp32.dll` is a clean record-oriented wrapper ("DM" = Data Manager) with 230
exports. Every function has a `_Name@N` stdcall alias, so argument counts are free
(`_DMBuildKey@20` = 5 args).

| Area | Exports |
|---|---|
| Lifecycle | `DMInitialize`, `DMExit`, `DMOpenFile`, `DMCloseFile`, `DMOpenDataFile`, `DMCloseDataFile`, `DMCreateMYOBDat` |
| Navigation | `DMFirstRecord`, `DMLastRecord`, `DMNextRecord`, `DMPrevRecord`, `DMGTRecord`, `DMLTRecord`, `DMGTERecord`, `DMLTERecord` |
| Record ops | `DMNewRecord`, `DMNewNumberedRecord`, `DMReadRecord`, `DMDeleteRecord`, `DMUseRecord`, `DMUseRecordXtd`, `DMReleaseRecord`, `DMSetRecHandle` |
| Keys | `DMBuildKey`, `DMTransformKey`, `DMUntransformKey`, `DMGetKey`, `DMFirstKey`, `DMNextKey`, `DMGetKey`/`DMLTGetKey` |
| **Schema** | **`DMGetDODANameList`** (c-tree DODA field-definition array), `DMGetConditionalIndexList`, `DMGetAlternateSequence`, `DMGetIndexDupsAllowed` |
| Meta | `DMSetCountryCode`, `DMGetVersionInfo`, `DMGetVersionInfoForFile`, `DMVerifyFile`, `DMGetDODANameList` |
| Counting | `DMGetRecordCount`, `DMCountUsers`, `DMIsFileLocked`, `DMHasExclusiveAccess` |
| Transactions | `DMBeginTransaction`, `DMCommitTransaction`, `DMAbortTransaction`, `DMAddRollbackRecord`, `DMBeginBackup`, `DMEndBackup` |
| Multi-user | `IMInitialize`, `IMRegisterUser`, `IMUnregisterUser`, `IMGetLocalNode` |

`DMGetDODANameList` is the important one: **DODA** is FairCom's Data Object
Definition Array, i.e. the schema. FairCom even ships a `ctinfo` utility whose
sole job is "retrieves IFIL and DODA structures from a FairCom DB file".

---

## 3. Company-file layout

A v13 company is **not a single file**. It is a folder of one c-tree VMS data file
per logical table, plus an index (`idx`) for each, plus a `.prm` preferences file.

Recovered verbatim from the file catalogue embedded in the shipped sample company
`tutorial.dat`:

```
C:\PREMIER7\tutorial.prm
```

Catalogued tables (8.3 stems, so names are truncated):

| Stem | Read as | Likely content |
|---|---|---|
| `tran` | transactions | Transaction headers |
| `line` | transaction lines | Line detail |
| `cards` | cards | Customers / suppliers |
| `cal`, `cacc` | chart of accounts | Account list + config |
| `items`, `inv` | inventory | Items + stock |
| `job` | jobs | Job costing |
| `hist`, `hst`, `shist`, `lshist` | history | Balance history |
| `curcy` | currencies | FX rates |
| `tax` | tax | Tax codes |
| `disc` | discounts | Discounts |
| `memo` | memo | Memo / notes |
| `cmnt`, `contc` | comments / contacts | |
| `jcash`, `rcash` | job cash / receipt cash | Cash tracking |
| `tg` | tax groups | |
| `mtg` | meeting / categories | |
| `alpha` | alphabetic index | A–Z lookup |
| `auto` | auto numbering | |
| `addr` | addresses | |
| `misc`, `msc` | miscellaneous | |
| `pen` | pending | |
| `prcat`, `lst`, `prc` | price categories / lists | |
| `bl` | balance / budgets | |
| `il` | mailing | |
| `rnpr` | reprint | |
| `log` | log | |
| `erms` | terms | Payment terms |

Catalog entry framing (from hex): each entry is
`<flag:1> <8.3 name:8> <4-byte value>` where the flag's high nibble is the
c-tree record type (`0xF6`/`0xF7`/`0xF8`), followed by a matching `idx` entry.
Byte-exact decode still pending confirmation via decompile.

The `.dat` files shipped in the install (`Clearwtr.dat`, `tutorial.dat`) are the two
**sample companies** (Clearwater and Tutorial). Per-table files are created on first
open, so the individual `tran.dat` / `cards.dat` etc. are *not* distributed.

`C:\PREMIER7\tutorial.prm` shows these samples originated in the Premier v7 product
and were reused.

---

## 4. Password / protection system

### What is NOT there

No standard cryptographic constants exist in `myob.exe`, `ctmyob32.dll`,
`MYOBSp32.dll` or `myobsbt.dll`. Searched for and **not found**:

- MD5 / SHA-1 init vectors (`0x67452301`, `0xefcdab89`, `0x98badcfe`, `0x10325476`)
- SHA-1 round constants (`0x5a827999`, `0x6ed9eba1`, `0x8f1bbcdc`, `0xca62c1d6`)
- MD5 T-table (`0xd76aa478`, `0xe8c7b756`, …)
- SHA-256 K (`0x428a2f98`, …)
- Blowfish P-array (`0x243f6a88`, …)
- CRC-32 polynomial (`0xedb88320`)

So there is **no MD5/SHA/DES/Blowfish/CRC anywhere** in the stack. Whatever the
scheme is, it is a custom, home-grown construction. (It turned out to be a
4-byte additive key held as a plain literal in `myob.exe` — see
"Where the key actually lives" in §5. The absence of crypto constants was the
right conclusion; MYOB's answer was to roll its own, badly.)

### The two distinct "passwords"

1. **Company file password** — set via Company Information ("Change passwords, fonts,
   and MYOB parameters"). Stored in the company `.prm`. Failure path string in
   `myob.exe`: `The password you have entered is incorrect.`
2. **Registration serial** — `Help > Register Now`. Gates *write* access;
   unregistered, v13 opens company files read-only.

These are independent. The serial is not a licence unlock in the modern sense — it is
a hardcoded check inside `myob.exe`.

### Available hooks

- `ctSETENCRYPT` in `ctmyob32.dll` — decompiled via REA/Ghidra: it is
  `FUN_100057de(0x1c6)`, i.e. it pushes **raw-function index 470** into c-tree's
  dispatcher. That is FairCom's own optional file encryption, not MYOB code.
  **Verified unused:** `MYOBSp32.dll` — the only module that imports `ctmyob32.dll` —
  imports *none* of `ctSETENCRYPT`, `SECURITY`, `SERIALNUM` or `CTUSER`. MYOB v13
  company files are therefore **stored unencrypted**.
- `SECURITY`, `SERIALNUM`, `CTUSER` exports in `ctmyob32.dll`.
- `DMVerifyFile`, `DMGetVersionInfo` in `MYOBSp32.dll`.
- c-tree's own serial-number field in the file header (visible in the header-dump
  diagnostics) — note this is a c-tree record serial number, unrelated to MYOB
  registration.

### Correction

An earlier read of the odd-looking tables in `ctmyob32.dll`
(`mOMKIGECA?=;9753`, `)*+,-./012345679:;=>?@A8BCD…`) as a possible obfuscation
alphabet was **wrong**. They are c-tree **collating sequences** — key-ordering tables.
The giveaway is the repeating `<char> :<char> :` collation-entry pattern throughout
the region at `0x050000`+.

Status: **not reversed, and moot for the migration.** See §6b - the file is not
encrypted, so the password is not needed to read the data.

What was traced: `myob.exe` imported into Ghidra 12.1.4. The string
`The password you have entered is incorrect.` is at VA `0x00a6d15a`, but it lives in
`.rsrc` (file offset `0x66115a`), not in a code section. Ghidra creates no direct
reference, and there is no absolute-address operand anywhere in the binary pointing at
it. It is a **form-resource string**, so the chain to the check is

    resource string -> MYOB's runtime string table -> use site

To continue: enumerate the resource string table the way `myob.exe` builds it at
startup, find the entry for this string, then take the xref from that table slot.

`Myobres.res` is the resource carrying the About box, and the same mechanism produced
`Tax Table Revision Date:  ^0` (a runtime `^0` substitution token), so the About dialog
and the password dialog are reached the same way.

---

## 5. c-tree on-disk header fields

Recovered from `ctmyob32.dll`'s own header-dump diagnostics — these are the actual
header member names:

```
configuration version      index root ptr            node size
superfile last member#     data record length        extend file size
max bytes per leaf node    max bytes per non-leaf    file mode
key length                 file type                 # of additional members
update flag                index member number       key type
file id number             duplicate flag            server id number
# of active entries        current node ptr          delete stack ptr
index high transaction#    last byte used            serial number
last physical byte         delete type               permanent file mode flags
superfile type             leaf anchor ptr           superfile member #
file flavor                file alignment            key padding byte
maximum name length        header record ptr         resource header ptr
```

Plus extended-header concepts from FairCom's own docs: `XCREblk` (extended creation
block), `DEF_MASK_IFIL2`, `DEF_MASK_XTDPRM`, `DEF_MASK_UNIACS`, `DEF_MASK_HUGEFL`,
`DEF_MASK_HDRSZ4`, and file mode flags `ctFRC2HDRS`, `ctTRANDEP`, `ctFILEPOS8`,
`ctFILCRECHK`.

Sample file header (`tutorial.dat`, first 128 bytes, LE dwords):

| Offset | Value | Note |
|---|---|---|
| `0x00` | `0x000dffff` | flags / marker |
| `0x04` | `0x00000000` | |
| `0x08` | `0x000d898f` | 887,439 — logical size |
| `0x0c` | `0x00000800` | 2048 — page size / hdrsiz |
| `0x10` | `0x0000004f` | |
| `0x14` | `0x00000052` | |
| `0x28` | `0x08000081` | file mode-ish flags |
| `0x2c` | `0x80000000` | |
| `0x30` | `0x02040207` | |
| `0x34` | `0x07ee07e0` | |
| `0x80`–`0x7ff` | all `0xFF` | padding; data starts at `0x800` |

`Clearwtr.dat` has the same layout with `0x0033ffff` / `0x0033a8f9` at offsets
`0x00` / `0x08`.

c-tree record framing (per community reverse-engineering of c-tree v4): first byte is
a record-type tag in the `0xFA`–`0xFF` range (`0xFF` terminates), followed by length
fields, with null-terminated strings.

---

## 6. Schema extracted from the file itself — **done**

The company `.dat` embeds a **self-describing schema**. No Windows needed.

Layout, per table:

1. 8.3 filename pair (`<name>.dat`, `<name>.idx`)
2. a 16-bit field-id enumeration table
3. **length-prefixed field names**, where the declared length is `strlen(name) + 2`
   (the extra 2 bytes are c-tree's field type marker)
4. a `FE FE` c-tree record mark followed by a 12-byte fixed-width name field
   holding the record type with c-tree's `Z` name marker, e.g. `MiscRecZ`, `CardRecZ`

Field names and the record-type name can be **tens of KB apart**, so the association
is *ordinal*, not proximate: merge-join the k-th field-name run with the k-th `*RecZ`.

Parser: `myob13_schema.py` → `myob13_schema.json` (35 record types).

**Validation:** the two independent sample companies (`tutorial.dat`,
`Clearwtr.dat`) yield identical record-type sets and identical field lists for every
record. 41 field runs vs 35 record types, so ~6 runs are not schema records — the
join is approximate at the margins but every record listed below is internally
coherent.

### Record types recovered (35)

| Record | Fields | Maps to |
|---|---|---|
| `ChtAcctRec` | 68 | Chart of accounts — `Opening_Balance`, `Current_Balance`, `Activity00`–`Activity112`, `Budget0`–`Budget6` |
| `CardRec` | 32 | Customer / Supplier / Employee — `Name`, `Card_ID`, `Is_Inactive`, `First_Address`…`Fifth_Address`, `Terms`, `Currency`, `Payment_Method`, `Hourly_Cost`, `Billing_Rate`, `Default_Account`, `Salesperson` |
| `CTranRec` | 41 | Transaction header — `Amount`, `Account`, `Card`, `Reference`, `Sale_Purchase`, `Transaction_Date`, `Journal`, `Period`, `Year`, `Currency_Tag`, `Status`, `Source`, `Memo`, `Reconciliation_Date` |
| `ILRec` | 24 | Transaction line — `Quantity`, `Price`, `Discount`, `Amount`, `Cost`, **`Parent`** (FK → `CTranRec`), `Item`, `Job`, `Account`, `Tax_Code`, `Line_Type` |
| `ItemsRec` | 73 | Inventory items |
| `InvRec` | 35 | Inventory / stock on hand |
| `JobRec` | 108 | Job costing |
| `LogRec` | 11 | Activity log |
| `TaxRec` | 14 | Tax calculation detail |
| `TxCodRec` | 15 | Tax codes — `Rate`, `ECRate`, `Tax_Threshold`, `Collected_Account`, `Paid_Account` |
| `RInvRec` | 25 | Receipt / invoice |
| `RILRec` | 22 | Receipt / invoice line |
| `RCashRec`, `JCashRec` | 28, 18 | Cash tracking |
| `PRCatRec`, `PRLstRec`, `PRHstRec`, `PRMiscRec`, `PRPensnRec`, `PRTaxRec`, `PRTblRec` | 8–34 | Payroll: categories, lists, history, pension schemes, tax, tax tables |
| `CalRec`, `SHistRec`, `JHistRec`, `IHistRec`, `MemoRec`, `AddrRec`, `IpTxtRec`, `AlphaRec`, `AutoRec`, `CmntRec`, `TermsRec`, `SlipRec`, `ConsTCRec` | 7–46 | Calendar, history, memos, addresses, payment terms, etc. |

Authenticity check: MYOB's own schema contains the typo **`Foruth_Address`** in
`CardRec`, and `Desposit_Status` in `CTranRec` — consistent with real 2003 source.

---

## 6a. The `.prm` question — answered from MYOB's own docs and a real backup

**MYOB v13's "Create Backup" produces no `.prm` at all.** Verified against a real
company backup (`MYOB-backup-2026-10-02T17-52.ZIP`, 382 entries): it contains the
company `.dat` plus the user's `myob13/` folder (229 `.xlt` Excel export templates,
87 `.frm` forms, 11 `.wpt`, 10 `.dot`, 8 `.rpt`, images) and nothing else. No `.prm`,
no `.ini`.

### What MYOB's help says the password is

From the shipped help (`company_25/27/48/49/50/51/52.htm`, `tips_162.htm`):

- The security system is a **master password plus sub-passwords**.
- *"You can have only one master password in a single company file."* — so it is
  **per-company-file**, not a global application setting.
- *"If your system uses passwords, you'll enter the password when you start Accounting
  or switch from one company file to another"* — matches the Sign-on dialog.
- **Stored in plaintext:** *"Click Edit. The Set Up Passwords window appears,
  displaying the password."*
- Passwords gate *operations* (delete a sale, print cheques, payroll, Easy Setup), not
  data access — consistent with the file being readable without one.
- Forgotten master password: MYOB support will *"examine your company file and provide
  you with the needed password"* for a fee — i.e. it is extractable from the file.
- Reached via **Preferences window → Security view → Passwords** button.

### Where it actually lives

Not in the DODA records (no password field in any of the 35 record types), and not in
the file header. Differential comparison of the company-info record against the
*unlocked* sample (`Clearwtr.dat`) shows the protected company file has **extra linked
sub-records** the unlocked sample does not — three c-tree record pointers
(`0x258b4d`, `0x257716`, `0x256d56`) where Clearwtr has none:

```
Clearwtr.dat   0x07f971  (all zero)                  0x07f9bd  ff ff ff ff
real .dat     0x075a31  4b 00 00 00                 0x075a71  00 00 ff ff
                                          + ptr 0x258b4d / 0x257716 / 0x256d56
```

So the security/password data lives in a **linked record hanging off the company-info
record**, not in a `.prm`. Locating it exactly needs either a reference company with a
known password for diffing, or decompiling the security code path in `myob.exe`.

## 6c. Master password storage — SOLVED

Cracked by differential analysis against a controlled reference pair: the same
company created twice, once without a password and once with the master password
`TESTPW123` (`clear.dat` vs `password.dat`). The two files are
byte-for-byte the same size and differ in only 1,149 bytes across 180 regions. Exactly
one of those regions is a **706-byte `FA FA` record** at `0xb1000` that is pure `ff`
(never written) in the unprotected file.

The password is **plaintext**, obfuscated by a fixed 4-byte **additive** key:

```
stored[i] = (plaintext[i] + KEY[i % 4]) & 0xFF
KEY       = 8D 96 9D 95        (141 150 157 149)
```

Observed directly:

```
offset  stored  plaintext  delta
  +00    e1       T  'T'    8D
  +01    db       E  'E'    96
  +02    f0       S  'S'    9D
  +03    e9       T  'T'    95
  +04    dd       P  'P'    8D    <- key cycles
  +05    ed       W  'W'    96
  +06    ce       1  '1'    9D
  +07    c7       2  '2'    95
  +08    c0       3  '3'    8D
```

### Record layout

| offset | size | value |
|--------|------|-------|
| +0x00  | 2    | `fa fa` c-tree data record mark |
| +0x02  | 4    | `len1` = 706, total record length |
| +0x06  | 4    | `len2` = 688, payload length (`len1 - len2 == 18`) |
| +0x0A  | 4    | class = 2 |
| +0x0E  | 84   | index key (varies per file) |
| +0x62  | var  | **stored password**, NUL terminated, additive key applied from phase 0 |
| +0x62+ | rest | all zero — sub-password list; empty here, so no sub-passwords |

### Where the key actually lives: `myob.exe` and `myobsbt.dll`

Earlier revisions of this document attributed the key to `MYOBSp32.dll`. **That is
wrong.** Scanning all 24 byte-order permutations, `MYOBSp32.dll` (180 KB) and
`ctmyob32.dll` (344 KB) contain the sequence **zero** times. It is a literal in the
two Borland-compiled MYOB modules:

- **`myob.exe`** — `.data` string pool, four identical NUL-padded copies
- **`myobsbt.dll`** — `.data` string pool, one copy

```
myob.exe      file 0x3a8af0   VA 0x7A8AF0   (imagebase 0x00400000)
              8d 96 9d 95 00 00 00 00   x4 at 0x7A8AF0 / AF8 / B00 / B08
myobsbt.dll   file 0x05e21c   VA 0x1005E21C (imagebase 0x10000000)
              8d 96 9d 95 00 00 00 00   (sits between "alpha" and "MYOBDataHandler:")
```

Both are read through Borland's signed-`mod` codegen for `i % 4` — which is also
what pins the toolchain as Borland C++ Builder (`Analysis` PE sections, `.?AV`
RTTI descriptors, no `MSVBVM60`/`borlndmm` import because the RTL is statically
linked):

```asm
xor   ecx, ecx
mov   edx, ecx
and   edx, 0x80000003        ; ecx & 3, sign-corrected
jns   +5
dec   edx
or    edx, 0xFFFFFFFC
inc   edx
mov   dl, byte ptr [edx + 0x7A8AF0]   ; KEY[i mod 4]
mov   bl, byte ptr [ecx + esi]         ; plaintext byte
add   bl, dl                          ; or: sub bl, dl
mov   byte ptr [ecx + esi], bl
inc   ecx
cmp   ecx, eax
jl    loop
```

`myob.exe` — four routines, two encrypt and two decrypt:

| VA | operation | key literal | role |
|---|---|---|---|
| `0x635FE4` | `add bl, dl` | `0x7A8AF0` | encrypt, in place on a byte buffer |
| `0x63603E` | `add bl, dl` | `0x7A8AF8` | encrypt, string variant |
| `0x636094` | `sub bl, dl` | `0x7A8B00` | decrypt, byte-buffer variant |
| `0x6360EE` | `sub bl, dl` | `0x7A8B08` | decrypt, string variant |

The string wrappers sit at `VA 0x636000` (encrypt, 6 call sites) and `VA 0x6360B0`
(decrypt, 1 call site at `0x686D39`). These four are the only key-lookup loops in
the executable.

`myobsbt.dll` — one routine, `VA 0x1000E6D0`, decrypt only. It is a class method
(`thiscall`, `ret 4`) guarded by a virtual predicate:

```asm
mov  eax, [ecx]          ; vtable
call [eax + 0x28]        ; virtual guard -- skip unless true
test al, al
je   <done>
...
repne scasb              ; strlen the password
...
mov  cl, byte ptr [ecx + 0x1005E21C]
sub  bl, cl
```

So the scheme is MYOB's single general-purpose obfuscation helper, linked into
both the application and the business-tools DLL, and applied to the master password
and the sub-password list alike.

This also settles §4's "no cryptography" finding: the key is not a crypto constant
at all. `8D 96 9D 95` matches no CRC32 / Adler32 / djb2 / FNV / sdbm / MD5 / SHA of
any MYOB-, product- or version-related string, is not readable in any 8-bit
codepage (`0x8D` and `0x9D` are unassigned in Windows-1252), and has no arithmetic
pattern (deltas `+9, +7, −8`). It is an arbitrary opaque literal — all four bytes
have the high bit set, consistent with a developer picking deliberately
non-typeable "random" values.

The key is a compile-time constant, not derived from the company name, file ID or
any file property. Confirmed by recovering the 9-character reference password from
one test company and a 6-character password from an unrelated company, using the
same key.

### Result for the real company file

```
$ python3 myob13_password.py company.dat
master password @ 0x7a95e -> '<redacted 6-char value>'
```

The scheme was confirmed on that file (a 6-character password, independent of the
9-character reference), and the record contained **no sub-passwords**, so the
master password grants full access.

> The recovered value is **deliberately redacted** from this document. It is a
> live credential; re-run the tool to obtain it rather than copying it from here.

### Tool

`myob13_password.py` — validated 4/4: recovers the known reference password from the protected
file, and correctly reports the unprotected reference plus both shipped sample
companies (`Clearwtr.dat`, `tutorial.dat`) as having no password.

Two implementation traps worth recording:

1. The stored form is NUL terminated, so truncate at the first raw `0x00` **before**
   decoding. Decoding a run of NULs wraps into the printable string
   `sjcksjcksjc...` (because `0x00 - 0x8D = 0x73 = 's'`), which floods the output with
   false positives.
2. `len1 == 706 && class == 2` is not unique — around 32 records in the real file
   match that shape. A minimum password length of 4 characters is needed to reject
   one-byte coincidences.

## 6b. The password does not protect the data

Tested against a real 70 MB company file (company and customer details redacted). **It is not encrypted** — every record is
in cleartext:

```
<company name redacted>
Sale #00011696 for $258.50
<address redacted>
<customer names redacted>
```

So the password is an application-level gate checked by `myob.exe` at open time, not a
key over the records. **A lost password costs access through the MYOB UI, not access to
the data.** This is the single most important practical finding for the migration: the
file is recoverable without ever recovering the password.

---

## 6c. Record framing (decoded)

c-tree VMS data record:

```
<FA FA> <len1:u32> <len2:u32> <class:u32> ...header... <payload: len2 bytes>
```

- `FA FA` — data-record mark. `FE FE` — resource record (holds the schema/catalogue).
- `len1` — stored record length; `len2` — payload length; always `len1 - len2 == 18`.
- `class` (`len3`) — record-family discriminator.
- Payload begins after a header whose size **varies by record class**, because the
  header carries the index key. Observed 0x18–0x28. Auto-tuned per class by choosing
  the alignment that yields the most complete NUL-terminated strings.
- Fields inside the payload are a mix of fixed binary values and NUL-terminated
  strings, so records are **not** purely NUL-delimited — a naive token count does not
  match the schema field counts.

Records sharing a `(class, payload_len)` pair are the same record type. In the real
company file this yields 137,447 records across 2,680 classes, and the classes are
self-describing by content:

| Class | Count | Content |
|---|---|---|
| 4 | 32,395 | Sales / Payments / Purchases (`Sale #00010377 for $495.00`) |
| 28 | 30,373 | numeric activity records |
| 14, 15 | 44,130 | index structures |
| 6 | 9,890 | addresses + short cards (`511 Pacific Highway, Mt Colah, NSW 2079`) |
| **22** | **2,344** | **Cards** — customer/supplier master, fixed 352-byte payload |
| 38, 24, 32, 30 | 10,420 | further record types |

Card records contain `Name`, `Search_Name`, `Card_ID` and a trailing auto-numbered
numeric card ID (little-endian, sequential).

### Customer master (built)

`myob13_customers.py` uses the class-22 card headers as the authoritative card
list, then enriches from class-6 per-card detail records by name match. On the
real company file this yields **2,152 customers** with names, some contacts and
emails extracted.

Address and ABN enrichment is weak (only ~50 addresses, 1 ABN recovered) because
addresses sit in a different record type and the field-offset decode is not yet
resolved. Customer *names* are complete and clean.

### Partial decode still outstanding

The per-field descriptor table (2×`u16` per field, immediately preceding the field
names) was located but **not yet correctly aligned** — `First_Address` is measured at
40 bytes while the table yields 59, so there is an offset or ordering error to
resolve. Until that is done, field-level typing of numeric/date values is
heuristic.

---

Three options, in increasing order of effort:

### A. Use MYOB's own exports (least work, most reliable)
MYOB v13 has extensive CSV / report export. Open the company in MYOB and export Cards,
Transactions + lines, Chart of accounts, Payroll. Then map CSV → ERPNext doctypes.
This is what commercial MYOB→Xero migration tools actually do.

### B. Call `MYOBSp32.dll` directly (best fidelity)
Self-contained exported Win32 API. Load it (32-bit) and drive
`DMInitialize` → `DMOpenDataFile` → `DMGetDODANameList` → `DMFirstRecord` /
`DMReadRecord`. Needs a 32-bit Windows or Wine environment.

### C. Pure-Python reader (no Windows) — **now viable**
The format is identified, the header fields are known, and the schema is
self-describing. Remaining work: the record payload layout (offset/type/length per
DODA field) and key/index walking. The 16-bit enumeration table preceding each field
list likely encodes field ids/types.

---

## 7. Tooling

Everything below lives under `tools/` in this repository, which is **gitignored**
and local-only — with one exception: `tools/README.md` is tracked, so there is
always a human-readable description of what belongs here. Installed archives are
kept; their extracted trees are not, so run `scripts/extract.sh` first (it is
idempotent — it skips anything already unpacked, and `scripts/extract.sh --check`
reports what it would do without doing it).

- **REA** (`rea`, v6.5.0) — installed via `npm i -g rea-agents`, so it lives in
  `~/.local/lib/node_modules/rea-agents`, not in `tools/`. Evidence-oriented RE CLI
  wrapping Rizin/Ghidra. `rea doctor` reports the opencode MCP registration as
  missing; `rea setup` would fix it but needs a client restart.
- **Ghidra 12.1.4** — archive at `tools/ghidra/ghidra.zip`; unpack to
  `tools/ghidra/ghidra_12.1.4_PUBLIC/` (12.1.x is what REA requires). Set
  `GHIDRA_INSTALL_DIR` to make REA's ghidra provider available.
- **Temurin JDK 21** — archive at `tools/jdk21.tar.gz`; unpack to `tools/jdk21/`.
  Ghidra needs a full JDK (the system JREs had no `javac`).
- **MYOB v13 installer** — archive at `tools/myob13-installer/Data1.cab` (54 MB, 6,361
  files); unpack to `tools/myob13-installer/cab/`. `myob.exe` (sha256
  `f53e2190872c3d2f8046b7384139a80002939bf0e71e137d7eaf68d7cf539c35`) and the analysed
  `MYOBSp32.dll` / `ctmyob32.dll` / `myobsbt.dll` all come out of it.
- **Ghidra project** — was at `tools/ghidra-project/`; deleted as re-derivable.
  Rebuild it by importing `tools/myob13-installer/cab/myob.exe` into a fresh project
  and running `analyzeHeadless` (~5 minutes for this binary).
- **REA output** — `tools/rea/` holds the `gh-*.log` runs, `*-analyze.json`,
  `*.snap` and the schema dumps (`clearwtr_schema.json`, `ctsetenc.json`,
  `myob_cdx_*.txt`, `help_myob.txt`).
- **Ghidra post-scripts** — `scripts/find_xref.py` and `scripts/FindXref.java` are
  the same tool written both ways (Python and Java Ghidra scripts): find a string,
  list what references it, and decompile the referencing functions. Both are
  tracked in git.
- **`tools/misc/`** — deliberately *not* tracked. Holds `scrub.sh`, the one-shot
  `git filter-branch` filter used to redact the publisher's identifiers, and
  `myob-prefilter.bundle`, a bundle of the pre-redaction history. Both contain the
  personal identifiers that redaction removed, so neither belongs in the
  repository.

Extraction was verified before the trees were dropped: Ghidra's 5,219 files and
the installer's 6,361 files match their archives by name, size **and** CRC32, and
`gzip -t` passes on `jdk21.tar.gz`.

## 9. Open questions

- [x] Which storage engine — FairCom c-tree Plus VMS, `ctmyob32.dll`
- [x] Which layer MYOB sits on — `MYOBSp32.dll` DM record API
- [x] Company file layout — folder of per-table `.dat`/`.idx` + `.prm`
- [x] Record-type names and field names — 35 record types extracted and validated
- [x] Whether c-tree file encryption is used — **no**, verified via imports
- [ ] Field offset/type/length per record (needs record payload decoding)
- [ ] Company file password scheme — string traced to `.rsrc`, indirection unresolved
      (moot: file is unencrypted)
- [ ] Registration serial check (needs `myob.exe` decompile)
