# Constitution history — cross-publication judgment calls

Places where official publications diverge in punctuation, capitalization, or spelling.
Policy: the **session law (enacted text) governs** and was ingested; these are flagged for
review and cross-reference against ndconst.org section sidebar notes.
**138 variants flagged across segments 3–4.**

## 1925 clean-OCR verification pass (2026-06-08)

All 45 segment-3 (1914–1924) entries that cited the *old poor* embedded extraction
`/tmp/off1925.txt` were re-verified against the clean datalab-`marker` OCR of the same
publication: `~/refs/nd/const/processed/1925_official_constitution.md`. The clean OCR
confirmed the recorded off1925 reading in ~40 of 45 entries (those notes now stand on a
clean source rather than the poor pdftotext extraction). Five did not hold up:

- **3 spurious divergences** — the recorded off1925 reading was itself a poor-OCR artifact;
  the clean OCR shows 1925 *agrees with the session law*. Marked **RESOLVED** below: §67
  "in each house shall declare" (no comma), §162 "townships," (comma), §182 (Amdt XXXI)
  "in amounts, not exceeding" (comma).
- **2 note corrections** — §202 (Amdt XXVIII) and §185 (Amdt XXXII): clean 1925 actually
  *capitalizes* "Constitution" (the recorded "lowercase" was wrong); corrected in place.

No DB text changes result (session law already governs the enacted text); this pass only
prunes/hardens the variant log.



# Segment 3 (1914–1924)

## Amendment XV (1914-12-03) — N.D. Const. § 25
- **at least ten per cent. of the legal voters**
  - enacted (session law): at least ten per cent. (period after 'cent', appearing twice: also 'signed by ten per cent. of the legal voters')
  - other publications: off1925 prints 'ten per cent' with NO period both times; cl1913 also prints 'ten per cent' with no period. The session-law marker shows the abbreviating period.
- **This amendment shall be self executing**
  - enacted (session law): self executing (no hyphen)
  - other publications: off1925 prints 'self-executing' (hyphenated). cl1913 prints 'self executing' (no hyphen), matching the session law.
- **counties of this state shall be required**
  - enacted (session law): counties of this state
  - other publications: off1925 reads 'counties of this state'; cl1913 reads 'counties of the state'.
- **the basis upon which the number of legal voters**
  - enacted (session law): the whole number of votes cast for Secretary of State ... shall be the basis upon which the number of legal voters necessary to sign such petition shall be counted
  - other publications: off1925 agrees ('the whole number of votes cast ... the basis upon which'). cl1913 differs materially: 'the whole number of votes for secretary of state ... the basis on which' and 'for the initiative or for the referendum' (vs. session law 'for the initiative and referendum').
- **if upon aye and nay vote in each house**
  - enacted (session law): aye and nay vote
  - other publications: off1925 agrees 'aye and nay vote'; cl1913 differs: 'aye and no vote'.
- **from a majority of the counties, or by the legislative assembly if a majority of the members elect**
  - enacted (session law): by the legislative assembly if a majority (no comma after 'assembly')
  - other publications: off1925 agrees (no comma); cl1913 inserts a comma: 'by the legislative assembly, if a majority'.
- **until legislation shall be especially provided therefor**
  - enacted (session law): especially provided therefor
  - other publications: off1925 agrees ('especially'); cl1913 reads 'specially provided therefor'.

## Amendment XVI (1914-12-03) — N.D. Const. § 202
- **at least twenty-five per cent. of the legal voters**
  - enacted (session law): twenty-five per cent. (terminal period after "cent")
  - other publications: Both the 1913 Compiled Laws (/tmp/cl1913.txt) and the 1925 official snapshot (/tmp/off1925.txt) print "twenty-five per cent" with NO terminal period. The session law's period is confirmed by re-OCR at 400 and 600 DPI.
- **to which it has been referred, such amendement or amendments shall again be submitted**
  - enacted (session law): such amendement (spelled with an extra interior "e")
  - other publications: Both 1913 Compiled Laws and 1925 official snapshot read "such amendment" (normal spelling). The misspelling is in the session law and is confirmed by the marker OCR plus re-OCR at 400 and 600 DPI; preserved verbatim as a genuine session-law typo.

## Amendment XVII (1914-12-03) — N.D. Const. § 216
- **viz:**
  - enacted (session law): as is allotted by law, viz:
  - other publications: 1913 Compiled Laws (cl1913) prints "viz.:" with a period after viz; manual1919 prints "viz:"
- **may determine at Lisbon, in the County of Ransom**
  - enacted (session law): as the legislative assembly may determine at Lisbon, in the County of Ransom (no comma after 'determine')
  - other publications: cl1913 inserts a comma: "may determine, at Lisbon, in the county"; manual1919 reads "may determine at Lisbon,' in" (no comma after determine, matching session law apart from a stray OCR apostrophe)
- **FIRST / SECOND / THIRD heading capitalization and institution names**
  - enacted (session law): Headings and institution names capitalized: "FIRST: A Soldiers' Home ...", "SECOND: The School for the Blind of North Dakota ...", "An Industrial School and School for Manual Training", "A School of Forestry", "A Scientific School", "A State Normal School"
  - other publications: cl1913 (1913 Compiled Laws) renders headings and institution names in lower case: "First. A soldiers' home ...", "Second. The school for the blind of North Dakota ...", "school of forestry", "scientific school", "state normal school" (and uses a period after each ordinal rather than a colon)
- **at the City of Bottineau in the County of Bottineau**
  - enacted (session law): at the City of Bottineau in the County of Bottineau (no comma before 'in')
  - other publications: cl1913 inserts a comma: "at the city of Bottineau, in the county of Bottineau"
- **at the City of Minot in the County of Ward; provided**
  - enacted (session law): at the City of Minot in the County of Ward; provided, that no other institution, of a character similar (no comma before 'in'; semicolon before provided)
  - other publications: cl1913 reads "at the city of Minot, in the county of Ward provided, that" (comma before 'in', and an OCR-garbled "Ward ; ..." with the semicolon displaced)

## Amendment XVIII (1914-12-03) — N.D. Const. § 185
- **any other political sub-division shall loan**
  - enacted (session law): sub-division (hyphenated)
  - other publications: The 1925 official snapshot (off1925) prints 'subdivision' (one word, no hyphen). The session law (re-OCR) and the 1919 Legislative Manual print 'sub-division' (hyphenated).
- **vote of the people. Provided, that the state**
  - enacted (session law): Provided, (capital P, roman type, comma following; preceded by a period ending the prior clause)
  - other publications: The marker OCR (seg3_src.md) renders this word in italics as '*Provided*,' — an OCR/typographic artifact not present in the enacted session law. off1925 and manual1919 both print 'Provided,' in plain roman, consistent with the session law.

## Amendment XIX (1914-12-03) — N.D. Const. amend. art. XIX
- **erection, purchasing or leasing**
  - enacted (session law): erection, purchasing or leasing
  - other publications: 1913 Compiled Laws (cl1913.txt) prints 'erection, purchase or leasing' ('purchase' not 'purchasing'). That source reproduces the 1913 proposed/referred text approved March 10, 1913; the enacted session-law text and the 1919 Legislative Manual both read 'purchasing'.

## Amendment XX (1914-12-03) — N.D. Const. § 176, N.D. Const. § 179
- **used for any purposes other than the operation of a railroad (§ 179)**
  - enacted (session law): any purposes other than
  - other publications: 1919 Legislative Manual and 1954 Blue Book read "any purpose other than" (singular "purpose"); 1925 official snapshot agrees with the session law ("purposes")

## Amendment XXI (1916-12-07) — N.D. Const. § 216
- **one hundred and seventy thousand (170,000) acres**
  - enacted (session law): one hundred and seventy thousand (170,000) acres (marker + 1925 official agree, with "and" and the parenthetical numeral)
  - other publications: 1954 Blue Book reads "one hundred seventy thousand acres" — drops "and" and omits the (170,000) numeral (reflects later re-printing/amendments)
