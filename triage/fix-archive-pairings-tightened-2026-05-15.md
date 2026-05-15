# Archive linkage audit (dry-run)

## Summary
- ok           5531
- move         1
- swap         4
- detach       1
- verify       3
- dup-suspect  34
- unparseable  0

## move (1)
| os.id | opinion_id | archive_path | DB cites | title cite | target | swap_path | note |
|------:|-----------:|-------------|----------|-----------|-------:|-----------|------|
| 25495 | 17133 | `archive/2018/20170296.htm` | 909 N.W.2d 113 | 2018 ND 865 | 17133 | `—` | move linkage to opinion 17133 |

## swap (4)
| os.id | opinion_id | archive_path | DB cites | title cite | target | swap_path | note |
|------:|-----------:|-------------|----------|-----------|-------:|-----------|------|
| 30372 | 14585 | `archive/2006/20060031.htm` | 719 N.W.2d 759 | 2006 ND 132 | 18554 | `archive/2006/20060027.htm` | target 18554 already has archive; swap with archive/2006/20060027.htm |
| 30374 | 14587 | `archive/2006/20060158.htm` | 719 N.W.2d 759 | 2006 ND 130 | 18552 | `archive/2006/20060027.htm` | target 18552 already has archive; swap with archive/2006/20060027.htm |
| 30375 | 14588 | `archive/2006/20050374.htm` | 719 N.W.2d 759 | 2006 ND 129 | 18551 | `archive/2006/20060027.htm` | target 18551 already has archive; swap with archive/2006/20060027.htm |
| 30376 | 14589 | `archive/2006/20050446.htm` | 719 N.W.2d 759 | 2006 ND 131 | 18553 | `archive/2006/20060027.htm` | target 18553 already has archive; swap with archive/2006/20060027.htm |

## detach (1)
| os.id | opinion_id | archive_path | DB cites | title cite | target | swap_path | note |
|------:|-----------:|-------------|----------|-----------|-------:|-----------|------|
| 30373 | 14586 | `archive/2006/20060027.htm` | 719 N.W.2d 759 | 2006 ND 128 | 18550 | `—` | target 18550 already has archive |

## verify (3)
| os.id | opinion_id | archive_path | DB cites | title cite | target | swap_path | note |
|------:|-----------:|-------------|----------|-----------|-------:|-----------|------|
| 20727 | 12599 | `archive/1998/970402.htm` | 574 N.W.2d 591, 1998 ND 59 | 574 N.W.2d 591 | — | `—` | parallel-cite-only match; no neutral cite in title to corroborate — verify manually before trusting linkage |
| 25508 | 17148 | `archive/2018/20170286.htm` | 910 N.W.2d 171 | 910 N.W.2d 171 | — | `—` | parallel-cite-only match; no neutral cite in title to corroborate — verify manually before trusting linkage |
| 25529 | 17166 | `archive/2018/20170325.htm` | 910 N.W.2d 888 | 910 N.W.2d 888 | — | `—` | parallel-cite-only match; no neutral cite in title to corroborate — verify manually before trusting linkage |