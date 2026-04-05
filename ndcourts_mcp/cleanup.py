"""Apply and manage data corrections with full audit trail.

All corrections go through the changelog table, making them revertible.

Usage:
    python -m ndcourts_mcp.cleanup apply [--dry-run]    Apply all pending corrections
    python -m ndcourts_mcp.cleanup revert <batch>        Revert a batch of corrections
    python -m ndcourts_mcp.cleanup log                   Show changelog summary
"""

import argparse
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection


def _apply_author_map(
    conn, batch: str, mapping: dict[str, str], dry_run: bool = False
) -> int:
    """Apply a set of author name corrections.

    mapping: {old_name: new_name}
    Returns count of rows updated.
    """
    total = 0
    for old, new in mapping.items():
        rows = conn.execute(
            "SELECT id, author FROM opinions WHERE author = ?", (old,)
        ).fetchall()
        for row in rows:
            if not dry_run:
                conn.execute(
                    "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                    "VALUES (?, ?, 'author', ?, ?)",
                    (batch, row["id"], old, new),
                )
                conn.execute(
                    "UPDATE opinions SET author = ? WHERE id = ?", (new, row["id"])
                )
            total += 1
    return total


def _apply_per_curiam(
    conn, batch: str, names: list[str], dry_run: bool = False
) -> int:
    """Set author→NULL and per_curiam→1 for mangled 'Per Curiam' labels."""
    total = 0
    for name in names:
        rows = conn.execute(
            "SELECT id, author, per_curiam FROM opinions WHERE author = ?", (name,)
        ).fetchall()
        for row in rows:
            if not dry_run:
                conn.execute(
                    "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                    "VALUES (?, ?, 'author', ?, NULL)",
                    (batch, row["id"], name),
                )
                conn.execute(
                    "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                    "VALUES (?, ?, 'per_curiam', ?, '1')",
                    (batch, row["id"], str(row["per_curiam"])),
                )
                conn.execute(
                    "UPDATE opinions SET author = NULL, per_curiam = 1 WHERE id = ?",
                    (row["id"],),
                )
            total += 1
    return total


# ── Correction batches ──────────────────────────────────────────────────

BATCH_01_CASE_NORMALIZATION = {
    # VandeWalle consolidation
    "WALLE": "VandeWalle",
    "VANDEWALLE": "VandeWalle",
    "VandeWALLE": "VandeWalle",
    "Vandewalle": "VandeWalle",
    "Vande Walle": "VandeWalle",
    "Vande Walle Cmef": "VandeWalle",
    "Vande Vande Walle": "VandeWalle",
    "De Walle": "VandeWalle",
    "YANDEWALLE": "VandeWalle",
    "Walle": "VandeWalle",
    "WÁLLE": "VandeWalle",
    # Erickstad
    "ERICKSTAD": "Erickstad",
    "ER1CKSTAD": "Erickstad",
    "EKICKSTAD": "Erickstad",
    # Simple case normalization
    "MESCHKE": "Meschke",
    "LEVINE": "Levine",
    "LEYINE": "Levine",
    "GIERKE": "Gierke",
    "PEDERSON": "Pederson",
    "PEDERuON": "Pederson",
    "SAND": "Sand",
    "PAULSON": "Paulson",
    "SANDSTROM": "Sandstrom",
    "NEUMANN": "Neumann",
    "BURKE": "Burke",
    "MARING": "Maring",
    "TEIGEN": "Teigen",
    "TKIGEN": "Teigen",
    "TLIGEN": "Teigen",
    "VOGEL": "Vogel",
    "STRUTZ": "Strutz",
    "JOHNSON": "Johnson",
    "MORRIS": "Morris",
    "CHRISTIANSON": "Christianson",
    "NUESSLE": "Nuessle",
    "KAPSNER": "Kapsner",
    "BURR": "Burr",
    "BuRR": "Burr",
    "BIRDZELL": "Birdzell",
    "BiRdzell": "Birdzell",
    "BiRDZELL": "Birdzell",
    "BlRDZELL": "Birdzell",
    "GRIMSON": "Grimson",
    "SATHRE": "Sathre",
    "SATURE": "Sathre",
    "CROTHERS": "Crothers",
    "BRUCE": "Bruce",
    "BUTTZ": "Buttz",
    "COLE": "Cole",
    "COOLEY": "Cooley",
    "SWENSON": "Swenson",
    "WOLFE": "Wolfe",
    "KNEESHAW": "Kneeshaw",
    "KONENKAMP": "Konenkamp",
    "McKENNA": "McKenna",
    "MOELLRING": "Moellring",
    "JANSONIUS": "Jansonius",
    "GEN": "Gen",
    "PUGH": "Pugh",
    "KNUDSON": "Knudson",
    # OCR misreads with correct era
    "CRIMSON": "Grimson",
    "MAKING": "Maring",
}