- **as is allotted by law, namely:**
  - enacted (session law): namely : (marker uses a space before the colon; sense identical)
  - other publications: 1925 official and 1954 Blue Book print "namely:" with no space
- **Sixth: A state normal school at the city of Minot, in the county of Ward.**
  - enacted (session law): ...at the city of Minot, in the county of Ward. (comma after Minot)
  - other publications: 1954 Blue Book reads "at the city of Minot in the county of Ward" — no comma after Minot
- **Second : A blind asylum, or such other institution**
  - enacted (session law): A blind asylum, or such other institution as the legislative assembly may determine, at such place in the county of Pembina... (marker + 1925 official)
  - other publications: 1954 Blue Book substitutes an entirely different Second clause ("The blind asylum shall be known as the North Dakota school for the blind...") reflecting a post-1916 amendment; not the enacted 1916 text
- **First: A soldiers' home, when located or such other**
  - enacted (session law): when located or such other charitable institution (no comma after "located"; marker + 1925 official)
  - other publications: 1954 Blue Book reads "when located, or such other" — adds a comma after "located"

## Amendment XXII (1916-12-07) — N.D. Const. § 216
- **Bottineau or Rolette; as the electors**
  - enacted (session law): Bottineau or Rolette; as the electors of said counties may determine (SEMICOLON after Rolette)
  - other publications: 1925 official and 1919 Legislative Manual (Article XXII printing) use a COMMA: 'Bottineau or Rolette, as the electors'. A separate 1919 Manual integrated printing of the same subdivision reads 'Bottineau AND Rolette' (and for or).
- **may determine at an election to be held**
  - enacted (session law): qualified electors of said county may determine at an election (NO comma after 'determine')
  - other publications: 1925 official agrees (no comma). 1919 Legislative Manual inserts a comma: 'may determine, at an election'.
- **prescribed by the legislative assembly with a grant of thirty thousand**
  - enacted (session law): to be held as prescribed by the legislative assembly with a grant of thirty thousand (NO comma before 'with')
  - other publications: 1919 Legislative Manual inserts a comma: 'legislative assembly, with a grant of thirty thousand'.
- **First: A soldiers' home, when located, or such other**
  - enacted (session law): A soldiers' home, when located, or such other charitable institution (COMMA after 'located')
  - other publications: 1925 official omits the second comma: 'when located or such other charitable institution'.
- **Seventh: (b) A state hospital for the insane**
  - enacted (session law): Seventh: (b) A state hospital for the insane at such place within this state as shall be selected by the legislative assembly, provided, that no other institution ... without a revision of this Constitution.
  - other publications: 1925 official and 1954 Blue Book detach the 'provided' clause and the geographic order differs in codified integration (e.g., 1954 prints 'Seventh: (a) ... Dickinson ... (b) A state hospital for the insane ...' as one combined subdivision). 'this Constitution' is capitalized in the session law; 1925 official/1954 Blue Book lowercase 'constitution' in some printings.

## Amendment XXIII (1918-12-05) — N.D. Const. § 135
- **directors or managers of a corporation**
  - enacted (session law): directors or managers
  - other publications: The 1925 official snapshot (off1925.txt line 4104) reads "directors and managers". All other sources (marker session-law text, 1919 Manual Article XXIII at line 10812, 1913 Compiled Laws, 1907 Manual, 1954 Blue Book) read "directors or managers". The off1925 "and" appears to be a printing deviation.
- **any cooperative corporation may adopt**
  - enacted (session law): cooperative (no hyphen)
  - other publications: off1925.txt ("co-operative"), 1919 Manual Article XXIII ("co-operative"), and 1954 Blue Book ("co-operative") all hyphenate. The enacted session-law marker text has no hyphen.
- **as he may prefer; provided, any cooperative**
  - enacted (session law): prefer; provided (semicolon)
  - other publications: The 1919 Manual Article XXIII printing (line 10812) reads "prefer, provided" with a comma. The marker session-law text and off1925 use a semicolon.

## Amendment XXIV (1918-12-05) — N.D. Const. amend. art. XXIV
- **shall seem just and necessary and may vary the tax rate**
  - enacted (session law): ...just and necessary and may vary the tax rate in such districts... (no comma after 'necessary'; singular 'rate')
  - other publications: 1919 Legislative Manual (/tmp/manual1919.txt) reads '...just and necessary, and may vary the tax rates in such districts...' — adds a comma after 'necessary' and uses plural 'rates'.

## Amendment XXV (1918-12-05) — N.D. Const. § 89
- **five judges, a majority of whom**
  - enacted (session law): five judges, a majority of whom (comma after 'judges'; the marker OCR renders this as a period -- 'five judges. a majority' -- which is OCR garble, not the enacted punctuation)
  - other publications: 1925 official snapshot and 1954 Blue Book both print a comma after 'judges'. The 1913 Compiled Laws (pre-amendment base text) likewise reads 'five judges, a majority'. The enacted/comma reading is adopted in the transcribed text.
- **pronounce a decision, but one or more**
  - enacted (session law): pronounce a decision, but one or more (comma before 'but')
  - other publications: 1925 official snapshot reads 'pronounce a decision, but' (comma, matching enacted). However other historical printings vary: the 1907/1919 Legislative Manuals and a second 1925-snapshot rendering print a semicolon ('pronounce a decision; but'), and the 1913 Compiled Laws drops the comma entirely ('pronounce a decision but'). Recorded as a cross-printing punctuation divergence for human review; the session-law comma is transcribed.

## Amendment XXVI (1918-12-05) — N.D. Const. § 25
- **shall go into effect on the thirtieth day after the election**
  - enacted (session law): thirtieth day
  - other publications: off1925.txt (1925 official ndlegis.gov snapshot) reads "thirteenth day" — a secondary-publication error. The enacted reading "thirtieth" was confirmed by re-OCR of the session-law PDF itself (sl1919.pdf p. 516).
- **Seven thousand Electors at large ... Each measure initiated by or referred to the Electors ... except an Emergency measure ... by the Secretary of State ... called by the Governor ... by the Board of Canvassers**
  - enacted (session law): Inconsistent initial-capitals throughout: Electors, Emergency (and Emergency Measure / Emergency Petition), Secretary of State, Governor, Legislature, Board of Canvassers, Referendum Petition, Committee for the Petitioners — while "secretary of state" and "legislature" appear lowercase in the first two paragraphs.
  - other publications: off1925.txt normalizes ALL of these to lowercase ("electors," "emergency," "secretary of state," "governor," "legislature," "board of canvassers"). The session-law's mixed capitalization is transcribed verbatim in the text field.
- **If a Referendum Petition is filed against an Emergency Petition, such measure shall be a law**
  - enacted (session law): against an Emergency Petition
  - other publications: off1925.txt prints "against an emergency petition [measure]" — the bracketed "[measure]" is the 1925 editor's interpolated correction, signaling that "petition" here is likely a drafting/printing slip in the enacted text; the session law as enacted reads "Petition" and is transcribed as such.
- **If conflicting measures initiated by or referred to the Electors**
  - enacted (session law): If conflicting measures
  - other publications: off1925.txt prints "In [If] conflicting measures" — i.e., the 1925 snapshot OCR/text reads "In" with an editorial "[If]" correction; the session law reads "If".

## Amendment XXVII (1918-12-05) — N.D. Const. § 67
- **set forth in the Act; provided, however, that**
  - enacted (session law): semicolon before "provided" — "set forth in the Act; provided, however, that"
  - other publications: The 1919 Legislative Manual and the 1954 Blue Book use a COMMA instead: "set forth in the act, provided, however, that". The 1925 official snapshot agrees with the session law (semicolon).
- **No Act of the legislative assembly ... an Emergency measure ... in the State**
  - enacted (session law): capitalizes "Act", "Session", "Legislature", "Emergency measure", and "State"
  - other publications: All three published codes (1925 official, 1919 Manual, 1954 Blue Book) render these lowercase: "act", "session", "legislature", "emergency measure", "state".
