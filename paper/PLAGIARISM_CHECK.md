# Plagiarism screen (2026-11-02)

This is a self-run screen, not an iThenticate/Turnitin report. IEEE runs CrossCheck (iThenticate) on submission;
run the institution's checker before submitting if one is available.

| Check | Method | Result |
|---|---|---|
| Cited arXiv papers, abstracts | word 7-gram overlap with all 9 cited arXiv abstracts (arXiv API) | 0 of 4,619 paper 7-grams shared |
| Cited arXiv papers, full text | word 7-gram overlap with the full PDFs of the same 9 papers | 2 shared, one phrase from Kraishan (arXiv:2609.14119), "does not version tool definitions at all"; **reworded** ("keeps no versioned record of tool definitions") |
| Web | exact-phrase searches for 4 randomly sampled sentences | no match |
| Own public material (self-overlap) | 7-gram overlap with README, PREREG, STATUS, GATE, SPEC, SUGGESTIONS | 0.0–1.4% of the paper per file |

Not covered: non-arXiv references (blogs, specifications, datasets) were not compared in full; the web sample is
small. The OSF pre-registration and the public GitHub repository are the authors' own; if a venue asks about prior
publication, state that the plan was pre-registered on OSF and the code is public.