BATCH_02_BIRDZELL_OCR = {
    # All within Birdzell's 1918–1933 tenure
    # 70+ count
    "Biedzell": "Birdzell",
    "Bikdzell": "Birdzell",
    # 20-69
    "Bibdzell": "Birdzell",
    "Birdzbll": "Birdzell",
    "Birdzele": "Birdzell",
    # 10-19
    "Birdzeel": "Birdzell",
    "Birdzeix": "Birdzell",
    "Biruzell": "Birdzell",
    "Birbzell": "Birdzell",
    # 5-9
    "Birdzelu": "Birdzell",
    "Birdzull": "Birdzell",
    "Birdzehl": "Birdzell",
    # 3-4
    "Birdzelx": "Birdzell",
    "Birdzexl": "Birdzell",
    "Birdzsll": "Birdzell",
    "Birhzell": "Birdzell",
    "Biedzbll": "Birdzell",
    "Biedzeli": "Birdzell",
    "Biedzelx": "Birdzell",
    "Birdzelb": "Birdzell",
    "Birdzelh": "Birdzell",
    "Birdzeul": "Birdzell",
    "Bibbzell": "Birdzell",
    "Bibdzbll": "Birdzell",
    # 2
    "Bisdzell": "Birdzell",
    "Birdzrll": "Birdzell",
    "Birdzüll": "Birdzell",
    "Birdeell": "Birdzell",
    "Biudzell": "Birdzell",
    "Berdzell": "Birdzell",
    "Birezell": "Birdzell",
    "Biedzeul": "Birdzell",
    "Biedzele": "Birdzell",
    "Birdzexx": "Birdzell",
    "Birdzerl": "Birdzell",
    "Birdzelr": "Birdzell",
    "Birdzeli": "Birdzell",
    "Birdzei": "Birdzell",
    "Birdzebl": "Birdzell",
    "Bikdzeix": "Birdzell",
    "B'irdzell": "Birdzell",
    # 1 — clear Birdzell OCR
    "Birdzcell": "Birdzell",
    "Birdzelt": "Birdzell",
    "Birnzell": "Birdzell",
    "Bjbdzell": "Birdzell",
    "Bierdzell": "Birdzell",  # extra 'e'
    "Bjbdzell": "Birdzell",
    "Birdzeln": "Birdzell",
    "Birdzetil": "Birdzell",
    "Birdzxix": "Birdzell",
    "Birdztsll": "Birdzell",
    "Birdzkll": "Birdzell",
    "Birdzjell": "Birdzell",
    "Birdzjeil": "Birdzell",
    "Birdzhehl": "Birdzell",
    "Birdzri": "Birdzell",
    "Birdzerr": "Birdzell",
    "Birdzeud": "Birdzell",
    "Birdzüíll": "Birdzell",
    "Birdxell": "Birdzell",
    "Birdhell": "Birdzell",
    "BiRdkell": "Birdzell",
    "BiRDzbll": "Birdzell",
    "Birdzblu": "Birdzell",
    "Birdzebe": "Birdzell",
    "Birdzeill": "Birdzell",
    "BiRDZEim": "Birdzell",
    "BiRDzeix": "Birdzell",
    "Birdzekt": "Birdzell",
    "Birdzela": "Birdzell",
    "BiRDZELi": "Birdzell",
    "Bibcdzell": "Birdzell",
    "Bibdzebl": "Birdzell",
    "Bibdzejll": "Birdzell",
    "Bibdzekl": "Birdzell",
    "Bibdzeli": "Birdzell",
    "Bibdzkll": "Birdzell",
    "Bibuzell": "Birdzell",
    "Biebzbll": "Birdzell",
    "Biebzell": "Birdzell",
    "Biedzbbb": "Birdzell",
    "Biedzbuu": "Birdzell",
    "Biedzeel": "Birdzell",
    "Biedzehl": "Birdzell",
    "Biedzei": "Birdzell",
    "Biedzelx": "Birdzell",
    "Biedzelu": "Birdzell",
    "Biedzkll": "Birdzell",
    "Biedzet": "Birdzell",
    "Biejozell": "Birdzell",
    "Bielzell": "Birdzell",
    "Bieuzell": "Birdzell",
    "Bieuzeul": "Birdzell",
    "Biisdzell": "Birdzell",
    "Biiídzell": "Birdzell",
    "Bikdzeel": "Birdzell",
    "Bikdzei": "Birdzell",
    "Bikdzeli": "Birdzell",
    "Bikdzelu": "Birdzell",
    "Bikdzelx": "Birdzell",
    "Bikdzkll": "Birdzell",
    "Birbzebl": "Birdzell",
    "Birbzelb": "Birdzell",
    "Birbzele": "Birdzell",
    "Birbzeul": "Birdzell",
    "Biruzeel": "Birdzell",
    "Biruzeim": "Birdzell",
    "Biruzekl": "Birdzell",
    "Biruzelu": "Birdzell",
    "Biruztslx": "Birdzell",
    "Biudzelu": "Birdzell",
    "BiudzRi": "Birdzell",
    "Bjbdzell": "Birdzell",
    "Bjerdzell": "Birdzell",
    "Bjudzell": "Birdzell",
    "Blrdzbll": "Birdzell",
    "Bianzell": "Birdzell",
    "Birezeel": "Birdzell",
    "Birhzeel": "Birdzell",
    "Birixzell": "Birdzell",
    "Birjdzell": "Birdzell",
    "Birlkzell": "Birdzell",
    "Birnzeim": "Birdzell",
    "Birukeel": "Birdzell",
    "BtRpzeul": "Birdzell",
    "Bhudzeli": "Birdzell",
    "Bhídzeul": "Birdzell",
    # Bhucb omitted — 1914, likely Bruce not Birdzell
    "Bekdzell": "Birdzell",
    "Bnmzeix": "Birdzell",
    # Bmuzei omitted — 1917, judges field shows separate from Birdzell
    "Breuzicim": "Birdzell",
    "Bxbdzell": "Birdzell",
    "Obirdzell": "Birdzell",
}