- **approval by the Governor**
  - enacted (session law): "Governor" capitalized
  - other publications: The 1919 Manual and 1954 Blue Book also capitalize "Governor"; the 1925 official snapshot lowercases it as "governor".
- **voting, in each house shall declare** — ✓ **RESOLVED (1925 clean OCR)**
  - enacted (session law): no comma after "house" — "in each house shall declare"
  - other publications: The 1919 Manual and 1954 Blue Book insert a comma: "in each house, shall declare". ~~off1925~~ **CORRECTED:** the clean 1925 marker OCR (`1925_official_constitution.md:1994`) reads "...present and voting, in each house shall declare it an emergency measure" — **no** comma after "house" (the comma is after "voting"). The recorded off1925 comma was a poor-OCR artifact; 1925 agrees with the session law.

## Amendment XXVIII (1918-12-05) — N.D. Const. § 202
- **majority of the members elected to each house it shall be submitted**
  - enacted (session law): each house it shall be submitted (no comma after "house")
  - other publications: manual1919 and bb1954 insert a comma: "each house, it shall be submitted." off1925 agrees with the session law (no comma).
- **such petition shall be signed by twenty thousand of the Electors at large**
  - enacted (session law): twenty thousand of the Electors at large
  - other publications: manual1919 and bb1954 omit "of the": "twenty thousand electors at large." off1925 agrees with the session law: "twenty thousand of the electors at large."
- **so proposed shall be submitted to the Electors and shall become a part of the Constitution**
  - enacted (session law): shall be submitted to the Electors and shall become a part of the Constitution
  - other publications: manual1919 and bb1954 read "shall be submitted to the electors and become a part of the constitution" (dropping the second "shall"). off1925 agrees with the session law ("shall become a part").
- **All provisions of the Constitution relating to the submission and adoption of measures by initiative petition and on referendum petition, shall apply**
  - enacted (session law): by initiative petition and on referendum petition, shall apply (comma only after "petition")
  - other publications: manual1919 and bb1954 add a comma after "initiative petition": "by initiative petition, and on referendum petition shall apply" (comma after "initiative petition," none after "referendum petition"). off1925 matches the session law.
- **capitalization of Constitution / State / Legislature / Electors / Secretary of State**
  - enacted (session law): marker capitalizes "Constitution," "State," "Legislature," "Electors," and "Secretary of State"
  - other publications: manual1919 and bb1954 lowercase "constitution," "state," "legislature," "electors"; manual1919 and bb1954 capitalize "Secretary of State." **CORRECTED (1925 clean OCR, `1925_official_constitution.md:4480`):** off1925 actually *capitalizes* "Constitution" (twice — "a part of the Constitution," "amendments to the Constitution"), matching the session law; it lowercases only "electors" and "secretary of state." The earlier "off1925 lowercases constitution" was a poor-OCR misread. These are typographic/period-rendering differences across printings.

## Amendment XXIX (1918-12-05) — N.D. Const. § 176
- **same class of property including franchises, within**
  - enacted (session law): property including franchises, within (no comma after "property"; comma after "franchises")
  - other publications: manual1919 reads "property; including franchises within" (semicolon after "property", no comma after "franchises"); off1925 reads "property including franchises, within" (agrees with session law); bb1954 reads "property including franchises within" (no comma after "franchises")
- **every character whatsoever, upon land, shall be deemed**
  - enacted (session law): every character whatsoever, upon land, shall be deemed (no comma before "whatsoever"; comma after "land")
  - other publications: manual1919 and bb1954 read "every character, whatsoever, upon land shall be deemed" (comma before "whatsoever"; no comma after "land"); off1925 reads "every character whatsoever, upon land, shall be deemed" (agrees with session law)
- **County and Municipal Corporations, and property used exclusively**
  - enacted (session law): County and Municipal Corporations, and property used exclusively (capitalized "County", "Municipal Corporations"; comma after "Corporations")
  - other publications: off1925, manual1919, and bb1954 lowercase "county and municipal corporations"; manual1919 and bb1954 omit the comma after "corporations"; off1925 keeps the comma after "corporations"
- **school, religious, cemetery, charitable**
  - enacted (session law): for school, religious, cemetery, charitable (singular "school")
  - other publications: bb1954 reads "for schools, religious" (plural "schools"); off1925 and manual1919 read singular "school" (agree with session law)
- **restricted by this Article, the Legislature**
  - enacted (session law): by this Article, the Legislature (capitalized "Article" and "Legislature")
  - other publications: off1925 and manual1919 lowercase "article" and "legislature"; off1925 lowercases "article" but the session-law/seg3 reading capitalizes both

## Amendment XXX (1918-12-05) — N.D. Const. § 177
- **the limitation specified in Section 174**
  - enacted (session law): singular "limitation" ("in addition to the limitation specified")
  - other publications: plural "limitations" in the 1919 Legislative Manual and the 1954 Blue Book; the 1925 official snapshot agrees with the session law ("limitation")
- **manufacturing or pasturage, may be exempt**
  - enacted (session law): comma after "pasturage" ("manufacturing or pasturage, may be exempt")
  - other publications: no comma after "pasturage" in the 1919 Legislative Manual and the 1954 Blue Book; the 1925 official snapshot agrees with the session law (comma present)

## Amendment XXXI (1918-12-05) — N.D. Const. § 182
- **real or personal property of State owned utilities**
  - enacted (session law): real or personal property
  - other publications: off1925 explanatory note (1918 text) agrees: 'real or personal'. manual1919 reads 'real and personal'. (The later 1924 Art. 42 re-amendment in off1925 running text and bb1954 also reads 'real and personal'.)
- **property of State owned utilities, enterprises**
  - enacted (session law): State owned utilities (capital S in first occurrence; 'state owned' lowercase in the second occurrence within the section)
  - other publications: off1925 note prints both occurrences lowercase 'state owned'; manual1919 prints 'state-owned' (hyphenated, lowercase). The capital 'S' in the marker first occurrence is likely an OCR/printing artifact.
- **in amounts, not exceeding its value** — ✓ **RESOLVED (1925 clean OCR)**
  - enacted (session law): in amounts, not exceeding its value (comma after 'amounts')
  - other publications: manual1919 prints 'in amounts not exceeding' (no comma). ~~off1925 'in amounts. not exceeding' (stray period)~~ **CORRECTED:** the clean 1925 marker OCR (`1925_official_constitution.md:4125`, the 1918 Art. XXXI rendering) reads "in amounts, not exceeding its value" — comma, agreeing with the session law. The stray period was a poor-OCR artifact only.
- **and provided, further, that the state shall not issue**
  - enacted (session law): and provided, further, that
  - other publications: off1925 note agrees: 'provided, further'. manual1919 reads 'and, provided further, that'.

## Amendment XXXII (1918-12-05) — N.D. Const. § 185
- **any county or city, may make internal improvements**
  - enacted (session law): comma present after "city": "any county or city, may make"
  - other publications: The 1919 Legislative Manual (manual1919) omits the comma: "any county or city may make". The 1925 official snapshot (off1925) retains the comma, agreeing with the session law.
- **any industry, enterprise or business, not prohibited**
  - enacted (session law): comma present after "business": "enterprise or business, not prohibited"
  - other publications: The 1919 Legislative Manual (manual1919) omits the comma: "enterprise or business not prohibited". The 1925 official snapshot (off1925) retains the comma, agreeing with the session law.
- **not prohibited by Article 20 of the Constitution**
  - enacted (session law): capital "A" and capital "C": "Article 20 of the Constitution"
  - other publications: The 1925 official snapshot lowercases "article" but **capitalizes "Constitution"**: "article 20 of the Constitution" (clean OCR `1925_official_constitution.md:4209`; the earlier "lowercases both" was imprecise — only "article" is lowercased). The 1919 Manual matches the session law with capital "Article 20".

## Amendment XXXIII (1920-04-15) — N.D. Const. amend. art. XXXIII
- **thirty per cent of the qualified electors**
  - enacted (session law): thirty per cent of the qualified electors (no comma after "cent")
  - other publications: 1919 Legislative Manual prints a comma: "thirty per cent, of the qualified electors"
