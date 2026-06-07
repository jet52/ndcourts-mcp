export const meta = {
  name: 'nd-const-amend-extract',
  description: 'Extract + verify ND constitutional amendment text from marker-OCR markdown in parallel',
  phases: [{ title: 'Extract & verify' }],
}

const REC_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    number: { type: 'string' },
    effective_date: { type: 'string' },
    election_date: { type: 'string' },
    type: { type: 'string', enum: ['amend_section', 'new_article'] },
    changes: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          target: { type: 'string', description: 'N.D. Const. § N  or  N.D. Const. amend. art. N' },
          heading: { type: 'string' },
          text: { type: 'string', description: 'verbatim amended/added provision text' },
        },
        required: ['target', 'text'],
      },
    },
    authority: { type: 'string' },
    sources_verified: { type: 'array', items: { type: 'string' } },
    code_agreement: { type: 'string' },
    discrepancies: { type: 'string' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    notes: { type: 'string' },
  },
  required: ['number', 'type', 'changes', 'confidence'],
}

// args may arrive as a JSON string; normalize.
const cfg = typeof args === 'string' ? JSON.parse(args) : args
const items = cfg.items
const markerMd = cfg.marker_md // path to the clean marker markdown of the sliced session-law pages

log(`Extracting ${items.length} amendments from ${markerMd}`)

const results = await parallel(items.map((it) => () =>
  agent(
    `Extract the VERBATIM text of ONE North Dakota constitutional amendment and verify it. Use Bash (grep/sed/cat) on local files only. Return a structured record.

AMENDMENT METADATA:
${JSON.stringify(it, null, 2)}

PRIMARY SOURCE (high-quality marker OCR of the authoritative session-law pages, all segment amendments in one file):
  ${markerMd}
Find THIS amendment within that markdown by its affected section(s) "${it.affected}" and subject "${it.subject}". The text appears as a concurrent resolution; the operative provision follows "be amended to read as follows:" (for an existing section) or the "## AMENDMENT." heading (for a new article). Extract ONLY the substantive constitutional text — exclude procedural wording ("be it resolved", "be referred to the legislative assembly", certifications, secretary-of-state attestations).

CROSS-CHECK (resolve any remaining uncertainty; confirm the wording). grep distinctive phrases in these published-code texts:
  /tmp/cl1913.txt      (1913 Compiled Laws — all amendments through 1912)
  /tmp/manual1907.txt  (1907 Legislative Manual — through 1906)
  /tmp/manual1919.txt  (1919 Legislative Manual)
If a word is still uncertain after comparing, re-OCR the relevant published-code page at high quality with:  bash /tmp/ocrpages.sh <pdf> <page> <page>
Preserve the document's actual early-1900s spelling/capitalization/punctuation — fix only OCR errors, never modernize. Record which sources you confirmed against in sources_verified.

OUTPUT the record:
- type: "amend_section" (amends existing numbered section) or "new_article" (affected = "Art. XIV").
- changes: one entry PER affected section. amend_section -> target "N.D. Const. § <N>", text = full verbatim amended section text. new_article -> target "N.D. Const. amend. art. ${it.number}", a short heading, text = the new provision. Amendment #2 affects TWO sections (121 AND 127) -> return TWO change entries.
- confidence: "high" only if the marker text and >=1 published code agree on the wording; "medium" if only one legible source; "low" if unresolved.
- authority: "Amendment ratified ${it.election_date}".
- discrepancies: any source disagreement or anything unresolved.
Return ONLY the structured record.`,
    { schema: REC_SCHEMA, label: `amd ${it.number} (§${it.affected})`, phase: 'Extract & verify' }
  )
))

return results.filter(Boolean)