BATCH_06_MISC_JUSTICE_OCR = {
    # Christianson variants
    "Cheistianson": "Christianson",
    "Ci-Iristianson": "Christianson",
    "Christian": "Christianson",
    "Cheistxanson": "Christianson",
    "Chkistianson": "Christianson",
    "Chuistianson": "Christianson",
    "Chetstianson": "Christianson",
    "Chexstianson": "Christianson",
    "Chbistianson": "Christianson",
    "C'Heistianson": "Christianson",
    "Christxanson": "Christianson",
    "Cribisauanson": "Christianson",
    "Cumstianson": "Christianson",
    "Ohbistianson": "Christianson",
    "Oheistianson": "Christianson",
    "Ohkistianson": "Christianson",
    "Ohmstianson": "Christianson",
    "Ohristianson": "Christianson",
    "Ohuistianson": "Christianson",
    "Ouristianson": "Christianson",
    "Ciibistianson": "Christianson",
    "Ciibtstianson": "Christianson",
    "Ciieistianson": "Christianson",
    "Ciiristianson": "Christianson",
    "Ciiristxanson": "Christianson",
    "Ciritistianson": "Christianson",
    "Citristianson": "Christianson",
    "Cjuk'Istianson": "Christianson",
    # Fisk variants
    "Eisk": "Fisk",
    "Fisic": "Fisk",
    "Bisk": "Fisk",
    "Pisk": "Fisk",
    "Pise": "Fisk",
    "Rise": "Fisk",
    "Risk": "Fisk",
    "Fise": "Fisk",
    "Eisic": "Fisk",
    # Robinson variants
    "Bobinson": "Robinson",
    "Eobinson": "Robinson",
    # Birdzell truncation
    "Bird": "Birdzell",
    # Johnson variants
    "Joiinson": "Johnson",
    "Joi-Inson": "Johnson",
    "Jonnson": "Johnson",
    "Jonxson": "Johnson",
    "Jorinson": "Johnson",
    "Johrson": "Johnson",
    # Grimson variants
    "Crimson": "Grimson",
    "Geimson": "Grimson",
    "G-Rimson": "Grimson",
    "Gbimson": "Grimson",
    "Gbtmson": "Grimson",
    "Griimson": "Grimson",
    "Grims-On": "Grimson",
    "Grimsón": "Grimson",
    # Erickstad variants
    "Erick": "Erickstad",
    "Erick-Stad": "Erickstad",
    "Ralph J. Erickstad": "Erickstad",
    "Ericicstad": "Erickstad",
    "Ericksted": "Erickstad",
    "Ericstad": "Erickstad",
    "Ertckstad": "Erickstad",
    # Nuessle variants
    "Ntjessle": "Nuessle",
    "Nubssle": "Nuessle",
    "Nuessee": "Nuessle",
    "Nubsslt": "Nuessle",
    "Nubsstje": "Nuessle",
    "Nuessi": "Nuessle",
    "Nuessijs": "Nuessle",
    "Nuesslb": "Nuessle",
    "Nuesstje": "Nuessle",
    "Nuesstjs": "Nuessle",
    "Nuessub": "Nuessle",
    "Nuessue": "Nuessle",
    "Nuessxjs": "Nuessle",
    "Nuessxu": "Nuessle",
    "Nunssnn": "Nuessle",
    "Nxjessle": "Nuessle",
    "Ncjessle": "Nuessle",
    "Neussle": "Nuessle",
    "Ntjessi": "Nuessle",
    "Nttessle": "Nuessle",
    # Sathre variants
    "Sature": "Sathre",
    "Satiire": "Sathre",
    "Satpire": "Sathre",
    "Sathke": "Sathre",
    # Burke stragglers
    "Bubkb": "Burke",
    # Teigen
    "Teígen": "Teigen",
    # Wallin
    "Walltn": "Wallin",
    "Wali": "Wallin",
    # Spalding
    "Spalning": "Spalding",
    "Spauding": "Spalding",
    "Spálding": "Spalding",
    # Ellsworth
    "Ellsworti": "Ellsworth",
    # Morris
    "Moréis": "Morris",
    "Mórris": "Morris",
    "Mortus": "Morris",
    "Morjris": "Morris",
    "Mobbis": "Morris",
    "M'Orris": "Morris",
    "Norris": "Morris",
    # Full name → last name
    "Adam Gefreh": "Gefreh",
    "Beryl J. Levine": "Levine",
    "Clifford Jansonius": "Jansonius",
    "Clifford Schneller": "Schneller",
    "Eugene A. Burdick": "Burdick",
    "Hamilton E. Englert": "Englert",
    "Harry E. Rittgers": "Rittgers",
    "James H. O'Keefe": "O'Keefe",
    "Ralph B. Maxwell": "Maxwell",
    "William F. Hodny": "Hodny",
    "Douglas B. Heen": "Heen",
    "A. C. Bakken": "Bakken",
}