- **for the office of Governor**
  - enacted (session law): office of Governor (capital G)
  - other publications: 1919 Legislative Manual lowercases it: "office of governor"

## Amendment XXXIV (1920-04-15) — N.D. Const. § 161
- **pasturage and meadow purposes and at a public auction**
  - enacted (session law): pasturage and meadow purposes and at a public auction (no comma or punctuation between 'purposes' and 'and'; the marker's stray hyphen 'purposes-' is OCR garble)
  - other publications: 1925 official, 1919 Manual, and 1954 Blue Book all read 'purposes and' with no intervening punctuation — confirming the enacted reading.
- **not exceeding five years as the legislature may provide**
  - enacted (session law): not exceeding five years as the legislature may provide (no comma after 'years')
  - other publications: 1925 official snapshot also has no comma after 'years'. The 1919 Legislative Manual inserts a comma: 'not exceeding five years, as the legislature may provide.'
- **Provided further, that coal lands may also be leased**
  - enacted (session law): Provided further, that (comma after 'further' only)
  - other publications: 1925 official reads 'Provided further, that' (matches). The 1919 Legislative Manual reads 'Provided, further, that' (additional comma after 'Provided').
- **Board of University and School Lands**
  - enacted (session law): Board of University and School Lands (initial caps; marker OCR 'UniVersity' is garble)
  - other publications: 1925 official lowercases: 'board of university and school lands'. 1919 Manual and 1954 Blue Book capitalize 'Board of University and School Lands'.
- **The Legislative Assembly shall have authority**
  - enacted (session law): The Legislative Assembly (initial caps)
  - other publications: 1925 official reads 'The legislative assembly' (lowercase). 1919 Manual reads 'The Legislative Assembly' (caps).

## Amendment XXXV (1920-04-15) — N.D. Const. § 183
- **a school district, by a majority vote may increase such indebtedness five per cent on such assessed value**
  - enacted (session law): five per cent
  - other publications: The 1925 official ndlegis.gov snapshot (/tmp/off1925.txt) reads "five per centum" here. The 1954 Blue Book (/tmp/bb1954_marker) agrees with the session law ("five per cent"). Judgment call: the session-law marker reading "five per cent" is transcribed per the authority rule; this is the only substantive cross-publication divergence.
- **school district or any other political sub-division shall never exceed**
  - enacted (session law): sub-division (hyphenated)
  - other publications: The 1925 official snapshot prints "subdivision" (unhyphenated) in this first occurrence; the session-law marker hyphenates only the first occurrence and prints "subdivision" later. Minor styling divergence.
- **for no other purposes whatever. All bonds**
  - enacted (session law): purposes whatever. (plural "purposes")
  - other publications: The 1919 Legislative Manual's earlier/different proposal reads "purpose whatever" (singular); the 1925 official snapshot and session-law marker both read "purposes whatever." Noted only because the earlier proposal is a near neighbor in the sources.

## Amendment XXXVI (1920-04-15) — N.D. Const. amend. art. XXXVI
- **moves from one precinct to another within the same county**
  - enacted (session law): within the same county
  - other publications: The superseding 1922 version (Article 40), as printed in off1925 (§121 integration), bb1954 line 426, and marker line 563, reads "within the state" instead of "within the same county." No publication reproduces this 1920 article's "within the same county" reading.
- **the precinct from which he moved, until he establishes his residence in the precinct to which he moved**
  - enacted (session law): moved ... moved (past tense)
  - other publications: The superseding 1922 version (off1925, bb1954, marker Article 40) uses present tense throughout: "from which he moves ... to which he moves."
- **in the county ninety days, and in the precinct thirty days**
  - enacted (session law): ninety days ... thirty days (spelled out)
  - other publications: The marker rendering of the superseding 1922 Article 40 (line 563) uses numerals "90 days" and "30 days"; bb1954's 1922 version spells them out ("ninety days"/"thirty days").

## Amendment XXXVII (1920-12-02) — N.D. Const. § 121
- **severed their tribal relation two years**
  - enacted (session law): tribal relation (singular)
  - other publications: The 1954 Blue Book reads "tribal relations" (plural). The session law and the 1925 official snapshot both read "tribal relation" (singular).
- **First, citizens of the United States; Second, civilized persons**
  - enacted (session law): First ... Second (both capitalized)
  - other publications: The 1925 official snapshot capitalizes "First" but prints "second" in lowercase. The 1954 Blue Book also prints "second" lowercase. The session law capitalizes both.

## Amendment XXXVIII (1920-12-02) — N.D. Const. § 215
- **A State Training School at the City of Mandan**
  - enacted (session law): City (capitalized); institution names capitalized throughout (e.g., "State Training School", "State Normal School", "State Hospital for the Insane")
  - other publications: 1925 official ndlegis.gov snapshot lowercases both the descriptors and "city"/"county" throughout: "A state training school at the city of Mandan, in the county of Morton."
- **in the Act of Congress approved February 22, 1889**
  - enacted (session law): ARTICLE 38 canvassers' text (sl1921): "Act of Congress approved February 22, 1889" (Act capitalized, no "nd" suffix on 22)
  - other publications: The 1919 proposing-resolution instance in the same marker reads "act of Congress Approved February 22nd, 1889" (lowercase act, capitalized Approved, ordinal "22nd"); 1925 official reads "act of Congress approved February 22, 1889" (lowercase act).
- **an institution for the Feeble Minded**
  - enacted (session law): Feeble Minded (capitalized)
  - other publications: 1925 official: "an institution for the feeble minded" (lowercase).

## Amendment XXXIX (1920-12-02) — N.D. Const. § 162
- **any sub-division on which the same may be loaned**
  - enacted (session law): sub-division (hyphenated)
  - other publications: subdivision (no hyphen) in off1925.txt (1925 official snapshot, current text), bb1954_const.md (1954 Blue Book), and the prior-version cl1913.txt (1913 Compiled Laws)
- **or of townships, or of municipalities within the state** — ✓ **RESOLVED (1925 clean OCR)**
  - enacted (session law): townships, (comma) — per 400-dpi re-OCR of sl1921.pdf p.272
  - other publications: townships. (period) in the marker compilation seg3_src.md and in the poor off1925.txt; judged an OCR/typesetting artifact. **CONFIRMED:** the clean 1925 marker OCR (`1925_official_constitution.md:3637`) reads "or of townships, or of municipalities within the state" — comma, agreeing with the session law and the prior cl1913 version. The "period" was a poor-OCR artifact only.

## Amendment XL (1922-07-28) — N.D. Const. amend. art. XL
- **in the county 90 days and in the precinct 30 days**
  - enacted (session law): numerals: "90 days" and "30 days"
  - other publications: 1954 Blue Book spells these out as "ninety days" and "thirty days"
- **Section/article designation**
  - enacted (session law): enacted and published as "Article 40" (a constitutional amendment adopted by the electors)
  - other publications: 1954 Blue Book integrates the same operative text as the body of "Section 121" (superseding the earlier §121 elector-qualification language)

## Amendment XLI (1924-04-17) — N.D. Const. § 173
- **At the First general election**
  - enacted (session law): First (capitalized)
  - other publications: off1925.txt lowercases it: "At the first general election"
- **in each organized county in the State**
  - enacted (session law): State (capitalized)
  - other publications: off1925.txt lowercases it: "in the state"
- **elected and qualified; provided in counties**
  - enacted (session law): qualified ; provided (space before the semicolon as typeset/OCR'd in the session law)
  - other publications: off1925.txt sets it tight: "qualified; provided"; transcribed here without the spurious pre-semicolon space

## Amendment XLII (1924-04-17) — N.D. Const. § 182
- **of such other provisions to the payment of said principal**
  - enacted (session law): no comma after 'provisions' ("...of such other provisions to the payment...")
  - other publications: off1925.txt also has no comma here. NOTE the SUPERSEDED 1918 version of this same section (seg3_src.md line 403, Article XXXI) read 'of such other provisions, to the payment' WITH a comma. The enacted 1924 reading (no comma) is adopted.
- **first mortgage upon real estate**
  - enacted (session law): singular 'first mortgage' ("secured by first mortgage upon real estate")
  - other publications: off1925.txt agrees (singular). The superseded 1918 Article XXXI version (seg3_src.md line 397) read plural 'first mortgages'. Enacted 1924 = singular.
- **except for the purpose of repelling invasion**
  - enacted (session law): singular 'purpose' ("except for the purpose of repelling invasion")
  - other publications: off1925.txt agrees (singular 'purpose'). The superseded 1918 Article XXXI version (seg3_src.md line 403) read plural 'purposes'. Enacted 1924 = singular.


# Segment 4 (1956–1980, CAA PDFs)

## Amendment LXV (1956-07-26) — N.D. Const. amend. art. LXV
- **N.D. Blue Book 1961, Article 65**
  - enacted (session law): § 1.) The legislative assembly ... under such terms and conditions as the legislative assembly may prescribe. (CAA enacted text)
  - other publications: Rendered as 'Section 1.' (dropping the '§ 1.)' enacting marker). Substantive text identical; remaining differences are OCR noise (e.g. 'such terms .uid conditions').
- **N.D. Blue Book 1973, Article 65**
  - enacted (session law): § 1.) The legislative assembly ... under such terms and conditions as the legislative assembly may prescribe. (CAA enacted text)
  - other publications: Rendered as 'Section 1.' (dropping the '§ 1.)' enacting marker). Substantive text identical to CAA.

