"""Create + populate the print_anomalies registry, and apply two corrections
that fell out of building it.

print_anomalies: every verified instance where the COURT'S authoritative
print contains an apparent typo. Policy: text_content stays verbatim to the
print; the citation graph resolves to the INTENDED case (override applied on
every cited_by rebuild — cite_extract.apply_print_anomaly_overrides); each
row carries a follow-up note because West sometimes publishes corrections /
the court submits corrected pages — our slip-PDF-derived text could postdate
or miss an approved correction. We don't assume that; we flag it.

Corrections in this batch:
  * 15948 (2012 ND 217): RESTORE "599 N.W.3d 323" — the print genuinely
    reads N.W.3d (4x glyph render, agent-verified vs p.10); the earlier
    parallel-pair-textfixes change to N.W.2d violated the verbatim policy.
  * 12605 case_name "Wodrich v. Bauske" -> "Paulson v. Bauske" — the caption
    is "Rebecca J. PAULSON, n/k/a Rebecca J. Wodrich v. Raymond J. BAUSKE";
    courts cite it as Paulson (e.g. 12875 ¶6); the n/k/a surname had been
    used as the case name.
"""
import sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "print-anomalies-registry-2026-06-10"
REFS = Path.home() / "refs/nd/opin"
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")

FOLLOWUP = ("Check West advance sheets / N.W.2d bound volume and any court-submitted "
            "corrected page: if West prints the corrected cite, the court may have "
            "approved a correction our slip-PDF text misses.")

