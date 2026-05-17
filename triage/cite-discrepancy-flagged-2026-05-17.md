# Cite-discrepancy collisions — flagged for review (2026-05-17)

From the Type Y sweep's 37 cite bugs: 30 SAFE auto-corrected (batch `fix-cite-discrepancy-2026-05-17`). These **7** were NOT auto-applied — the Westlaw-footer-correct N.W. cite already belongs to another opinion, so it is not a simple OCR typo: either a genuine shared-page/companion pair, a lead+rehearing, or a deeper mispairing/dup. Each needs an individual read (same discipline as §6).

| oid | case | DB has | Westlaw footer | collides with oid |
|-----|------|--------|----------------|-------------------|
| 6023 | Sykes v. Allen (1903-07-03) | 98 N.W. 1134 | 96 N.W. 1134 | [5982] |
| 107 | State v. Gerhart (1905-03-06) | 103 N.W. 880 | 102 N.W. 880 | [68] |
| 190 | Walker v. Stimmel (1906-05-21) | 107 N.W. 1083 | 107 N.W. 1081 | [189] |
| 2167 | Olson v. Middlewest Grain Co. (1919-06-21) | 173 N.W. 474 | 173 N.W. 475 | [2169, 2170, 2171] |
| 2795 | Olness v. Duffy (1923-06-11) | 193 N.W. 113 | 194 N.W. 113 | [2826] |
| 4008 | State v. Ligaarden (1930-04-24) | (none) | 230 N.W. 729 | [4009] |
| 4062 | Ellis v. Fiske (1930-10-21) | (none) | 232 N.W. 891 | [4063] |

Note the adjacency pattern (4008→4009, 4062→4063, 107→68, 190→189, 2167→2169-2171, 2795→2826): collisions land on near/adjacent oids — likely companion opinions sharing a N.W. page, or lead+rehearing, or CL double-ingest. Resolve per-item: if genuine shared page, the corrected cite is right and both rows legitimately share it; if dup/mispairing, route to §6 / fix the pairing.
