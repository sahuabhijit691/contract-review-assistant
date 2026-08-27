"""
AI Contract Review Assistant
-----------------------------
Upload an NDA, get an AI-powered review that flags missing/unusual
clauses and suggests redlines with plain-language explanations.

Run locally:  streamlit run app.py
"""

import json
import os
import time

from google import genai
from google.genai import types
import streamlit as st
from dotenv import load_dotenv
from pypdf import PdfReader
from docx import Document

load_dotenv()

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

st.set_page_config(page_title="AI Contract Review Assistant", page_icon="⚖️", layout="wide")

# ---------------------------------------------------------------------------
# VISUAL DESIGN -- a "counsel's letterhead" aesthetic: warm ivory paper,
# deep navy for authority, aged brass for accent, a serif display face for
# the letterhead-style header. Risk colors stay functionally the same
# (red/amber/green/blue carry real meaning) but are muted to sit inside
# the palette instead of reading as generic web alert colors.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --paper: #FAF8F3;
        --paper-raised: #FFFFFF;
        --navy: #1C2B45;
        --navy-light: #2A3F5F;
        --brass: #A9814B;
        --brass-light: #C9A876;
        --forest: #3F6B52;
        --forest-dark: #345942;
        --ink: #22262B;
        --ink-muted: #6B7280;
    }

    /* Base canvas */
    .stApp {
        background-color: var(--paper);
    }
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: var(--ink);
    }
    /* Force readable ink text everywhere in the MAIN content area
       specifically (not the sidebar, which is styled separately below).
       This is a broad safety net: if the browser/Streamlit is in dark
       mode, many components default to light text, which becomes
       invisible against the white/ivory cards this design uses. Rather
       than patching each component one at a time, force it here once. */
    div[data-testid="stAppViewContainer"] > div:nth-child(1) * {
        color: var(--ink);
    }
    div[data-testid="stAppViewContainer"] > div:nth-child(1) h1,
    div[data-testid="stAppViewContainer"] > div:nth-child(1) h2,
    div[data-testid="stAppViewContainer"] > div:nth-child(1) h3 {
        color: var(--navy) !important;
    }

    /* Letterhead-style headings */
    h1, h2, h3 {
        font-family: 'Fraunces', serif !important;
        color: var(--navy) !important;
        font-weight: 500 !important;
        letter-spacing: -0.01em;
    }
    h1 {
        font-size: 2.1rem !important;
        border-bottom: 1.5px solid var(--brass);
        padding-bottom: 0.5rem;
        margin-bottom: 0.25rem !important;
    }

    /* Sidebar: deeper tone to read as the "desk" beside the "page" */
    section[data-testid="stSidebar"] {
        background-color: var(--navy);
    }
    section[data-testid="stSidebar"] * {
        color: #EDEBE4 !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #F5F0E6 !important;
        font-family: 'Fraunces', serif !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: rgba(201, 168, 118, 0.35) !important;
    }
    section[data-testid="stSidebar"] input {
        background-color: rgba(255,255,255,0.06) !important;
        color: #F5F0E6 !important;
        border: 1px solid rgba(201, 168, 118, 0.4) !important;
    }
    /* Contract type dropdown -- target broadly and force full opacity,
       since Streamlit/baseweb sometimes renders the selected value with
       reduced opacity (looks "greyed out") independent of text color. */
    section[data-testid="stSidebar"] [data-testid="stSelectbox"] div {
        background-color: rgba(255,255,255,0.08) !important;
        color: #F5F0E6 !important;
        opacity: 1 !important;
        border-color: rgba(201, 168, 118, 0.4) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSelectbox"] span {
        color: #F5F0E6 !important;
        opacity: 1 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSelectbox"] svg {
        fill: #F5F0E6 !important;
    }

    /* Primary button ("Run Review") -- deep forest green, reads as "go" */
    .stButton > button[kind="primary"] {
        background-color: var(--forest) !important;
        border: 1px solid var(--forest-dark) !important;
        color: #FAF8F3 !important;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        border-radius: 6px;
        padding: 0.55rem 1.4rem;
        transition: background-color 0.15s ease;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: var(--forest-dark) !important;
        border-color: var(--forest-dark) !important;
    }

    /* Secondary buttons -- brass-outlined, quieter */
    .stButton > button:not([kind="primary"]) {
        background-color: var(--paper-raised) !important;
        border: 1px solid var(--brass-light) !important;
        color: var(--navy) !important;
        border-radius: 6px;
        font-weight: 500;
    }
    .stButton > button:not([kind="primary"]):hover {
        border-color: var(--brass) !important;
        background-color: #FBF6EC !important;
    }

    /* Expanders (findings) styled as case-file cards */
    div[data-testid="stExpander"] {
        background-color: var(--paper-raised);
        border: 1px solid rgba(169, 129, 75, 0.25);
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(28, 43, 69, 0.05);
    }
    /* Expander BODY content (e.g. "View contract text", finding details) --
       force visible ink color on everything inside, not just the header.
       This covers the case where the browser/Streamlit is in dark mode
       and body text would otherwise default to light-on-light against
       the white card background set above. */
    div[data-testid="stExpanderDetails"],
    div[data-testid="stExpanderDetails"] * {
        color: var(--ink) !important;
        background-color: transparent;
    }
    div[data-testid="stExpanderDetails"] pre,
    div[data-testid="stExpanderDetails"] code {
        color: var(--ink) !important;
        background-color: #F7F4EC !important;
    }

    /* Redline suggestions in a legal-pad monospace */
    code, .stCodeBlock, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Alerts (info/success/warning/error) -- muted, paper-toned */
    div[data-testid="stAlert"] {
        border-radius: 8px;
        font-family: 'Inter', sans-serif;
    }

    /* File uploader as a document intake tray */
    section[data-testid="stFileUploaderDropzone"] {
        background-color: var(--paper-raised);
        border: 1.5px dashed var(--brass-light);
        border-radius: 10px;
        padding: 0.5rem;
    }
    section[data-testid="stFileUploaderDropzone"] > div,
    section[data-testid="stFileUploaderDropzone"] span,
    section[data-testid="stFileUploaderDropzone"] small,
    section[data-testid="stFileUploaderDropzone"] svg {
        color: var(--ink) !important;
        fill: var(--brass) !important;
    }
    /* "Browse files" button lives inside the dropzone and has its own
       dark background by default -- style it explicitly so it can't
       collide with the ink-colored text rule above (dark-on-dark). */
    section[data-testid="stFileUploaderDropzone"] button {
        background-color: var(--navy) !important;
        color: #FAF8F3 !important;
        border: 1px solid var(--navy) !important;
        border-radius: 6px;
        font-weight: 500;
    }
    section[data-testid="stFileUploaderDropzone"] button:hover {
        background-color: var(--navy-light) !important;
    }
    section[data-testid="stFileUploaderDropzone"] button * {
        color: #FAF8F3 !important;
    }

    /* Uploaded file entry (filename + size shown after upload) --
       explicit background + text color so it can't inherit an
       invisible combination from either the light or dark contexts. */
    [data-testid="stFileUploaderFile"],
    [data-testid="stFileUploaderFileName"] {
        background-color: var(--paper-raised) !important;
        color: var(--ink) !important;
        border-radius: 6px;
    }
    [data-testid="stFileUploaderFile"] * {
        color: var(--ink) !important;
    }

    /* Expander header ("View contract text", findings) -- force
       visible text explicitly rather than relying on inheritance. */
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary * {
        color: var(--navy) !important;
        font-weight: 500;
    }
    div[data-testid="stExpander"] summary:hover {
        color: var(--brass) !important;
    }

    /* Caption/eyebrow text */
    .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--ink-muted) !important;
    }

    /* Main content column -- contained "page" card on the ivory canvas,
       rather than content sitting flush against the browser edge. This
       is the difference between "styled Streamlit" and "a branded page." */
    div[data-testid="stAppViewContainer"] > div:nth-child(1) section.main {
        padding-top: 2rem;
    }
    .block-container {
        max-width: 900px;
        padding-top: 2.5rem !important;
        padding-bottom: 3rem !important;
    }

    /* Sidebar heading spacing */
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem !important;
    }

    /* Selectbox (Contract type) in sidebar -- ensure selected value text
       and dropdown arrow are visibly light against the navy background */
    section[data-testid="stSidebar"] [data-baseweb="select"] * {
        color: #F5F0E6 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Each contract type has its own review checklist. This is what makes the
# tool extensible rather than a single-purpose NDA demo -- adding a new
# contract type is just adding a new entry here.
CONTRACT_TYPES = {
    "NDA (Non-Disclosure Agreement)": [
        "Definition of Confidential Information",
        "Mutuality (is the NDA one-way or mutual, and is that appropriate?)",
        "Term / duration of confidentiality obligation",
        "Carve-outs (e.g. independently developed info, publicly available info)",
        "Return or destruction of confidential information",
        "Non-solicitation or non-compete language (if present, is it unusually broad?)",
        "Governing law and jurisdiction",
        "Remedies (injunctive relief clause)",
    ],
    "Employment Agreement": [
        "Job title, duties, and reporting structure",
        "Compensation, bonus structure, and equity (if any)",
        "At-will employment status vs. fixed term, and termination conditions",
        "Non-compete clause (scope, duration, geography -- is it enforceable/reasonable?)",
        "Non-solicitation of employees/clients clause",
        "Confidentiality and IP assignment (who owns work product?)",
        "Severance terms",
        "Governing law and dispute resolution (arbitration vs. litigation)",
    ],
    "MSA / Services Agreement": [
        "Scope of services and reference to Statements of Work (SOWs)",
        "Payment terms (rates, invoicing schedule, late payment penalties)",
        "Liability cap and limitation of liability clause",
        "Indemnification (who indemnifies whom, and for what)",
        "Intellectual property ownership of deliverables",
        "Termination rights and notice period",
        "Confidentiality obligations",
        "Warranties and disclaimers",
        "Governing law and dispute resolution",
    ],
    "Consulting / Independent Contractor Agreement": [
        "Independent contractor status (language guarding against misclassification as employee)",
        "Scope of work and deliverables",
        "Payment terms and invoicing",
        "IP ownership / work-for-hire language",
        "Confidentiality obligations",
        "Non-compete or non-solicitation (is it appropriate for a contractor relationship?)",
        "Termination rights",
        "Indemnification and liability limits",
    ],
    "SaaS / Software License Agreement": [
        "License grant scope (users, seats, permitted use)",
        "Data ownership and data processing / privacy terms",
        "Service Level Agreement (SLA) / uptime commitments",
        "Limitation of liability and liability cap",
        "Indemnification (especially IP infringement indemnity)",
        "Termination and data return/deletion upon termination",
        "Auto-renewal and price increase terms",
        "Governing law and dispute resolution",
    ],
    "Vendor / Supplier Agreement": [
        "Scope of goods/services and delivery terms",
        "Pricing, payment terms, and price change provisions",
        "Warranties on goods/services provided",
        "Limitation of liability and indemnification",
        "Termination rights and notice period",
        "Force majeure clause",
        "Confidentiality obligations",
        "Governing law and dispute resolution",
    ],
    "Commercial Lease Agreement": [
        "Rent amount, escalation clauses, and payment terms",
        "Lease term and renewal/termination options",
        "Permitted use of premises",
        "Maintenance and repair responsibilities (landlord vs. tenant)",
        "Assignment and subletting rights",
        "Insurance requirements",
        "Default and remedies clause",
        "Governing law and jurisdiction",
    ],
    "Sales / Purchase Agreement": [
        "Description of goods/assets being sold and purchase price",
        "Payment terms and conditions precedent to closing",
        "Representations and warranties of both parties",
        "Indemnification provisions",
        "Limitation of liability",
        "Conditions for termination of the agreement",
        "Governing law and dispute resolution",
    ],
    "Partnership / Joint Venture Agreement": [
        "Capital contributions of each party",
        "Profit and loss allocation",
        "Management and decision-making authority",
        "Non-compete obligations between partners",
        "Exit provisions / buyout terms",
        "Dispute resolution mechanism between partners",
        "Governing law and jurisdiction",
    ],
    "M&A Agreement (Asset/Stock Purchase or Merger)": [
        "Purchase price and adjustment mechanisms (working capital, earnouts)",
        "Representations and warranties (scope, and survival period post-closing)",
        "Indemnification (caps, baskets/deductibles, survival period)",
        "Conditions precedent to closing",
        "Material Adverse Change (MAC) / Material Adverse Effect (MAE) clause",
        "Non-compete and non-solicitation covenants on the seller",
        "Termination rights and break-up fee (if any)",
        "Governing law and dispute resolution",
    ],
}

RISK_COLORS = {"high": "🔴", "medium": "🟡", "low": "🟢", "info": "🔵"}


def extract_text(uploaded_file) -> str:
    """Pull plain text out of a .txt, .pdf, or .docx upload."""
    name = uploaded_file.name.lower()

    if name.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="ignore")

    if name.endswith(".pdf"):
        reader = PdfReader(uploaded_file)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)

    if name.endswith(".docx"):
        document = Document(uploaded_file)
        paragraphs = [p.text for p in document.paragraphs]
        return "\n".join(paragraphs)

    raise ValueError(f"Unsupported file type: {name}")