# (citing_oid, kind, printed_text, printed_cite_for_graph, intended_text,
#  intended_oid, location, basis, verified)
IN_CORPUS = [
    (16446, "citation", "Jaste v. Gailfus, 2004 ND 87, ¶ 18", "2004 ND 87", "2004 ND 94, ¶ 18", 14008,
     "¶? (detect_overruled build)", "case name + ¶18 pincite exceed 2004 ND 87's ¶10 max; Jaste is 2004 ND 94", "print crop 2026-05-24/06-09"),
    (14127, "citation", "674 N.W.2d 402 (Muhammed)", "674 N.W.2d 402", "675 N.W.2d 402", 13968,
     "", "Muhammed v. Welch parallel is 675 N.W.2d 402", "print verified (citeflip batch 2026-06-09)"),
    (16894, "citation", "716 N.W.2d 535 (Pace)", "716 N.W.2d 535", "713 N.W.2d 535", 14507,
     "", "State v. Pace parallel is 713 N.W.2d 535", "print verified (citeflip batch 2026-06-09)"),
    (16184, "citation", "Disciplinary Board v. Hoffman, 2013 ND 137, 835 N.W.2d 836", "835 N.W.2d 836",
     "834 N.W.2d 636", 16090, "¶9", "Hoffman's parallel is 834 N.W.2d 636", "print crops 33/34, 2026-06-09"),
    (16917, "citation", "Johnson v. Hovland, 2011 ND 64, ¶¶ 11-12, 795 N.W.2d 194", "795 N.W.2d 194",
     "795 N.W.2d 294", 15588, "¶15", "CL filed Hovland at NW2d/795/294", "print crop 69, 2026-06-09"),
    (14777, "citation", "2006 ND 6, ¶ 25, 604 N.W.2d 445", "2006 ND 6", "2000 ND 6", 13067,
     "¶13", "State v. Dvorak is 2000 ND 6, 604 N.W.2d 445; printed year impossible for that volume", "print crop idx 250, 2026-06-10"),
    (13063, "citation", "Henry, 1999 ND 141, ¶ 22, 581 N.W.2d", "1999 ND 141", "1998 ND 141", 12721,
     "¶9", "Henry v. Henry is 1998 ND 141, 581 N.W.2d 921", "personal spot-check crop 72, 2026-06-10"),
    (15011, "citation", "Rist v. North Dakota Dep't of Transp., 2003 ND 133, ¶ 15, 665 N.W.2d 45", "2003 ND 133",
     "2003 ND 113", 13830, "¶34 region", "Rist is 2003 ND 113, 665 N.W.2d 45", "print crop /tmp/p15011, 2026-06-10"),
    (15834, "citation", "Clark, 1998 ND 155, ¶ 28, 583 N.W.2d 377", "1998 ND 155", "1998 ND 153", 12736,
     "¶46 region", "Ohio Cas. v. Clark is 1998 ND 153, 583 N.W.2d 377", "print crop /tmp/p15834, 2026-06-10"),
    (12875, "citation", "Paulson, 1998 ND 7, ¶¶ 5, 13, 574 N.W.2d 801", "1998 ND 7", "1998 ND 17", 12605,
     "¶11", "Paulson v. Bauske is 1998 ND 17, 574 N.W.2d 801", "print crop pass3 idx 0, 2026-06-10"),
    (12920, "citation", "Dakutak, 1997 ND 76, ¶ 6, 652 N.W.2d 750", "652 N.W.2d 750", "562 N.W.2d 750", 12425,
     "¶10", "Dakutak v. Dakutak is 562 N.W.2d 750; 652 volume impossible for 1997", "print crop pass3 idx 1, 2026-06-10"),
    (13927, "citation", "Henderson v. Dir., N.D. Dep't of Transp., ... N.W.2d 617", "640 N.W.2d 617",
     "640 N.W.2d 714", 13543, "¶14", "Henderson 2002 ND 44 parallel is 640 N.W.2d 714", "print crop pass3 idx 6, 2026-06-10"),
    (14719, "citation", "Stout v. Stout, 1997 ND 61, 506 N.W.2d 903", "506 N.W.2d 903", "560 N.W.2d 903", 12399,
     "¶5", "Stout is 560 N.W.2d 903; 506 volume is 1993-era", "print crop pass3 idx 10, 2026-06-10"),
    (15087, "citation", "718 N.W.2d 01 (Aakre)", "718 N.W.2d 01", "718 N.W.2d 1", 14555,
     "¶1", "Disciplinary Board v. Aakre, 2006 ND 146, 718 N.W.2d 1", "print crop pass3 idx 11, 2026-06-10"),
    (15308, "citation", "Rockwell, 1999 ND 125, ¶ 18, 579 N.W.2d 406", "579 N.W.2d 406", "597 N.W.2d 406", 12926,
     "¶31", "City of Fargo v. Rockwell is 597 N.W.2d 406", "print crop pass3 idx 12, 2026-06-10"),
    (15869, "citation", "State v. Jones, 2011 ND 234, ¶ 8, 812 N.W.2d 484", "812 N.W.2d 484", "817 N.W.2d 313", 15852,
     "¶8", "Jones's parallel is 817 N.W.2d 313; print miscites vol+page", "print crop /tmp/jones_hit0, 2026-06-10"),
    (16413, "citation", "Lyon, 2000 ND 12, ¶ 12, 604 N.W.2d 543", "604 N.W.2d 543", "604 N.W.2d 453", 13068,
     "¶25", "Lyon v. Ford is 604 N.W.2d 453", "print crop pass3 idx 17, 2026-06-10"),
    (16533, "citation", "Howe, 2014 ND 17, 842 N.W.2d 64", "842 N.W.2d 64", "842 N.W.2d 646", 16203,
     "¶5", "Disciplinary Board v. Howe is 842 N.W.2d 646; page truncated in print", "print crop pass3 idx 18, 2026-06-10"),
    (13031, "citation", "Lee, 1999 ND 218, ¶ 11, 587 N.W.2d 423", "1999 ND 218", "1998 ND 218", 12797,
     "¶11", "Lee v. Workers Comp. Bureau is 1998 ND 218, 587 N.W.2d 423", "re-rendered print, agent slice 02, 2026-06-10"),
    (13124, "citation", "Ebach, 1999 ND 5, ¶ 15, 689 N.W.2d 566", "689 N.W.2d 566", "589 N.W.2d 566", 12814,
     "¶11", "State v. Ebach is 589 N.W.2d 566; 689 volume impossible for 1999", "zoomed print, agent slice 03, 2026-06-10"),
    (16816, "citation", "Datz v. Dosch, 2014 ND 102, ¶ 13, 346 N.W.2d 724", "346 N.W.2d 724", "846 N.W.2d 724", 16273,
     "¶13", "Datz is 846 N.W.2d 724; 346 volume is 1984-era", "print crop /tmp/b16816, 2026-06-10"),
    (14391, "citation", "State v. Harmon, 1997 ND 223, 575 N.W.2d 635", "1997 ND 223", "1997 ND 233", 12636,
     "¶3", "Harmon is 1997 ND 233, 575 N.W.2d 635", "print crop /tmp/b14391, 2026-06-10"),
    (13208, "citation", "Gibson v. State, 1998 ND 89, ¶ 5, 578 N.W.2d 129", "578 N.W.2d 129", "578 N.W.2d 128", 12664,
     "¶? (Compare cite)", "Gibson's parallel is 578 N.W.2d 128; printed page 129 belongs to Moch", "print crop /tmp/b13208, 2026-06-10"),
    (15948, "citation", "Svedberg, 1999 ND 181, ¶ 15, 599 N.W.3d 323", "599 N.W.3d 323", "599 N.W.2d 323", 12976,
     "¶20", "N.W.3d did not exist in 2012; Svedberg is 599 N.W.2d 323; print glyph verified 4x", "agent glyph render p.10, 2026-06-10"),
    (16507, "citation", "Smestad v. Harris, 2001 ND 91, ¶ 15, 796 N.W.2d 662", "2001 ND 91", "2011 ND 91", 15619,
     "¶20", "Smestad is 2011 ND 91, 796 N.W.2d 662", "print crop slice 16 idx 505, 2026-06-10"),
]
OUT_OF_CORPUS = [
    (13417, "citation", "United States v. Ward, 488 U.S. 242, 248 (1980)", None, "448 U.S. 242", None,
     "¶17", "Ward is 448 U.S. 242 (1980)", "print crop idx 110, 2026-06-10"),
    (14087, "date", "Carroll v. United States, 267 U.S. 132 ... (1923)", None, "(1925)", None,
     "¶10", "Carroll was decided 1925", "print crop idx 178, 2026-06-10"),
    (17066, "citation", "Miller v. Alabama, 597 U.S. 460, 132 S.Ct. ... (2012)", None, "567 U.S. 460", None,
     "¶9", "Miller is 567 U.S. 460", "print crop idx 604, 2026-06-10"),
    (14611, "date", "Hofsommer, 488 N.W.2d 380, 383 (N.D. 1982)", None, "(N.D. 1992)", None,
     "¶10", "488 N.W.2d is a 1992 volume", "zoomed print, agent slice 07, 2026-06-10"),
    (15888, "date", "McCarthy, 394 U.S. 459 ... (1968)", None, "(1969)", None,
     "¶10", "McCarthy was decided 1969", "print crop idx 395, 2026-06-10"),
    (16972, "date", "Burlington Res. Oil & Gas v. Lang & Sons, 259 P.3d 766 (2001)", None, "(2011)", None,
     "¶?", "259 P.3d is a 2011 volume (moderate confidence on date)", "print crop idx 586, 2026-06-10"),
    (13089, "date", "Hagert, 350 N.W.2d 591, 595 (N.D. 1994)", None, "(N.D. 1984)", None,
     "¶7", "350 N.W.2d is a 1984 volume", "zoomed print, agent slice 02, 2026-06-10"),
    (15283, "date", "526 N.W.2d 487, 490 (N.D. 1985)", None, "(N.D. 1995)", None,
     "¶16", "526 N.W.2d is a 1995 volume", "print crop idx 299, 2026-06-10"),
    (15939, "date", "531 N.W.2d 289, 300-01 (N.D. 1985)", None, "(N.D. 1995)", None,
     "¶16", "531 N.W.2d is a 1995 volume", "3x print crop idx 401, 2026-06-10"),
    (18238, "date", "174 N.W.2d 717 (N.D. 1969)", None, "(N.D. 1970)", None,
     "¶31", "174 N.W.2d 717 (State v. Hapip) is 1970 (moderate confidence)", "print crop pass3 idx 21, 2026-06-10"),
]