BATCH_06B_PER_CURIAM = [
    # OCR mangled "Per Curiam" — set author→NULL, per_curiam→1
    "Cueiam",
    "Oueiam",
    "Pee",
    "Cubiam",
    "Cuetam",
    "Cuexam",
    "Cukiam",
    "Curium",
    "Curriam",
    "Curtam",
    "Oubiam",
    "Ourtam",
    "Ourxam",
    "Per Curiam",
]

BATCH_05_BURKE_OCR = {
    # Three Burkes: Edward T. (1911–1916), John (1919–1937), Thomas J. (1951–1966)
    "Bure": "Burke",
    "Burice": "Burke",
    "Bueke": "Burke",
    "Bubke": "Burke",
    "Buekb": "Burke",
    "Bueice": "Burke",
    "Burk": "Burke",
    "Bukke": "Burke",
    "Bukr": "Burke",
    "Buer": "Burke",
    "Buee": "Burke",
    "Burnt": "Burke",
    "Bubee": "Burke",
    "Bueeb": "Burke",
    "Bubb": "Burke",
    "Bur": "Burke",
    "Bube": "Burke",
    "Buree": "Burke",
    "Bue": "Burke",
    "Bueee": "Burke",
    "Bujrr": "Burke",
    "Bubr": "Burke",
    "Bunn": "Burke",
    "Bürke": "Burke",
    "Burkb": "Burke",
    "Borke": "Burke",
    "Bcrke": "Burke",
    "Purke": "Burke",
    "Bürkb": "Burke",
    "Buricb": "Burke",
    "Burick": "Burke",
    "Buriíe": "Burke",
    "Bueiíe": "Burke",
    "Burjie": "Burke",
    "Burjke": "Burke",
    "Buke": "Burke",
    "Bukee": "Burke",
    "Bukice": "Burke",
    "Bujrice": "Burke",
    "Buetce": "Burke",
    "Buek": "Burke",
    "Bueb": "Burke",
    "Bup": "Burke",
    "Eurke": "Burke",
}

BATCH_05B_CONTEXT_FIXES = {
    # Identified by checking judges field context
    "Nubs": "Nuessle",      # 1924, judges missing Nuessle
    "Nubsslb": "Nuessle",   # 1947, judges missing Nuessle
    "Bums": "Burr",          # 1929, judges missing Burr
}

