# ⚖️ AI Contract Review Assistant

A legal-engineering portfolio project: an AI-powered first-pass review tool
for NDAs. Upload a contract, and it checks it against a defined clause
checklist, flags missing or unusual language, explains the risk in plain
English, and drafts a suggested redline.

**Live demo:** _[add your Streamlit Cloud link here after deploying]_
**Stack:** Python, Streamlit, Anthropic API (Claude Sonnet)

---

## The problem this solves

Reviewing routine contracts like NDAs is repetitive, time-consuming, and a
common bottleneck for in-house legal teams and small firms. Junior lawyers
often spend 20-45 minutes on a first-pass NDA review that mostly involves
checking for the same handful of things every time: is confidentiality
mutual, is the term reasonable, is there a carve-out for public information,
is the non-solicit clause overly broad, etc.

This tool automates that first pass so a human reviewer can spend their time
on judgment calls instead of checklist items.

**This is explicitly a triage tool, not a legal-advice tool.** It doesn't
approve or reject contracts -- it surfaces findings for a lawyer to confirm.
That distinction is deliberate and is stated in the UI itself.

---

## How it works

1. User uploads a contract (currently `.txt`; see "Next steps" for PDF/docx).
2. The app sends the contract text to Claude along with a fixed checklist of
   8 clause types (defined in `CLAUSE_CHECKLIST` in `app.py`).
3. The model is prompted to return **structured JSON only** (not free text),
   so the output can be reliably parsed and rendered -- this is a small but
   important design choice: it makes the tool's output auditable and
   testable rather than a wall of unstructured prose.
4. Each finding includes: whether the clause is present, a risk level, a
   plain-language explanation, and a suggested redline.

---

## Evaluation (read this before you trust it)

I ran this tool against [N] real/template NDAs sourced from LawInsider and
manually reviewed the output against my own read of each contract.

| Metric | Result |
|---|---|
| Correctly flagged known issues | X / Y |
| False positives (flagged something that wasn't actually a problem) | X |
| False negatives (missed a real issue) | X |
| Clauses it never got wrong | e.g. "governing law", "mutuality" |
| Clauses where it struggled | e.g. distinguishing "reasonable" vs "unusually broad" non-solicit scope without more context |

**Fill this table in yourself** once you've run it on ~10-15 real contracts
-- this is the single most important section of the README for a legal-tech
hiring manager. It shows you understand that AI legal tools must be
evaluated for accuracy, not just shipped. Being honest about a 70-80%
hit rate with clear failure modes is far more credible than claiming
perfection.

**Known limitations:**
- Only reviews against a fixed 8-clause checklist -- it will not catch
  issues outside that list.
- No jurisdiction-specific legal knowledge -- it does not know if a clause
  is enforceable in a given state/country.
- Can hallucinate if a contract is very long or unusually formatted, since
  it relies on the model reading the full text in one pass.
- Only tested on NDAs. Would need checklist changes to work on other
  contract types (MSAs, employment agreements, etc).

---

## Running it locally

```bash
git clone <your-repo-url>
cd contract-review-assistant
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your real ANTHROPIC_API_KEY
streamlit run app.py
```

Or just paste your API key directly into the sidebar when the app opens --
useful for the deployed version where you don't want to bake in a shared key.

---

## Deploying it live (free)

1. Push this folder to a public GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, and click "New app."
3. Point it at your repo and `app.py`.
4. Do **not** put your API key in the code. Instead, users paste their own
   key into the sidebar at runtime (as this app is built to allow) -- or,
   if you want a fully working public demo, add your key under the app's
   "Secrets" settings in Streamlit Cloud and read it via
   `st.secrets["ANTHROPIC_API_KEY"]` instead of requiring user input.

---

## Next steps / how I'd extend this

- Add PDF and .docx upload support (via `pypdf` and `python-docx`).
- Expand the checklist to a second contract type (e.g. an MSA) to show the
  approach generalizes.
- Add a feedback loop: let a reviewer mark a finding as "correct" /
  "incorrect" and log it, to build a real accuracy dataset over time.
- Add clause-level citations (quote the exact contract text a finding is
  based on) to make review faster and reduce hallucination risk.

---

## Why I built this

Built as a legal-engineering portfolio project to demonstrate: prompt design
for structured/auditable AI output, an understanding of where legal AI tools
actually create value (routine first-pass review) versus where they're
risky (final legal judgment), and a habit of evaluating AI output for
accuracy rather than assuming it's correct.