print(f"{len(IN_CORPUS)} in-corpus + {len(OUT_OF_CORPUS)} out-of-corpus anomalies")
if not apply:
    print("DRY RUN"); sys.exit(0)

conn.execute("""CREATE TABLE IF NOT EXISTS print_anomalies (
    id INTEGER PRIMARY KEY,
    opinion_id INTEGER NOT NULL REFERENCES opinions(id),  -- opinion whose print carries the anomaly
    kind TEXT NOT NULL,            -- 'citation' | 'date' | 'other'
    printed_text TEXT NOT NULL,    -- the anomalous passage as the court printed it (preserved verbatim in text_content)
    printed_cite TEXT,             -- normalized cite string for the graph override (NULL when no edge impact)
    intended_text TEXT,            -- the apparent intended reading
    intended_opinion_id INTEGER REFERENCES opinions(id),  -- in-corpus resolution target
    location TEXT,
    basis TEXT NOT NULL,           -- evidence for the intended reading
    verified TEXT NOT NULL,        -- how the printed reading was verified
    followup TEXT,                 -- e.g. West advance-sheet / corrected-page check
    batch TEXT NOT NULL,
    UNIQUE(opinion_id, printed_text)
)""")
for row in IN_CORPUS + OUT_OF_CORPUS:
    oid, kind, ptext, pcite, itext, ioid, loc, basis, ver = row
    conn.execute("""INSERT OR REPLACE INTO print_anomalies
        (opinion_id, kind, printed_text, printed_cite, intended_text, intended_opinion_id,
         location, basis, verified, followup, batch)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (oid, kind, ptext, pcite, itext, ioid, loc, basis, ver, FOLLOWUP, BATCH))
    log_change(conn, BATCH, oid, "print_anomaly.registered", "", ptext,
               authority=f"intended: {itext}; {basis}")

# correction 1: restore the verbatim N.W.3d in 15948
text, sp = conn.execute("SELECT text_content, source_path FROM opinions WHERE id=15948").fetchone()
if text.count("599 N.W.2d 323") == 1 and "N.W.3d 323" not in text:
    conn.execute("UPDATE opinions SET text_content=? WHERE id=15948",
                 (text.replace("599 N.W.2d 323", "599 N.W.3d 323"),))
    log_change(conn, BATCH, 15948, "text_content.cite_token", "599 N.W.2d 323", "599 N.W.3d 323",
               authority="REVERT of parallel-pair-textfixes-2026-06-10: the print genuinely reads "
                         "N.W.3d (4x glyph render verified); verbatim policy governs; graph override "
                         "resolves it to Svedberg via print_anomalies")
    p = REFS / sp
    if p.exists():
        md = p.read_text()
        if md.count("599 N.W.2d 323") == 1:
            p.write_text(md.replace("599 N.W.2d 323", "599 N.W.3d 323"))
    print("15948 restored to print (N.W.3d)")

# correction 2: 12605 case_name
old = conn.execute("SELECT case_name FROM opinions WHERE id=12605").fetchone()[0]
if old != "Paulson v. Bauske":
    conn.execute("UPDATE opinions SET case_name='Paulson v. Bauske' WHERE id=12605")
    log_change(conn, BATCH, 12605, "case_name", old, "Paulson v. Bauske",
               authority="caption: 'Rebecca J. PAULSON, n/k/a Rebecca J. Wodrich v. Raymond J. BAUSKE'; "
                         "cited by the court as Paulson v. Bauske (e.g. 12875 ¶6)")
    print(f"12605 case_name {old!r} -> 'Paulson v. Bauske'")

log_provenance(conn, "print-anomalies-registry",
               command="triage/build_print_anomalies_2026-06-10.py --apply",
               rows_affected=len(IN_CORPUS) + len(OUT_OF_CORPUS),
               notes=f"batch {BATCH}; registry created; graph overrides wired into cite_extract")
conn.commit()
print("APPLIED")
