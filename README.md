# ⚖️ AI Contract Review Assistant

A legal-engineering portfolio project: an AI-powered first-pass review tool
that checks contracts against a type-specific clause checklist, flags
missing or unusual language, explains the risk in plain English, and
drafts a suggested redline.

**Live demo:** _[add your Streamlit Cloud link here after deploying]_
**Stack:** Python, Streamlit, Google Gemini API

---

## Supported contract types

The tool covers 10 of the most commonly reviewed contract types, each with
its own tailored clause checklist (defined in `CONTRACT_TYPES` in `app.py`):

1. NDA (Non-Disclosure Agreement)
2. Employment Agreement
3. MSA / Services Agreement
4. Consulting / Independent Contractor Agreement
5. SaaS / Software License Agreement
6. Vendor / Supplier Agreement
7. Commercial Lease Agreement
8. Sales / Purchase Agreement
9. Partnership / Joint Venture Agreement
10. M&A Agreement (Asset/Stock Purchase or Merger)

Adding an 11th contract type is a single dictionary entry in `app.py` --
the checklist-driven design was a deliberate choice to keep the tool
extensible rather than hardcoded to one contract type.

**Note on M&A specifically:** real M&A agreements are long, heavily
negotiated documents typically reviewed by deal teams over weeks. This
tool's M&A checklist is a high-level first-pass check on core protective
clauses only -- not a substitute for full diligence. The app surfaces this
caveat directly in the UI when that contract type is selected.

Accepted upload formats: **.txt, .pdf, .docx**

---

## The problem this solves

Reviewing routine contracts is repetitive, time-consuming, and a common
bottleneck for in-house legal teams and small firms. A first-pass review
often involves checking for the same handful of things every time per
contract type -- is there a liability cap in an MSA, is a non-compete
reasonable in an employment agreement, is there a carve-out clause in an
NDA, and so on.

This tool automates that first pass so a human reviewer can spend their
time on judgment calls instead of checklist items.

**This is explicitly a triage tool, not a legal-advice tool.** It doesn't
approve or reject contracts -- it surfaces findings for a lawyer to
confirm. That distinction is deliberate and is stated in the UI itself.

---

## How it works

1. User selects a contract type from the sidebar, and uploads a contract
   (.txt, .pdf, or .docx).
2. The app extracts plain text from the file (via `pypdf` for PDFs and
   `python-docx` for Word docs).
3. The app sends the contract text to Gemini along with the checklist
   matching the selected contract type.
4. The model is prompted to return **structured JSON only** (not free
   text), so the output can be reliably parsed and rendered -- this is a
   small but important design choice: it makes the tool's output auditable
   and testable rather than a wall of unstructured prose.
5. Each finding includes: whether the clause is present, a risk level, a
   plain-language explanation, and a suggested redline.

---

## Evaluation (read this before you trust it)

I ran this tool against [N] real/template contracts sourced from
LawInsider, across [list contract types tested], and manually reviewed the
output against my own read of each contract.

| Contract type | Docs tested | Correctly flagged known issues | False positives | False negatives |
|---|---|---|---|---|
| NDA | X | X / Y | X | X |
| Employment Agreement | X | X / Y | X | X |
| MSA / Services Agreement | X | X / Y | X | X |

**Fill this table in yourself** once you've run it on real contracts across
a few of the 10 supported types -- this is the single most important
section of the README for a legal-tech hiring manager. It shows you
understand that AI legal tools must be evaluated for accuracy, not just
shipped. Being honest about a 70-80% hit rate with clear failure modes is
far more credible than claiming perfection.

**Known limitations:**
- Only reviews against each contract type's fixed checklist -- it will not
  catch issues outside that list.
- No jurisdiction-specific legal knowledge -- it does not know if a clause
  is enforceable in a given state/country.
- Can hallucinate if a contract is very long or unusually formatted, since
  it relies on the model reading the full text in one pass.
- M&A checklist is intentionally high-level -- see note above.
- Free-tier Gemini API usage is rate-limited; heavy testing may hit limits.

---

## Running it locally

```bash
git clone https://github.com/sahuabhijit691/contract-review-assistant.git
cd contract-review-assistant
pip3 install -r requirements.txt
streamlit run app.py
```

Get a **free** Gemini API key at
[aistudio.google.com/apikey](https://aistudio.google.com/apikey) -- no
credit card required. Paste it into the sidebar when the app opens.

---

## Deploying it live (free)

1. Push this folder to a public GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, and click "New app."
3. Point it at your repo and `app.py`.
4. Leave "Secrets" empty -- this app is designed so each visitor pastes
   their own free Gemini key into the sidebar at runtime, so no shared key
   or billing risk lives on the deployed app.

---

## Next steps / how I'd extend this

- Add a feedback loop: let a reviewer mark a finding as "correct" /
  "incorrect" and log it, to build a real accuracy dataset over time.
- Add clause-level citations (quote the exact contract text a finding is
  based on) to make review faster and reduce hallucination risk.
- Add jurisdiction-aware review (e.g. flag non-compete clauses that are
  unenforceable in states like California).
- Support side-by-side redline comparison (original vs. suggested).

---

## Why I built this

Built as a legal-engineering portfolio project to demonstrate: prompt
design for structured/auditable AI output, a checklist-driven architecture
that generalizes across 10 contract types instead of one, an understanding
of where legal AI tools actually create value (routine first-pass review)
versus where they're risky (final legal judgment on complex documents like
M&A agreements), and a habit of evaluating AI output for accuracy rather
than assuming it's correct.