SYSTEM_PROMPT = """You are a contract review assistant helping a legal team quickly \
triage a contract. You are NOT providing legal advice -- you are flagging items \
for a human lawyer to review.

For each clause in the checklist provided, determine:
1. Is it present in the contract? (yes/no/partial)
2. If present, is the language standard/market, or unusual in a way that \
creates risk for one of the parties?
3. A short, plain-language explanation (2-3 sentences max) of WHY it matters.
4. If there's an issue, a specific suggested redline (the actual replacement \
or added language), or "N/A" if no issue.
5. A risk level: "high", "medium", "low", or "info" (info = present and fine).

Ground every finding in the actual contract text. If a clause is simply \
absent, say so plainly rather than inferring intent.

Respond with ONLY valid JSON (no markdown fences, no preamble), in this exact shape:

{
  "overall_summary": "2-3 sentence plain-language summary of the contract's overall risk profile",
  "findings": [
    {
      "clause": "string - name of the clause from the checklist",
      "present": "yes | no | partial",
      "risk_level": "high | medium | low | info",
      "explanation": "string",
      "suggested_redline": "string or 'N/A'"
    }
  ]
}
"""


def review_contract(api_key: str, contract_text: str, checklist: list) -> dict:
    """Send the contract to Gemini and get back structured findings."""
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=90000))

    checklist_str = "\n".join(f"- {item}" for item in checklist)

    user_message = f"""Checklist to review against:
{checklist_str}

Contract text to review:
\"\"\"
{contract_text}
\"\"\"
"""

    # Google renames/retires model aliases periodically, so try a few
    # known-good options in order rather than hardcoding just one.
    candidate_models = [
        "gemini-3.6-flash",
        "gemini-2.5-flash",
        "gemini-flash-latest",
    ]

    last_error = None
    for model_name in candidate_models:
        # Retry each candidate model a couple of times before moving on --
        # 503 "high demand" errors are common and usually resolve within
        # a few seconds, so a quick retry avoids surfacing a scary error
        # for what is often a temporary blip.
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        max_output_tokens=4000,
                        temperature=0.2,
                    ),
                )
                raw_text = response.text.strip()
                raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                return json.loads(raw_text)
            except Exception as e:
                last_error = e
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    time.sleep(3)
                    continue
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    # Rate limit -- a short automatic wait then one retry
                    # often succeeds once the per-minute quota window rolls over.
                    time.sleep(15)
                    continue
                break  # other error: don't bother retrying this model

    # If every candidate model failed, surface the last real error
    raise last_error


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div style="font-family:'Inter',sans-serif; letter-spacing:0.14em; text-transform:uppercase;
                font-size:0.72rem; color:#A9814B; font-weight:600; margin-top:1.25rem; margin-bottom:0.4rem;">
        Legal Engineering &nbsp;·&nbsp; First-Pass Review
    </div>
    """,
    unsafe_allow_html=True,
)
st.title("⚖ Contract Review Assistant")
st.caption(
    "Upload a contract and get an AI-drafted first-pass review: missing clauses, "
    "unusual language, and suggested redlines. Pick the contract type in the "
    "sidebar first -- this is a triage tool, not legal advice; every finding "
    "should be checked by a human lawyer."
)

with st.sidebar:
    st.header("Setup")

    # On the deployed version, a shared key lives in Streamlit's Secrets so
    # visitors don't need their own -- gated by a small per-session limit so
    # the free-tier quota can't be drained by casual traffic. Locally, this
    # secret won't exist, so it falls back to asking for a personal key.
    try:
        shared_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        shared_key = None

    MAX_FREE_REVIEWS_PER_SESSION = 3
    if "reviews_used" not in st.session_state:
        st.session_state.reviews_used = 0

    if shared_key:
        remaining = MAX_FREE_REVIEWS_PER_SESSION - st.session_state.reviews_used
        st.success(f"No API key needed -- {remaining} free review(s) left this session.")
        own_key_input = st.text_input(
            "Or use your own Gemini API key (unlimited)",
            value="",
            type="password",
            help="Optional. Get a free key at aistudio.google.com/apikey.",
        )
        st.caption("Optional -- get a free key at aistudio.google.com/apikey")
        api_key_input = own_key_input if own_key_input else shared_key
        using_shared_key = not own_key_input
    else:
        api_key_input = st.text_input(
            "Google Gemini API Key",
            value=os.getenv("GEMINI_API_KEY", ""),
            type="password",
            help="Get a free key at aistudio.google.com/apikey. Stored only for this session.",
        )
        st.caption("Get a free key at aistudio.google.com/apikey -- stored only for this session.")
        using_shared_key = False

    st.divider()
    contract_type = st.selectbox(
        "Contract type",
        options=list(CONTRACT_TYPES.keys()),
        help="Choosing the right type loads the correct clause checklist for review.",
    )
    st.subheader("What this tool checks")
    for item in CONTRACT_TYPES[contract_type]:
        st.markdown(f"- {item}")
    if contract_type == "M&A Agreement (Asset/Stock Purchase or Merger)":
        st.warning(
            "M&A agreements are typically long, heavily negotiated, and reviewed "
            "by deal teams over weeks -- this is a high-level first-pass check on "
            "core protective clauses only, not a substitute for full diligence.",
            icon="⚠️",
        )
    st.divider()
    st.subheader("Risk level key")
    st.markdown(
        "🔴 **High** -- significant issue, needs redlining\n\n"
        "🟡 **Medium** -- worth a closer look\n\n"
        "🟢 **Low** -- minor or standard variation\n\n"
        "🔵 **Info** -- present and looks fine"
    )
    st.divider()
    st.caption(
        "Built as a legal-engineering portfolio project. "
        "See README for the evaluation methodology and known limitations."
    )

uploaded_file = st.file_uploader(
    "Upload a contract (.txt, .pdf, or .docx)",
    type=["txt", "pdf", "docx"],
)

sample_button = st.button("Or try it on the included sample NDA")
if sample_button and contract_type != "NDA (Non-Disclosure Agreement)":
    st.info(
        "Note: the sample document is an NDA. Switch 'Contract type' in the "
        "sidebar to 'NDA (Non-Disclosure Agreement)' to review it with the "
        "matching checklist."
    )

# Use session_state so the loaded contract "sticks" across reruns
# (e.g. after clicking Run Review), instead of resetting to nothing.
if "contract_text" not in st.session_state:
    st.session_state.contract_text = None

if uploaded_file is not None:
    try:
        st.session_state.contract_text = extract_text(uploaded_file)
        st.session_state.last_result = None  # clear stale results from a previous contract
    except Exception as e:
        st.error(f"Couldn't read that file: {e}")
elif sample_button:
    sample_path = os.path.join(os.path.dirname(__file__), "sample_nda.txt")
    with open(sample_path, "r") as f:
        st.session_state.contract_text = f.read()
    st.session_state.last_result = None  # clear stale results from a previous contract

contract_text = st.session_state.contract_text

if "last_result" not in st.session_state:
    st.session_state.last_result = None

if contract_text:
    with st.expander("View contract text"):
        st.text(contract_text)

    if st.button("Run Review", type="primary"):
        if not api_key_input:
            st.error("Please enter your Google Gemini API key in the sidebar first.")
        elif using_shared_key and st.session_state.reviews_used >= MAX_FREE_REVIEWS_PER_SESSION:
            st.error(
                f"You've used all {MAX_FREE_REVIEWS_PER_SESSION} free reviews for this "
                "session. Paste your own free Gemini API key in the sidebar "
                "(aistudio.google.com/apikey) to keep going with no limit."
            )
        else:
            with st.spinner("Reviewing contract... this can take up to a minute for longer documents."):
                try:
                    result = review_contract(api_key_input, contract_text, CONTRACT_TYPES[contract_type])
                except json.JSONDecodeError:
                    st.error(
                        "The model's response couldn't be parsed as JSON. "
                        "This happens occasionally -- try running again."
                    )
                    st.stop()
                except Exception as e:
                    if "503" in str(e) or "UNAVAILABLE" in str(e):
                        st.error(
                            "Google's Gemini API is temporarily overloaded (this is on "
                            "their end, not this app). Please wait a moment and click "
                            "'Run Review' again."
                        )
                    elif "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        st.error(
                            "The free-tier Gemini quota has been hit for the moment "
                            "(this resets quickly, usually within a minute). Please "
                            "wait ~30-60 seconds and click 'Run Review' again -- or "
                            "paste your own free Gemini key in the sidebar to use a "
                            "separate quota."
                        )
                    else:
                        st.error(f"Something went wrong: {e}")
                    st.stop()

            if using_shared_key:
                st.session_state.reviews_used += 1

            # Store the result and rerun so the sidebar's "reviews left"
            # count updates immediately, rather than lagging one click behind.
            st.session_state.last_result = result
            st.rerun()

    # Render the most recent result, if any -- this runs on every page
    # load/rerun, which is what lets the sidebar count and the results
    # stay in sync immediately after clicking Run Review.
    result = st.session_state.last_result
    if result:
        st.subheader("Summary")
        st.info(result.get("overall_summary", "No summary returned."))

        st.subheader("Clause-by-Clause Findings")
        st.caption("🔴 High risk &nbsp;·&nbsp; 🟡 Medium risk &nbsp;·&nbsp; 🟢 Low risk &nbsp;·&nbsp; 🔵 Info / looks fine")
        for finding in result.get("findings", []):
            risk = finding.get("risk_level", "info")
            icon = RISK_COLORS.get(risk, "⚪")
            with st.expander(f"{icon} {finding.get('clause', 'Unknown clause')}  —  {risk.upper()}"):
                st.markdown(f"**Present in contract:** {finding.get('present', 'unknown')}")
                st.markdown(f"**Why it matters:** {finding.get('explanation', '')}")
                redline = finding.get("suggested_redline", "N/A")
                if redline and redline != "N/A":
                    st.markdown("**Suggested redline:**")
                    st.code(redline, language="text")
                else:
                    st.markdown("**Suggested redline:** N/A")

        st.divider()
        st.caption(
            "⚠️ This is an AI-generated first-pass review for triage purposes only. "
            "It is not legal advice and may contain errors or omissions. "
            "A qualified lawyer should review the contract before relying on it."
        )
else:
    st.info("Upload a .txt contract file, or click the sample button above to try it out.")