BATCH_04_BRUCE_OCR = {
    # All within Andrew A. Bruce's 1912–1918 tenure
    "Bbuce": "Bruce",
    "Beuce": "Bruce",
    "Beucb": "Bruce",
    "Beuoe": "Bruce",
    "Bhucb": "Bruce",
    "Bruoe": "Bruce",
    "Bsuce": "Bruce",
    "Beugb": "Bruce",
    "Brtjoe": "Bruce",
}

BATCH_03_BRONSON_OCR = {
    # All within Harrison A. Bronson's 1918–1924 tenure
    "Beonson": "Bronson",
    "Bbonson": "Bronson",
    "Beokson": "Bronson",
    "BeoNSON": "Bronson",
    "Beohson": "Bronson",
    "Beoiyson": "Bronson",
    "BeoNsoN": "Bronson",
    "Beonsou": "Bronson",
    "BeoxsoN": "Bronson",
    "Bkonson": "Bronson",
    "Broxkon": "Bronson",
}

# All correction batches in order
BATCHES = [
    ("01-case-normalization", BATCH_01_CASE_NORMALIZATION),
    ("02-birdzell-ocr", BATCH_02_BIRDZELL_OCR),
    ("03-bronson-ocr", BATCH_03_BRONSON_OCR),
    ("04-bruce-ocr", BATCH_04_BRUCE_OCR),
    ("05-burke-ocr", BATCH_05_BURKE_OCR),
    ("05b-context-fixes", BATCH_05B_CONTEXT_FIXES),
    ("06-misc-justice-ocr", BATCH_06_MISC_JUSTICE_OCR),
    ("06b-per-curiam", BATCH_06B_PER_CURIAM),
    ("06c-stragglers", {"ENGLERT": "Englert", "Engleet": "Englert"}),
]


def apply_all(db_path: Path, dry_run: bool = False):
    conn = get_connection(db_path)

    # Check which batches have already been applied
    try:
        applied = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT batch FROM changelog"
            ).fetchall()
        }
    except Exception:
        applied = set()

    for batch_name, data in BATCHES:
        if batch_name in applied:
            print(f"  {batch_name}: already applied, skipping")
            continue

        if isinstance(data, dict):
            count = _apply_author_map(conn, batch_name, data, dry_run=dry_run)
        elif isinstance(data, list):
            count = _apply_per_curiam(conn, batch_name, data, dry_run=dry_run)
        else:
            continue
        label = " (dry run)" if dry_run else ""
        print(f"  {batch_name}: {count} rows{label}")

    if not dry_run:
        conn.commit()
    conn.close()


def revert_batch(db_path: Path, batch: str):
    conn = get_connection(db_path)

    rows = conn.execute(
        "SELECT id, opinion_id, field, old_value FROM changelog "
        "WHERE batch = ? ORDER BY id DESC",
        (batch,),
    ).fetchall()

    if not rows:
        print(f"No changelog entries for batch '{batch}'")
        conn.close()
        return

    for row in rows:
        conn.execute(
            f"UPDATE opinions SET {row['field']} = ? WHERE id = ?",
            (row["old_value"], row["opinion_id"]),
        )

    conn.execute("DELETE FROM changelog WHERE batch = ?", (batch,))
    conn.commit()
    print(f"Reverted {len(rows)} changes from batch '{batch}'")
    conn.close()


def show_log(db_path: Path):
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT batch, field, COUNT(*) as n, MIN(timestamp) as first, "
            "MAX(timestamp) as last FROM changelog GROUP BY batch, field ORDER BY first"
        ).fetchall()
    except Exception:
        print("No changelog table found.")
        return

    if not rows:
        print("Changelog is empty.")
        return

    print(f"{'Batch':<30} {'Field':<10} {'Count':>6}  {'Applied'}")
    print("-" * 70)
    for r in rows:
        print(f"{r['batch']:<30} {r['field']:<10} {r['n']:>6}  {r['first']}")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Apply/revert data corrections")
    sub = parser.add_subparsers(dest="command")

    ap = sub.add_parser("apply", help="Apply pending corrections")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--dry-run", action="store_true")

    rv = sub.add_parser("revert", help="Revert a batch")
    rv.add_argument("batch", help="Batch name to revert")
    rv.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    lg = sub.add_parser("log", help="Show changelog")
    lg.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    args = parser.parse_args()

    if args.command == "apply":
        apply_all(args.db, dry_run=args.dry_run)
    elif args.command == "revert":
        revert_batch(args.db, args.batch)
    elif args.command == "log":
        show_log(args.db)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