## Amendment LXVI (1956-07-26) — N.D. Const. § 14
- **N.D. Const. § 14 (Art. 66)**
  - enacted (session law): CAA 1957 ch. 397 (clean typeset): '...irrespective of any benefit from any improvement proposed by such corporation...' — single-spelling, no internal capitalization of 'improvement', 'money', 'jury' mid-sentence.
  - other publications: 1961 and 1973 Blue Book integrated codifications carry the identical substantive text and identical amendment note ('Amendment: Art. 66, June 26, 1956, (S.L. 1957, ch. 397)'). The only divergences are OCR scanning artifacts (e.g., 1973 stray mid-sentence capitals 'In money', 'any Improvement', 'Its departments', 'way. It may', 'shall Immediately', 'a Jury trial'; 1961 garbled letters 'shnll', 'sulxlivisions', 'muy', 'wuy', 'wuived'). No genuine punctuation, capitalization, or spelling variant in the official text was found; the CAA reading governs.

## Amendment LXVII (1956-07-26) — N.D. Const. § 173
- **N.D. Const. § 173 (as enacted by amend. art. LXVII)**
  - enacted (session law): CAA ch. 398, Art. 67 (PRIMARY, governs): "...there shall be elected in each county... who shall hold office until their successors are elected and qualified..."
  - other publications: 1961 Blue Book substantively matches the CAA text (apparent differences are OCR noise: 'ilecled'/'elected', 'yeurs'/'years', 'ench'/'each', 'nnd'/'and', 'comity'/'county' — no genuine punctuation/capitalization/spelling divergence). 1973 Blue Book prints a DIFFERENT section 173 (four-year term, 'self-executing' language) because Art. 77 (Nov. 6, 1962; S.L. 1963, ch. 447) superseded the Art. 67 version; the 1973 text is not a variant of this amendment.

## Amendment LXVIII (1958-07-24) — N.D. Const. § 203
- **N.D. Const. § 203, paragraph 2 ("Second.")**
  - enacted (session law): CAA 1959, ch. 430 (clean typeset): "...by act of Congress; that the lands belonging to citizens..." — lowercase "act"; standard punctuation as set out in "text".
  - other publications: BB1961 (line ~17106) integrated text substantively identical (OCR noise only: "ng''ee"=agree, "dis-claim", "ar Indinn"=or Indian, "hinds"=lands, "nets"=acts). The resolution's recital clause (CAA header) capitalizes "Act of Congress" — a recital, not the enacted body. No substantive punctuation/spelling/capitalization divergence found in the enacted text across sources.

## Amendment LXIX (1958-07-24) — N.D. Const. § 121
- **N.D. Const. § 121**
  - enacted (session law): CAA ch. 431 (1959 S.L.): "Every person of the age of twenty-one or upwards who is a citizen of the United States and who shall have resided in the state one year and in the county ninety days and in the precinct thirty days next preceding any election shall be a qualified elector at such election."
  - other publications: Blue Book 1961 and 1973 match the enacted text. Apparent differences in the OCR ("nnd"/"and", "bis"/"his", "Is"/"is", "Provtded"/"Provided") are OCR scanning artifacts in the poor-quality Blue Book texts, not genuine textual divergences. No substantive punctuation, capitalization, or spelling divergence found.

## Amendment LXX (1960-07-28) — N.D. Const. § 82, N.D. Const. § 83, N.D. Const. § 84
- **N.D. Const. §§ 82, 83 (officer titles)**
  - enacted (session law): CAA enacts officer titles in lowercase ("secretary of state, auditor, treasurer, superintendent of public instruction, commissioner of insurance ... attorney general, a commissioner of agriculture and labor")
  - other publications: 1973 Blue Book integrated text capitalizes the officer titles ("Secretary of State, Auditor, Treasurer, Superintendent of Public Instruction, Commissioner of Insurance, an Attorney General, a Commissioner ..."); 1961 Blue Book lowercase but OCR-garbled ("Section 8 2 .", "shnll"). Capitalization difference is a codifier styling choice, not a substantive change; enacted CAA lowercase governs.

## Amendment LXXI (1960-07-28) — N.D. Const. § 155
- **N.D. Const. § 155**
  - enacted (session law): CAA 1961, ch. 404: "...salable by virtue of this section. No more than one-half of the remainder within ten years after the same become salable as aforesaid." / "...except that leases may be executed for the extraction and sale of such materials..."
  - other publications: Blue Book 1961 OCR garbage only (no real text variants): "became salable us aforesaid", "teases may be executed", "Mich terms". Blue Book 1973 OCR garbage only: "same become soluble as aforesaid". Both Blue Books label the amendment "Art. 71, June 28, 1960 (S.L. 1959, ch. 436)". All divergences are scanning/OCR artifacts, not genuine punctuation/capitalization/spelling differences.

## Amendment LXXII (1960-07-28) — N.D. Const. § 26, N.D. Const. § 29, N.D. Const. § 35
- **N.D. Const. § 26**
  - enacted (session law): CAA (Chapter 405): "The senate shall be composed of forty-nine members."
  - other publications: bb1961/bb1973 confirm identical substance and attribute to Art. 72, June 28, 1960 (S.L. 1959, ch. 438); only OCR garble present (e.g., bb1961 'Section 2G ... shnll he cnmposLAi'), not a genuine textual variant.

## Amendment LXXIII (1960-07-28) — N.D. Const. amend. art. LVI
- **/tmp/bb1961.txt Article 56**
  - enacted (session law): ...other aviation motor fuel excise and license taxation used / by aircraft, after deduction of cost of administration and collection authorized by legislative appropriation only, and statutory refunds, shall be appropriated and used solely...
  - other publications: OCR corruptions only (not real divergences): 'avinticn' for 'aviation', 'med' for 'used', 'nnd' for 'and', 'he' for 'be'. No genuine punctuation/spelling/capitalization differences.
- **/tmp/bb1973.txt Article 56**
  - enacted (session law): ...the payment of obligations incurred in the construction, reconstruction, repair and maintenance of public highways.
  - other publications: OCR corruption only: capital 'In' for 'in' ('incurred In the construction'). No genuine divergence.

