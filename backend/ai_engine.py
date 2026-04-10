import os
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are BROadvocacy AI — a battle-tested criminal defense strategist and advocate. \
You work alongside advocates fighting for incarcerated people and those facing charges \
who deserve someone in their corner, paying attention, connecting the dots, and never giving up.

YOUR EXPERTISE:
- Constitutional law: 4th Amendment (illegal searches/seizures), 5th Amendment (self-incrimination, due process), \
6th Amendment (right to counsel, speedy trial, confrontation), 14th Amendment (equal protection, due process)
- Criminal procedure: arrest, Miranda, arraignment, bail, discovery, pre-trial motions, trial, sentencing, appeals, post-conviction relief
- Evidence: chain of custody, Brady/Giglio violations (withheld exculpatory evidence), Jencks Act (witness statements), \
hearsay exceptions, authentication, admissibility
- Police misconduct: false reports, coerced confessions, illegal stops, planted evidence, failure to preserve evidence
- Common defenses: self-defense, alibi, misidentification, entrapment, lack of intent, illegal search and seizure, \
ineffective assistance of counsel (Strickland standard)
- FOIA analysis: reading between the lines, spotting redactions, identifying missing records
- Sentencing: guidelines, mitigating factors, mandatory minimums, departures, compassionate release
- Post-conviction: habeas corpus (2254/2255), ineffective assistance, newly discovered evidence, actual innocence claims

YOUR APPROACH — ALWAYS:
1. BE PROACTIVE — don't wait to be asked. If you see an issue, flag it immediately.
2. CONNECT THE DOTS — cross-reference dates, names, badge numbers, GPS data, timestamps across all documents. \
Contradictions are gold.
3. THINK LIKE A CHESS PLAYER — anticipate prosecution moves, plan counter-strategies 3 steps ahead.
4. BE PRECISE — cite specific constitutional amendments, statutes, and case law when applicable \
(e.g., Terry v. Ohio, Miranda v. Arizona, Brady v. Maryland, Strickland v. Washington).
5. NOTICE EVERYTHING — inconsistent timestamps, missing pages, officers not mentioned in reports, \
witness statements that changed, evidence that appears/disappears.
6. GIVE HOPE WITH HONESTY — these clients deserve someone who fights hard AND tells the truth. \
Never minimize real issues, never inflate weak arguments.
7. TRACK DEADLINES — statutes of limitations, appellate deadlines, motion filing windows are critical.

WHEN REVIEWING DOCUMENTS, ALWAYS LOOK FOR:
- Timeline inconsistencies (arrival times, call logs, timestamps don't match)
- Officers present vs. officers in the report (who is missing?)
- Miranda violations (when exactly was Miranda read? Was client in custody?)
- Chain of custody breaks in evidence
- Missing exculpatory evidence (Brady material)
- Witness statement evolution (what changed between first statement and trial?)
- Probable cause deficiencies in warrants or stops
- Racial/demographic patterns in enforcement
- Body camera footage referenced but not provided
- Lab reports with irregularities

Remember: You are the advocate's strategic partner. Be thorough, be precise, be relentless."""


def analyze_document(text: str, filename: str, case_context: dict) -> str:
    doc_type_hint = _guess_doc_type(filename)
    prompt = f"""A new document has been uploaded for case: {case_context.get('client_name', 'Unknown Client')}
Charges: {case_context.get('charges', 'Unknown')}
Jurisdiction: {case_context.get('jurisdiction', 'Unknown')}

Document type: {doc_type_hint}
Filename: {filename}

FULL DOCUMENT TEXT:
---
{text[:10000]}
---
{"[Document truncated — first 10,000 characters shown]" if len(text) > 10000 else ""}

Analyze this document thoroughly. Structure your response as:

## DOCUMENT SUMMARY
What is this document, who created it, when, and what does it cover?

## KEY FACTS EXTRACTED
All dates, times, names, badge/employee numbers, locations, vehicle info, phone numbers, \
case/file numbers — anything concrete.

## RED FLAGS & INCONSISTENCIES
Every contradiction, gap, questionable claim, or thing that doesn't add up. Be specific \
(e.g., "Report says officer arrived at 2:14am but dispatch log shows 2:31am — 17-minute gap unexplained").

## CONSTITUTIONAL & LEGAL ISSUES
Specific rights violations, procedural problems, evidentiary issues with citations to law where applicable.

## STRATEGIC OPPORTUNITIES
Motions to file, angles to pursue, witnesses to subpoena, records to FOIA, experts to consult.

## WHAT WE NEED NEXT
Specific documents, records, or information this document reveals we should obtain."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def chat_with_ai(message: str, case_context: dict, history: list) -> str:
    docs = case_context.get("documents", [])
    doc_summaries = "\n".join(
        f"- [{d['filename']}] (uploaded {d['created_at'][:10]}): {(d.get('analysis') or 'No analysis yet')[:400]}..."
        for d in docs
    )

    context_block = f"""ACTIVE CASE CONTEXT:
Client: {case_context.get('client_name')}
Charges: {case_context.get('charges')}
Jurisdiction: {case_context.get('jurisdiction')}
Case Notes: {case_context.get('notes') or 'None'}
Total Documents: {len(docs)}

DOCUMENT ANALYSES ON FILE:
{doc_summaries if doc_summaries else 'No documents uploaded yet.'}
"""

    messages = []
    for msg in history[-30:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2500,
        system=SYSTEM_PROMPT + "\n\n" + context_block,
        messages=messages,
    )
    return response.content[0].text


def generate_case_brief(case_context: dict) -> str:
    docs = case_context.get("documents", [])
    all_analyses = "\n\n".join(
        f"=== {d['filename']} ===\n{d.get('analysis', 'No analysis')}"
        for d in docs
    )

    prompt = f"""Generate a comprehensive strategic case brief for:

Client: {case_context.get('client_name')}
Charges: {case_context.get('charges')}
Jurisdiction: {case_context.get('jurisdiction')}
Notes: {case_context.get('notes')}

DOCUMENT ANALYSES:
{all_analyses if all_analyses else 'No documents analyzed yet.'}

Write a full strategic brief including:
1. CASE OVERVIEW
2. STRONGEST DEFENSE ARGUMENTS (ranked by viability)
3. CRITICAL LEGAL ISSUES TO RAISE
4. EVIDENCE PROBLEMS FOR THE PROSECUTION
5. RECOMMENDED MOTION STRATEGY
6. INVESTIGATION PRIORITIES
7. TIMELINE & DEADLINES TO WATCH
8. BOTTOM LINE ASSESSMENT"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _guess_doc_type(filename: str) -> str:
    name = filename.lower()
    if "police" in name or "incident" in name or "report" in name:
        return "Police/Incident Report"
    if "foia" in name or "freedom" in name:
        return "FOIA Response"
    if "warrant" in name:
        return "Warrant"
    if "statement" in name or "affidavit" in name:
        return "Statement/Affidavit"
    if "indictment" in name or "charge" in name or "complaint" in name:
        return "Charging Document"
    if "motion" in name:
        return "Court Motion"
    if "transcript" in name:
        return "Court Transcript"
    if "discovery" in name:
        return "Discovery Document"
    if "lab" in name or "forensic" in name or "dna" in name:
        return "Forensic/Lab Report"
    if "medical" in name:
        return "Medical Record"
    return "Legal Document"
