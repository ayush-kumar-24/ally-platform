"""Give the Word tables sensible column widths, and use the full page.

Pandoc writes every table with equal column widths. In these documents that is
badly wrong: the five-column field tables become Field | Type | Req | Key |
Notes, where Req holds the word "Yes" and Notes holds a sentence, and both get
20% of the width. The Notes column wraps into a tall narrow ribbon and the
table only occupies 5.50 of the 6.27 inches available.

So this rewrites each table's grid after conversion, choosing a width profile
from the table's own header row rather than from its column count -- a
six-column table in the ER document is the table summary and a six-column
table in the entity mapping is the entity index, and they want different
splits.

A table whose header matches nothing known gets a graduated fallback rather
than equal widths: narrow first column, widest last, which is the right shape
for nearly every table here (an identifier followed by prose).

Run:  python3 scripts/docs/fix_docx_tables.py file.docx [more.docx ...]
"""
from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

A4_PORTRAIT_USABLE = 11906 - 1440 - 1440  # page width less 1in margins = 9026

#: header signature (lowercased, joined by |) -> percentage per column.
#: Percentages must sum to 100; asserted below, because a profile that sums to
#: 90 silently shrinks the table and that is the bug this file exists to fix.
PROFILES: dict[tuple[str, ...], tuple[int, ...]] = {
    ("field", "type", "req", "key", "notes"): (20, 12, 6, 17, 45),
    ("#", "table", "part", "cols", "rows", "purpose"): (4, 20, 6, 6, 7, 57),
    ("#", "entity", "part", "purpose", "owned by", "reaches"): (4, 16, 5, 32, 21, 22),
    ("child table", "column(s)", "parent table", "on delete"): (30, 26, 30, 14),
    ("table", "july 2026", "now", "change"): (34, 16, 14, 36),
    ("marker", "meaning"): (26, 74),
    ("table", "referenced by"): (60, 40),
    ("", "count"): (70, 30),
    ("", "july 2026", "now", "change"): (34, 16, 14, 36),
    ("", ""): (30, 70),
}


def header_signature(tbl_xml: str) -> tuple[str, ...]:
    first_row = re.search(r"<w:tr[ >].*?</w:tr>", tbl_xml, re.S)
    if not first_row:
        return ()
    cells = re.findall(r"<w:tc>.*?</w:tc>", first_row.group(0), re.S)
    out = []
    for c in cells:
        text = "".join(re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", c, re.S))
        text = re.sub(r"<[^>]+>", "", text)
        out.append(text.strip().lower())
    return tuple(out)


def profile_for(sig: tuple[str, ...], ncols: int) -> tuple[int, ...]:
    if sig in PROFILES and len(PROFILES[sig]) == ncols:
        return PROFILES[sig]
    # Graduated fallback: first column narrow, last widest. Equal widths are
    # never right for these tables, so never fall back to them.
    if ncols == 1:
        return (100,)
    weights = [1 + i * 0.9 for i in range(ncols)]
    total = sum(weights)
    pcts = [max(5, round(wt / total * 100)) for wt in weights]
    drift = 100 - sum(pcts)
    pcts[-1] += drift
    return tuple(pcts)


def widths_from(pcts: tuple[int, ...], usable: int) -> list[int]:
    cols = [round(usable * p / 100) for p in pcts]
    cols[-1] += usable - sum(cols)  # absorb rounding so the sum is exact
    return cols


def fix(path: Path) -> tuple[int, int]:
    tmp = path.with_suffix(".tmp.docx")
    changed = 0
    seen = 0
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(
            tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                xml = data.decode("utf-8")
                out: list[str] = []
                pos = 0
                for m in re.finditer(r"<w:tbl>.*?</w:tbl>", xml, re.S):
                    seen += 1
                    tbl = m.group(0)
                    grid = re.search(r"<w:tblGrid>.*?</w:tblGrid>", tbl, re.S)
                    if not grid:
                        continue
                    ncols = len(re.findall(r'w:w="(\d+)"', grid.group(0)))
                    if not ncols:
                        continue
                    pcts = profile_for(header_signature(tbl), ncols)
                    assert sum(pcts) == 100, (pcts, sum(pcts))
                    cols = widths_from(pcts, A4_PORTRAIT_USABLE)

                    new_grid = "<w:tblGrid>" + "".join(
                        f'<w:gridCol w:w="{c}" />' for c in cols) + "</w:tblGrid>"
                    new_tbl = tbl.replace(grid.group(0), new_grid)

                    # Table width must match the grid, or Word re-derives its
                    # own layout and the grid is ignored.
                    new_tbl = re.sub(
                        r'<w:tblW[^/]*/>',
                        f'<w:tblW w:type="dxa" w:w="{sum(cols)}" />',
                        new_tbl, count=1)

                    # Every cell's own width has to agree with its column, per
                    # the dual-width rule -- grid alone is advisory.
                    def cell_widths(row_xml: str) -> str:
                        i = [0]

                        def repl(cm: re.Match) -> str:
                            w = cols[min(i[0], len(cols) - 1)]
                            i[0] += 1
                            return re.sub(r'<w:tcW[^/]*/>',
                                          f'<w:tcW w:type="dxa" w:w="{w}" />',
                                          cm.group(0), count=1)

                        return re.sub(r"<w:tc>.*?</w:tc>", repl, row_xml,
                                      flags=re.S)

                    new_tbl = re.sub(r"<w:tr[ >].*?</w:tr>",
                                     lambda rm: cell_widths(rm.group(0)),
                                     new_tbl, flags=re.S)

                    out.append(xml[pos:m.start()])
                    out.append(new_tbl)
                    pos = m.end()
                    changed += 1
                out.append(xml[pos:])
                data = "".join(out).encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, path)
    return changed, seen


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        p = Path(arg)
        ch, sn = fix(p)
        print(f"{p.name}: re-laid out {ch} of {sn} tables")