## Amendment LXXIV (1960-12-08) — N.D. Const. § 215
- **N.D. Const. § 215, Third (paragraph third)**
  - enacted (session law): CAA 1961 (Chapter 407): "Third: The North Dakota State University of Agriculture and Applied Science at the City of Fargo, in the County of Cass." (capital C in "City" and "County")
  - other publications: Blue Book 1973 (OCR, gross check): "Third: The North Dakota State University of Agriculture and Applied Science at the city of Fargo, in the county of Cuss." — lowercase "city"/"county" and OCR garble "Cuss" for "Cass". Blue Book 1961 has no clean constitutional-text rendering of this paragraph (only biographical mentions of the institution name).

## Amendment LXXV (1962-07-26) — N.D. Const. amend. art. LXXV
- **N.D. Const. amend. art. LXXV (Continuity of Government)**
  - enacted (session law): S.L. 1963, ch. 445: "length of sessions, quorum and voting requirements"; "shall in all respects conform"; "in the judgment of the legislative assembly so to do would be impracticable"
  - other publications: Blue Book 1973 (Art. 75) reads "length or sessions" (drops "of sessions,"), "shall in all respect conform", and capitalizes "In the judgment"/"would be Impracticable" — these are OCR artifacts of the poor scan, not genuine textual variants. No substantive divergence detected.

## Amendment LXXVI (1962-12-06) — N.D. Const. amend. art. LXXVI
- **N.D. Const. amend. art. LXXVI § 2**
  - enacted (session law): CAA (S.L. 1963, ch. 446) reads "five percent" (one word) and capitalizes "Constitution."
  - other publications: Blue Book 1973 (ARTICLE 76, Section 2) reads "five per cent" (three words) and lowercases "constitution"; this is the integrated-code restyling/OCR, not a substantive divergence.
- **N.D. Const. amend. art. LXXVI (section designators)**
  - enacted (session law): CAA designates the six provisions "§ 1.)" through "§ 6.)".
  - other publications: Blue Book 1973 renders the same provisions as "Section 1." through "Section 6." under the heading "ARTICLE 76"; numbering format differs but substance is identical.

## Amendment LXXVII (1962-12-06) — N.D. Const. § 173
- **N.D. Const. § 173 (Art. X)**
  - enacted (session law): S.L. 1963, ch. 447: "... a clerk of the district court, who shall be electors in the county in which they are elected and who shall hold their office for a term of four years and until their successors are elected and qualified ..." (Initiated Measure, Art. 77; approved Nov. 6, 1962)
  - other publications: ND Blue Book 1973 (OCR) reads consistently with the enacted text apart from OCR noise (e.g., "shull lie elected," "u clerk," "cterk," "Its operation"); ND Blue Book 1961 (OCR) prints the superseded pre-1962 text with two-year terms ("every two years thereafter ... shall hold office until their successors are elected and qualified").

## Amendment LXXVIII (1964-07-30) — N.D. Const. art. 54, § 6(d)
- **N.D. Const. art. 54, § 6(d)**
  - enacted (session law): CAA ch. 473 (clean typeset): "... a single unified budget covering the needs of all the institutions under its control." — governs; verbatim text in "text".
  - other publications: bb1973.txt integrated Blue Book reproduces the identical substantive provision ("single unified budget covering the needs of all the institutions under its control ... may be separate from those of state educational institutions"). Divergences are OCR artifacts only (e.g., "und"/"u" for "and"/"a", "us" for "as"), not genuine textual variants. bb1961.txt does not contain the post-amendment subdivision (d) language (pre-amendment edition; only narrative agency descriptions of the Agricultural Experiment Station / Extension Service appear).

## Amendment LXXIX (1964-07-30) — N.D. Const. § 113
- **N.D. Const. § 113**
  - enacted (session law): 1965 Session Laws ch. 474 (CAA): "...municipal judges in cities, incorporated towns, and villages, who shall hear, try, and determine cases arising under the ordinances of said cities, towns and villages..."
  - other publications: 1973 Blue Book (integrated, poor OCR) reads "municipal judges In cities. Incorporated towns, and villages... arising under the ordinances of suid cities" — capitalization (In/Incorporated), terminal period mid-sentence, and "suid" for "said" are OCR artifacts, not genuine publication divergences. The pre-amendment 1961 Blue Book carries the prior "police magistrate" text (confirming the amendment took effect between editions).

## Amendment LXXX (1964-07-30) — N.D. Const. § 71, N.D. Const. § 82, N.D. Const. § 150
- **N.D. Const. § 71**
  - enacted (session law): CAA (ch. 475): "a governor, who shall reside at the seat of government and shall hold his office for the term of four years beginning in the year 1965" (lowercase "governor"; phrase "beginning in the year 1965")
  - other publications: 1973 Blue Book integrated codification: "a Governor ... beginning the year 1965" (capitalizes "Governor"; drops "in" before "the year 1965"). OCR-quality codification difference; enacted CAA text governs.
- **N.D. Const. § 150**
  - enacted (session law): CAA (ch. 475): ends at "... shall be fixed by law." (no proviso)
  - other publications: 1973 Blue Book integrated codification adds a later proviso: "Provided, however, a superintendent of schools may be elected by and serve two or more counties or parts of counties as provided by law." This reflects a later, separate amendment to sec. 150, NOT a variant of the 1964 enacted text; excluded from "text".

## Amendment LXXXI (1964-12-03) — N.D. Const. § 25
- **1961 North Dakota Blue Book (integrated text of § 25, tenth paragraph), line 15808 et seq.**
  - enacted (session law): CAA Ch. 476 (clean): "The secretary of state shall cause to be printed and mailed to each elector a publicity pamphlet, containing a copy of each measure together with its ballot title... shall be the sum of two hundred dollars per page."
  - other publications: Blue Book OCR (gross check only): "The Secretary State shall cause to he printed and mailed to each elector a publicity pamphlet, containing a copy of each measure together with its ballot title... Any citi/en, or the officers of any organization... concerning nny mensure..." These are OCR artifacts in the Blue Book scan, not genuine textual divergences; the CAA text governs.
- **1973 North Dakota Blue Book, line 3435**
  - enacted (session law): Affirmative vote per CAA Ch. 476: 125,117 to 96,283; approved November 3, 1964.
  - other publications: 1973 Blue Book lists "Constitution, publicity pamphlet (Ch. 476, S.L. 1965) 125,177 96,283" — affirmative tally differs by one digit (125,177 vs. 125,117), an OCR/typographical variant in the vote count, not in constitutional text.

## Amendment LXXXII (1966-10-06) — N.D. Const. § 175
- **N.D. Const. § 175**
  - enacted (session law): CAA 1967 ch. 508 (authoritative): "...and every law imposing a tax shall state distinctly..."; "...in any law imposing a tax or taxes..."; "...such tax or taxes are imposed or measured..."
  - other publications: bb1973 integrated text matches substantively; apparent divergences are OCR artifacts only, not real variants: 'law Impos-ing' (spurious capital I from line-break hyphenation) and similar mid-word capital I's. bb1961 contains only the pre-amendment original (lacks the entire 'Notwithstanding the foregoing...' second sentence), confirming the second sentence is the amendment's addition.

## Amendment LXXXIII (1966-10-06) — N.D. Const. § 150
- **N.D. Const. § 150 (1973 Blue Book integrated code)**
  - enacted (session law): CAA Ch. 509: "...elected every four years beginning in the year 1964, whose qualifications, duties, powers and compensation shall be fixed by law. Provided, however, a superintendent of schools may be elected by and serve two or more counties or parts of counties as provided by law."
  - other publications: 1973 Blue Book OCR matches the enacted CAA text verbatim (modulo OCR noise); no substantive punctuation, capitalization, or spelling divergence detected. 1961 Blue Book shows the superseded pre-amendment text ('elected every two years'), confirming the amendment's operation.

## Amendment LXXXIV (1966-12-08) — N.D. Const. § 130
- **N.D. Const. § 130 (second paragraph, first sentence)**
  - enacted (session law): Constitutional Amendments Approved, ch. 510 (1967 Session Laws): "The legislative assembly shall provide by law for the establishment of home rule in cities and villages." (CAA pdftotext shows a stray "·" artifact before "cities"; the enacted word is "cities".)
  - other publications: 1973 ND Blue Book: "establishment of home rule in cities and villages" — agrees with enacted text (no stray character); remaining Blue Book differences are OCR errors (me/the, lb/its, mis/this).

