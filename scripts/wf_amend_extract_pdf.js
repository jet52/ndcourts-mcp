export const meta = {
  name: 'nd-const-amend-extract-pdf',
  description: 'Extract + verify ND constitutional amendment text from clean per-session CAA PDFs in parallel',
  phases: [{ title: 'Extract & verify' }],
}

const REC_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    number: { type: 'string' }, effective_date: { type: 'string' },
    type: { type: 'string', enum: ['amend_section', 'new_article', 'repeal'] },
    changes: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          target: { type: 'string' }, heading: { type: 'string' },
          text: { type: 'string' },
          action: { type: 'string', enum: ['amend', 'add', 'repeal'] },
        },
        required: ['target', 'text'],
      },
    },
    authority: { type: 'string' },
    sources_verified: { type: 'array', items: { type: 'string' } },
    variants: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          location: { type: 'string' }, enacted_session_law: { type: 'string' },
          other_publications: { type: 'string' },
        },
        required: ['location', 'enacted_session_law', 'other_publications'],
      },
    },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    discrepancies: { type: 'string' }, notes: { type: 'string' },
  },
  required: ['number', 'type', 'changes', 'confidence'],
}

const cfg = typeof args === 'string' ? JSON.parse(args) : args
const items = cfg.items
log(`Extracting ${items.length} amendments from clean per-session CAA PDFs`)

const results = await parallel(items.map((it) => () =>
  agent(
    `Extract the VERBATIM text of ONE North Dakota constitutional amendment from its dedicated, clean session PDF and return a structured record. Use Bash (pdftotext, grep).

AMENDMENT METADATA:
${JSON.stringify(it, null, 2)}

PRIMARY SOURCE (clean modern typeset — the enacted "Constitutional Amendments Approved" for that session):
  pdftotext -layout ${it.source_pdf} -   (small file; read it all)
Find THIS amendment by its affected section(s) "${it.affected}" and subject "${it.subject}". Each amendment reads like: "SECTION 1. AMENDMENT.) Section <N> of the Constitution ... is amended to read as follows: <TEXT>" (or "...is created and enacted ..." for a NEW section/article, or "...is repealed"). Extract ONLY the substantive constitutional text that follows "to read as follows:" — exclude the enacting/procedural wrapper ("BE IT ENACTED", resolution numbers, "SECTION 1. AMENDMENT.)").

DETERMINE the operation:
- amend_section: amends an existing numbered section -> target "N.D. Const. § <N>", action "amend".
- new_article: creates/adds a new provision -> target "N.D. Const. amend. art. ${it.number}", action "add".
- If it REPEALS a section, set type "repeal", action "repeal", text "[Repealed effective ${it.effective_date}]".
- If it touches multiple sections (affected lists several, e.g. "${it.affected}"), return one change entry per section.

CROSS-CHECK for variant detection (the CAA text is clean and authoritative; codes may differ): grep the section in the integrated Blue Books /tmp/bb1961.txt and /tmp/bb1973.txt (poor OCR, gross check only). Record any punctuation/capitalization/spelling divergence in "variants" (location, enacted_session_law reading, other_publications). The enacted CAA text governs and goes in "text"; preserve its spelling/capitalization/punctuation verbatim. Do NOT modernize.

confidence "high" if the CAA text is clean and unambiguous. Return ONLY the record.`,
    { schema: REC_SCHEMA, label: `amd ${it.number} (§${it.affected})`, phase: 'Extract & verify' }
  )
))

return results.filter(Boolean)
