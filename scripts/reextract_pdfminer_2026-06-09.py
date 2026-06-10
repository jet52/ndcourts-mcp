"""Re-extract OCR-flagged modern (1997+, source=ND) opinions from their court
PDFs with pdfminer, replacing the OCR-corrupted body (the `■`/`„` artifacts came
from an OCR pass; fresh pdfminer extraction is clean). Preserves the frontmatter
+ '# Title/court/cites/Decided' header prefix; swaps the body from the body anchor
('Filed ... by Clerk' / 'IN THE SUPREME COURT' / 'IN THE COURT OF APPEALS') onward.
Validates artifacts==0 and a contiguous [¶1..N] sequence (or no markers for short
orders). Dry-run default; --apply writes markdown/<year>/<cite>.md + text_content
(logged). Reads the ACCEPT_PM list from triage/pdf-reextract-scope.tsv.
"""
import sqlite3, re, sys, argparse
from pathlib import Path
from pdfminer.high_level import extract_text
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import get_connection, DEFAULT_DB_PATH, log_change, log_provenance
from ndcourts_mcp.ingest_nwcite import _split_frontmatter

ART=set("¡¿■£„")
ANCHOR=re.compile(r"(?m)^(Filed .*by Clerk of Supreme Court|IN THE SUPREME COURT|IN THE COURT OF APPEALS)")
MARK=re.compile(r"\[\s*¶\s*(\d+)\s*\]")
REFS=Path.home()/"refs"/"nd"/"opin"
BATCH="reextract-pdfminer-2026-06-09"

def reconstruct(cur_text, pdf):
    body=extract_text(pdf)
    mp=ANCHOR.search(cur_text); mb=ANCHOR.search(body)
    if not mp or not mb: return None,"no-anchor"
    new=cur_text[:mp.start()].rstrip()+"\n\n"+body[mb.start():].strip()+"\n"
    if any(c in new for c in ART): return None,"artifacts-remain"
    nums=[int(m.group(1)) for m in MARK.finditer(new)]
    if nums and nums!=list(range(1,max(nums)+1)): return None,"seq-gap"
    return new,"ok"

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--apply",action="store_true")
    ap.add_argument("--limit",type=int,default=None); a=ap.parse_args()
    conn=get_connection(DEFAULT_DB_PATH)
    rows=[l.rstrip("\n").split("\t") for l in open("triage/pdf-reextract-scope.tsv")][1:]
    accept=[r for r in rows if r[6]=="ACCEPT_PM"]
    wl={r[0]:r for r in [l.rstrip("\n").split("\t") for l in open("triage/ocr-pdf-reextract-worklist.tsv")][1:]}
    ok=skip=0
    for r in accept[:a.limit]:
        oid=r[0]; pdf=wl[oid][5]; cite=r[7]
        cur=conn.execute("SELECT text_content,source_path FROM opinions WHERE id=?",(oid,)).fetchone()
        new,why=reconstruct(cur["text_content"],pdf)
        if new is None: skip+=1; print(f"SKIP {oid} {cite}: {why}"); continue
        ok+=1
        if a.apply:
            log_change(conn,BATCH,int(oid),"text_content","OCR-corrupted body (■/„ artifacts)",
                       f"pdfminer re-extract from {pdf}",authority="court PDF re-extraction (pdfminer)")
            conn.execute("UPDATE opinions SET text_content=? WHERE id=?",(new,oid))
            yr=cite.split()[0]; fn=cite.replace(" ","")
            mdp=REFS/"markdown"/yr/f"{fn}.md"
            if mdp.parent.exists(): mdp.write_text(new,encoding="utf-8")
    if a.apply:
        log_provenance(conn,operation="reextract_pdfminer",command="python scripts/reextract_pdfminer_2026-06-09.py --apply",
                       source_paths="~/refs/nd/opin/pdfs",rows_affected=ok,notes=f"batch {BATCH}; {ok} re-extracted")
        conn.commit()
    print(f"\n{'APPLIED' if a.apply else 'DRY RUN'}: reextracted={ok} skipped={skip} of {len(accept[:a.limit])} ACCEPT_PM")

if __name__=="__main__": main()