## Amendment LXXXV (1968-10-03) — N.D. Const. § 148
- **N.D. Const. § 148 (Blue Book 1973 integrated text, OCR)**
  - enacted (session law): ...to assist in the financing of public schools of higher education.
  - other publications: BB1973 OCR reads "to assist In the financing" (capital I) — an OCR artifact, not a genuine textual variant; otherwise identical to the enacted CAA text.

## Amendment LXXXVI (1968-10-03) — N.D. Const. § 41, N.D. Const. § 53, N.D. Const. § 56
- **N.D. Const. § 53 (recess clause, unchanged portion)**
  - enacted (session law): CAA ch. 582: "twelve o'clock noon on the first Tuesday after the first Monday in January"
  - other publications: BB1973: "twelve o'clock noon of the first Tuesday after the first Munday in January" (of vs. on; 'Munday' is OCR noise)
- **N.D. Const. § 56 (impeachment exception)**
  - enacted (session law): CAA ch. 582: "except in the case of impeachment"
  - other publications: BB1973: "except in case of impeachment" (omits 'the')

## Amendment LXXXVII (1970-10-01) — N.D. Const. amend. art. LXXXVII
- **necessary for the payment**
  - enacted (session law): necessary for the payment (CAA ch. 616) — note: the CAA pdftotext extraction renders this as 'fer', an OCR misread; bb1973 reads 'for'; corrected to 'for' as the manifest enacted reading
  - other publications: bb1973 Art. 87: '...necessary for the pay-ment...' (OCR; reads 'for')
- **veterans of the Vietnam conflict**
  - enacted (session law): veterans of the Vietnam conflict (CAA ch. 616)
  - other publications: bb1973 Art. 87 OCR: 'vetenms for the Viet Nam conflict' — OCR-corrupted; the CAA 'veterans of the Vietnam conflict' governs

## Amendment LXXXVIII (1970-10-01) — N.D. Const. amend. art. LXXXVIII
- **Art. 88, para. 1 — "Such convention shall be called and conducted"**
  - enacted (session law): S.L. 1971, ch. 617 (CAA): "Such conventio~ shall be called and conducted, and delegates thereto shall be chosen in the manner provided by law." (the "~" is an OCR artifact for "n"; true reading "convention")
  - other publications: Blue Book 1973 (Art. 88): "Such convention shall be called and conducted and delegates thereto shall be chosen in the manner provided by law." — OCR drops the comma after "conducted" (poor-OCR artifact). Blue Book OCR also shows "culled"/"und" for "called"/"and" throughout (scanning artifacts, not real divergences). CAA enacted text governs and retains the comma after "conducted."

## Amendment LXXXIX (1970-10-01) — N.D. Const. § 153, N.D. Const. § 156, N.D. Const. § 159, N.D. Const. § 162
- **N.D. Const. § 153**
  - enacted (session law): Enacted CAA (1971 S.L. ch. 618) reads "common schools in this state" and uses lowercase "interest and income," "institution," "invested."
  - other publications: 1973 Blue Book (p. 334-335) substantively identical; only OCR artifacts diverge (e.g., "In this State," "Income," "Institution," "Invested" erroneously capitalized) — not genuine textual variants.
- **N.D. Const. § 156**
  - enacted (session law): Enacted CAA: "secretary of state and state auditor"; "shall be invested as provided by law."
  - other publications: 1973 Blue Book (p. 334-335) substantively identical; OCR-only divergences ("public Instruction," "Invested").

## Amendment XC (1972-10-05) — N.D. Const. § 216, N.D. Const. amend. art. LIV, subsec. 1
- **N.D. Const. § 216, Third (counties list)**
  - enacted (session law): CAA ch. 526 reads: "McHenry, Ward, Bottineau, or Rolette" (serial comma before "or")
  - other publications: bb1973 (OCR) reads: "McHenry, Ward, Bottineau or Rolette" (no serial comma)
- **N.D. Const. amend. art. LIV, subsec. 1, clause (4) (normal schools list)**
  - enacted (session law): CAA ch. 526 reads: "Valley City, Mayville, Minot, and Dickinson" (serial comma before "and")
  - other publications: bb1973 (OCR) reads: "Valley City, Muyville, Minot and Dickinson" — no serial comma; "Muyville" is an OCR artifact of "Mayville"

## Amendment XCIII (1974-12-05) — N.D. Const. § 74, N.D. Const. § 77
- **N.D. Const. § 77, enacted CAA text**
  - enacted (session law): "...he shall have no vote unless they be equally divided."
  - other publications: bb1973.txt (pre-amendment text) reads "...but shall have no vote unless they be equally divided." — but that is the OLD section 77 superseded by this amendment, not a typeset variant of the new text

## Amendment XCI (1975-07-01) — N.D. Const. § 7
- **N.D. Const. § 7**
  - enacted (session law): CAA (Chapter 532, HCR 3002, 1973), enacted/effective text: "Section 7. The right of trial by jury shall be secured to all, and remain inviolate. A person accused of a crime for which he may be confined for a period of more than one year has the right of trial by a jury of twelve. The legislative assembly may determine the size of the jury for all other cases, provided that the jury consists of at least six members. All verdicts must be unanimous."
  - other publications: Both integrated Blue Books predate the July 1, 1975 effective date and therefore print the PRE-amendment text of section 7. bb1961.txt (OCR): "Section 7. The right of trial by jury shall [be] secured to all, and remain inviolate; but a jury in civil cases, in courts not of record m[a]y consist of less than twelve men, [a]s may be prescribed by law." bb1973.txt (OCR, with scan typo "trail"): "Section 7. The right of tra[i]l by jury shall be secured to all, and remain inviolate; but a jury in civil cases. [I]n courts not of record may consist of less than twelve men, as may be prescribed by law." This is a substantive content difference (old vs. new section 7), not a punctuation/spelling drift in the same text — expected because both codes predate this amendment's effective date. No clean cross-check of the post-1975 text is available in the supplied Blue Books.

## Amendment XCII (1975-07-01) — N.D. Const. amend. art. XCII, N.D. Const. § 50
- **N.D. Const. § 50**
  - enacted (session law): CAA (1973 ch. 530, § 2): "Section 50. All sessions of the legislative assembly, including the committee of the whole and meetings of legislative committees, shall be open to the public."
  - other publications: 1961 and 1973 Blue Books still print the pre-amendment § 50 ("The sessions of each house and of the committee of the whole shall be open unless the business is such as ought to be kept secret."), because the amendment was not approved (Sept. 1974 primary) or effective (July 1, 1975) until after both compilations. No textual divergence in the amendment itself; the Blue Book simply predates integration.

## Amendment XCV (1976-10-07) — N.D. Const. § 53, N.D. Const. § 55, N.D. Const. § 56
- **N.D. Const. § 56 (pre-1976 / Blue Books)**
  - enacted (session law): Enacted CAA text (ch. 596): "Each regular session of the legislative assembly shall not exceed eighty natural days during the biennium ... a 'natural day' means a period of twenty-four consecutive hours."
  - other publications: Cross-check of /tmp/bb1973.txt and /tmp/bb1961.txt found no "eighty natural days" language; bb1973 carries the pre-amendment clause "No legislative day shall be shorter than the natural day." Both integrated codes predate this 1976 amendment, so the divergence is temporal (superseded prior text), not a publication discrepancy in the enacted text.

## Amendment XCVII (1976-10-07) — N.D. Const. § 28, N.D. Const. § 34
- **N.D. Const. § 28 (pre-amendment, prior text only)**
  - enacted (session law): Section 28. Each person elected as a senator must be, on the day of his election, a qualified elector in the district from which he is chosen and have been a resident of the state for one year next preceding his election. (CAA chapter 598, governs)
  - other publications: bb1973.txt: "Section 28. No person shall he [be] a senator who is not a qualified elector in the district in which he may be chosen, and who shall not have attained the age of twenty-five years and have been a resident of the state or territory for two years next preceding his election." This is the SUPERSEDED pre-1976 text, not a publication variant of the enacted amendment.
