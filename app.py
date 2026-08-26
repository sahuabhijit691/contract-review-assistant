"""
AI Contract Review Assistant
-----------------------------
Upload an NDA, get an AI-powered review that flags missing/unusual
clauses and suggests redlines with plain-language explanations.

Run locally:  streamlit run app.py
"""

import json
import os

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
            continue

    # If every candidate model failed, surface the last real error
    raise last_error


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("⚖️ AI Contract Review Assistant")
st.caption(
    "Upload a contract and get an AI-drafted first-pass review: missing clauses, "
    "unusual language, and suggested redlines. Pick the contract type in the "
    "sidebar first -- this is a triage tool, not legal advice; every finding "
    "should be checked by a human lawyer."
)

with st.sidebar:
    st.header("Setup")
    api_key_input = st.text_input(
        "Google Gemini API Key",
        value=os.getenv("GEMINI_API_KEY", ""),
        type="password",
        help="Get a free key at aistudio.google.com/apikey. Stored only for this session.",
    )
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
    except Exception as e:
        st.error(f"Couldn't read that file: {e}")
elif sample_button:
    sample_path = os.path.join(os.path.dirname(__file__), "sample_nda.txt")
    with open(sample_path, "r") as f:
        st.session_state.contract_text = f.read()

contract_text = st.session_state.contract_text

if contract_text:
    with st.expander("View contract text"):
        st.text(contract_text)

    if st.button("Run Review", type="primary"):
        if not api_key_input:
            st.error("Please enter your Google Gemini API key in the sidebar first.")
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
                    st.error(f"Something went wrong: {e}")
                    st.stop()

            st.subheader("Summary")
            st.info(result.get("overall_summary", "No summary returned."))

            st.subheader("Clause-by-Clause Findings")
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