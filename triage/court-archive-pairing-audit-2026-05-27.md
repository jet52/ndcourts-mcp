# Court-archive linkage audit (report-only)

Page-cardinality rule; court-archive fixes require reading the file BODY (titles are unreliable) and are not automated.

## Summary
- ok               4822
- shared_page      2
- title_elsewhere  7
- unresolved       6

## shared_page (2)
| os.id | opinion_id | other | path | title | note |
|------:|-----------:|-------|------|-------|------|
| 40567 | 20480 | 10796 | `court-archive/465/900333.htm` | Reimers Seed Co. v. Stedman, 465 N.W.2d 175 (N.D. App. 1991) | title cite NW2:465:175 shared with opinion(s) [10796]; verify by docket in body |
| 40568 | 20487 | 10797 | `court-archive/465/900255.htm` | City of Bismarck v. Berger, 465 N.W.2d 480 (N.D. App. 1991) | title cite NW2:465:480 shared with opinion(s) [10797]; verify by docket in body |

## title_elsewhere (7)
| os.id | opinion_id | other | path | title | note |
|------:|-----------:|-------|------|-------|------|
| 37539 | 7068 | 7020 | `court-archive/198/8758.htm` | East Grand Forks Federal Savings and Loan Assn. v. Mueller, 192 N.W.2d | title cite resolves to opinion(s) [7020], not the linked 7068; verify file BODY (title may be contaminated) |
| 37627 | 7194 | 7037 | `court-archive/210/8726.htm` | Matter of Anderson, 195 N.W.2d 345 (N.D. 1972) | title cite resolves to opinion(s) [7037], not the linked 7194; verify file BODY (title may be contaminated) |
| 37710 | 7288 | 7228 | `court-archive/219/8958.htm` | Naaden v. Hagen, 213 N.W.2d 702 (N.D. 1973) | title cite resolves to opinion(s) [7228], not the linked 7288; verify file BODY (title may be contaminated) |
| 40588 | 10823 | 10764 | `court-archive/466/900269.htm` | United Hospital v. D'Annunzio, 462 N.W.2d 652 (ND 1991) | title cite resolves to opinion(s) [10764], not the linked 10823; verify file BODY (title may be contaminated) |
| 41274 | 11675 | 11479 | `court-archive/518/930221.htm` | Disciplinary Board v. Schmidt, 505 N.W.2d 749 (N.D. 1993) | title cite resolves to opinion(s) [11479], not the linked 11675; verify file BODY (title may be contaminated) |
| 41835 | 20428 | 7351 | `court-archive/226/9038.htm` | Rogelstad v. Farmers Union Grain Terminal Association, 224 N.W.2d 544  | title cite resolves to opinion(s) [7351], not the linked 20428; verify file BODY (title may be contaminated) |
| 41879 | 20472 | 7116 | `court-archive/264/8785.htm` | Disciplinary Action Against McKinnon, 200 N.W.2d 62 (N.D. 1972) | title cite resolves to opinion(s) [7116], not the linked 20472; verify file BODY (title may be contaminated) |

## unresolved (6)
| os.id | opinion_id | other | path | title | note |
|------:|-----------:|-------|------|-------|------|
| 40583 | 10818 | — | `court-archive/466/900233.htm` | McCarter v. Pomeroy, 466 N.W.2d 563 (ND 1991) | title cite(s) match no opinion in DB |
| 40746 | 11007 | — | `court-archive/477/910390.htm` | , , (ND ) | title has no parseable citation |
| 40988 | 11314 | — | `court-archive/496/920122.htm` | Belfield Education Association v. Belfield Public School District No.  | title cite(s) match no opinion in DB |
| 41445 | 11896 | — | `court-archive/530/940278.htm` | Roen Land Trust v. Frederick, 350 N.W.2d 355 (N.D. 1995) | title cite(s) match no opinion in DB |
| 41575 | 12073 | — | `court-archive/541/950245.htm` | Ollom v. ND Workers Comp. Bureau, | title has no parseable citation |
| 41699 | 12232 | — | `court-archive/551/950386.htm` |  | archive file missing or empty |