- **N.D. Const. § 34 (pre-amendment, prior text only)**
  - enacted (session law): Section 34. Each person elected as a representative must be, on the day of his election, a qualified elector in the district from which he is chosen and have been a resident of the state for one year next preceding his election. (CAA chapter 598, governs)
  - other publications: bb1973.txt: "Section 34. No person shall be a representative who is not a qualified elector In [in] the district from which he may be chosen, and who shall not have attained the age of twenty-one years, and have been a resident of the state or territory for two years next preceding his election." This is the SUPERSEDED pre-1976 text, not a publication variant of the enacted amendment.

## Amendment XCVIII (1976-10-07) — N.D. Const. amend. art. XCVIII, N.D. Const. § 85, N.D. Const. § 86, N.D. Const. § 87, N.D. Const. § 88, N.D. Const. § 89, N.D. Const. § 90, N.D. Const. § 91, N.D. Const. § 92, N.D. Const. § 93, N.D. Const. § 94, N.D. Const. § 95, N.D. Const. § 96, N.D. Const. § 97
- **N.D. Const. § 85**
  - enacted (session law): CAA ch. 599 (1976): "The judicial power of the state is vested in a unified judicial system consisting of a supreme court, a district court, and such other courts as may be provided by law."
  - other publications: bb1961.txt l.16210 and bb1973.txt l.19312 show the PRE-amendment section 85 ("The judicial power of the state of North Dakota shall be vested in a supreme [court]..."). These are the OLD/repealed text, not a variant of the enacted new text — both Blue Books predate the 1976 effective date, so no post-amendment integrated publication was available for variant comparison. New-text phrasing of §§95 and 97 ("conflict of interest in a pending cause", "judicial nominating committee") does not appear in either Blue Book, as expected.

## Amendment XCIX (1976-10-07) — N.D. Const. amend. art. I
- **N.D. Const. amend. art. I (lottery/gift enterprises provision)**
  - enacted (session law): CAA Chapter 600: "The legislative assembly shall not authorize any game of chance, lottery, or gift enterprises, under any pretense, or for any purpose whatever. However, the legislative assembly may authorize by law bona fide nonprofit veterans', charitable, educational, religious, or fraternal organizations, civic and service clubs, or such other public-spirited organizations as it may recognize, to conduct games of chance when the entire net proceeds of such games of chance are to be devoted to educational, charitable, patriotic, fraternal, religious, or other public-spirited uses."
  - other publications: Blue Book 1961 (line 17723-24) and Blue Book 1973 (line 20784-85) show the PRE-amendment text: "The legislative assembly shall have no power to authorize lotteries or gift enterprises for any purpose and shall pass laws to prohibit the sale of lottery or gift enterprise tickets." This is the superseded version (these editions predate the 1976 amendment), not a variant reading of the enacted text. No code with the post-amendment text was available for punctuation comparison.

## Amendment C (1978-10-05) — N.D. Const. § 214, N.D. Const. Sched. §§ 1-25
- **N.D. Const. § 214 and Sched. §§ 1-25**
  - enacted (session law): CAA ch. 691: "Section 214 and sections 1 through 25 of the transition schedule of the Constitution of the State of North Dakota are hereby repealed."
  - other publications: Blue Book 1973 (/tmp/bb1973.txt) shows § 214 already annotated as "(Superceded by legislative action. Section 54-03-01, and also by Federal District ...)" with the original text reproduced in an editorial note; this is an editorial/annotation divergence in the integrated code, not a divergence in enacted text. No section 214 hit located in /tmp/bb1961.txt on the "transition schedule" grep (OCR/coverage).

## Amendment CI (1978-10-05) — N.D. Const. § 65, N.D. Const. § 77
- **N.D. Const. § 65 (pre-amendment, as published in Blue Book 1973, p.~19104)**
  - enacted (session law): Enacted CAA text reads (in part): "No bill shall become a law: except by a vote of a majority of all the members-elect in the house of representatives, and a vote of the majority of the members-elect in the senate, however the lieutenant governor may vote as provided in section 77 in the event the senate is equally divided, nor unless, on its final passage ..."
  - other publications: Blue Book 1973 shows the PRIOR (unamended) text: "No bill shall become a law except by a vote of a majority of all [OCR: 'till'] the members-elect in each house, nor unless, on its final passage ..." This is the pre-1978 version, not a divergent reading of the same enacted text. No genuine punctuation/spelling variant of the enacted text detected.
- **N.D. Const. § 77 (pre-amendment, as published in Blue Book 1973, p.~19227, and Blue Book 1961, p.~16113)**
  - enacted (session law): Enacted CAA text reads (in part): "The powers and duties of the lieutenant governor shall be to serve as president of the senate, and he may, when the senate is equally divided, vote on procedural matters, and on substantive matters if his vote would be decisive ..."
  - other publications: Blue Books 1961 and 1973 show the PRIOR (unamended) text: "The lieutenant governor shall be president of the senate, but shall have no vote unless they be equally divided. If, during a vacancy in the office of governor ..." This is the pre-1978 version that the amendment replaced, not a divergent reading of the same enacted text.

## Amendment CVI (1980-10-02) — N.D. Const. § 174
- **Blue Book 1961 (/tmp/bb1961.txt, line 16859) and Blue Book 1973 (/tmp/bb1973.txt, line 19965)**
  - enacted (session law): Amended Section 174 reads: "The legislative assembly shall be prohibited from raising revenue to defray the expenses of the state through the levying of a tax on the assessed value of real or personal property."
  - other publications: Both Blue Books predate the 1980 amendment and print the SUPERSEDED text of Section 174: "The legislative assembly shall provide for raising revenue sufficient to defray the expenses of the state for each year, not to exceed in any one year four (4) mills on the dollar of the assessed valuation of all taxable property in the state, to be ascertained by the last assessment made for state and county purposes, and also a sufficient sum to pay the interest on the state debt." This is the language the CAA shows struck through, not a punctuation/spelling divergence in the enacted text. No post-amendment integrated code was available for cross-check.

## Amendment CVII (1980-10-02) — N.D. Const. § 173, N.D. Const. § 69
- **N.D. Const. § 173**
  - enacted (session law): CAA Chapter 655: "...sheriff, state's attorney, and a clerk of the district court... provided that in counties having population of six thousand or less the register of deeds shall also be clerk of the district court." (county judge and fifteen-thousand-population proviso struck)
  - other publications: Blue Book 1973 (pre-amendment): "...sheriff, state's attorney, county judge and a clerk of the district court... provided in counties having fifteen thousand population or less, the county judge shall also be clerk of the district court; provided further that in counties having population of six thousand or less the register of deeds shall also be clerk of the district court and county judge. This amendment shall be construed as applying to the officers elected at the general election in 1962." Divergence is substantive (this is the older text the 1980 amendment superseded), not a publication-error variant; minor Blue Book OCR artifacts: "shull lie" for "shall be," "cterk" for "clerk," "u"/"und" for "a"/"and."

## Amendment CVIII (1980-12-04) — N.D. Const. § 182
- **N.D. Const. § 182 (first sentence, mortgage security ratio)**
  - enacted (session law): Constitutional Amendments, Approved, ch. 656 (CAA 1981): "in amounts not to exceed sixty-five percent of its value" (the prior phrase "one-half" is shown struck through and replaced)
  - other publications: 1973 Blue Book integrated text (pre-amendment) reads: "in amounts not to exceed one-half of its value" — this reflects the prior section, not a publication discrepancy. (No 182 hit in /tmp/bb1961.txt.) The 1973 codification also shows OCR/typesetting differences: "state owned" (no hyphen), "enterprises or industries. In amounts" (period and capital I), and "in excess often million dollars" (OCR run-together), all attributable to OCR rather than substantive divergence.
