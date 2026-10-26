"""Verdict synthesis and merging logic for Satyavani AI.

Enforces strict verification rules:
- Published fact-check rating of False/Misleading outranks LLM judge output and sets CONTRADICTED.
- A VERIFIED verdict requires evidence from at least 2 distinct outlets; downgraded to PARTIAL if < 2.
- Permitted verdicts ONLY: VERIFIED, PARTIAL, CONTRADICTED, UNVERIFIED.
- UNVERIFIED reasons must always explain that lack of evidence does not prove falsehood.
"""
from typing import List, Dict, Any, Tuple
from backend.schemas.chat import VerdictType, ConfidenceType, SourceItem


FALSE_RATINGS = {
    "false", "fake", "misleading", "incorrect", "debunked", "pants on fire",
    "mostly false", "manipulated", "altered", "distorted"
}

TRUE_RATINGS = {
    "true", "correct", "accurate", "verified", "mostly true"
}


def merge_verdict(
    judge_verdict: str,
    judge_reason: str,
    judge_confidence: str,
    supporting_chunk_ids: List[int],
    evidence_items: List[Dict[str, Any]],
    fact_check_results: List[Dict[str, Any]],
    user_language: str = "en",
) -> Tuple[str, str, str, List[SourceItem]]:
    """Synthesize the final verdict, confidence, reason, and source citations."""
    final_verdict = judge_verdict.strip().upper()
    final_confidence = judge_confidence.strip().lower()
    final_reason = judge_reason.strip()

    # Rule 1: Check for authoritative published fact-check ratings that outrank LLM
    contradicting_fact_check = None
    for fc in fact_check_results:
        rating_str = fc.get("rating", "").strip().lower()
        if any(f_word in rating_str for f_word in FALSE_RATINGS):
            contradicting_fact_check = fc
            break

    if contradicting_fact_check:
        final_verdict = VerdictType.CONTRADICTED.value
        final_confidence = ConfidenceType.HIGH.value
        publisher = contradicting_fact_check.get("publisher", "Published Fact-Check")
        rating = contradicting_fact_check.get("rating", "False")
        if user_language == "hi":
            final_reason = f"{publisher} की फैक्ट-चेक रिपोर्ट में इस दावे को '{rating}' बताया गया है।"
        elif user_language == "te":
            final_reason = f"{publisher} ఫ్యాక్ట్-చెక్ నివేదిక ఈ వాదనను '{rating}' గా నిర్ధారించింది."
        else:
            final_reason = f"{publisher} fact-check verified this claim as '{rating}'."

    # Rule 2: If verdict is VERIFIED, verify that at least 2 distinct outlets support it
    if final_verdict == VerdictType.VERIFIED.value:
        supporting_outlets = set()
        # Look up outlets of supporting chunks
        for item in evidence_items:
            chunk_id = item.get("id")
            if chunk_id in supporting_chunk_ids or not supporting_chunk_ids:
                source_name = item.get("source", "").strip()
                if source_name:
                    supporting_outlets.add(source_name)

        if len(supporting_outlets) < 2:
            final_verdict = VerdictType.PARTIAL.value
            if final_confidence == ConfidenceType.HIGH.value:
                final_confidence = ConfidenceType.MEDIUM.value
            note = " (Downgraded to PARTIAL because only one outlet supports this claim)."
            if note not in final_reason and user_language == "en":
                final_reason += note

    # Rule 3: Guarantee allowed verdicts
    if final_verdict not in [v.value for v in VerdictType]:
        final_verdict = VerdictType.UNVERIFIED.value

    # Rule 4: Ensure UNVERIFIED includes mandatory absence-of-evidence explanation
    if final_verdict == VerdictType.UNVERIFIED.value:
        if not final_confidence or final_confidence not in [c.value for c in ConfidenceType]:
            final_confidence = ConfidenceType.LOW.value
        absence_disclaimer = {
            "en": "Absence of evidence does not prove the claim is false; it may be very new or very local.",
            "hi": "साक्ष्य की अनुपस्थिति यह साबित नहीं करती कि दावा झूठा है; यह बहुत नया या स्थानीय हो सकता है।",
            "te": "ఆధారాలు లభించకపోవడం వలన ఈ వాదన అసత్యమని చెప్పలేము; ఇది చాలా తాజాది లేదా స్థానికమైనది కావచ్చు."
        }
        disclaimer = absence_disclaimer.get(user_language, absence_disclaimer["en"])
        if disclaimer not in final_reason:
            final_reason = f"{final_reason} {disclaimer}".strip()

    # Rule 5: Format source items
    sources: List[SourceItem] = []
    seen_links = set()

    # Add fact-check sources first if applicable
    for fc in fact_check_results:
        link = fc.get("review_url", "")
        if link and link not in seen_links:
            seen_links.add(link)
            sources.append(SourceItem(
                outlet=fc.get("publisher", "Fact-Checker"),
                title=fc.get("title") or fc.get("claim", "Fact-Check Review"),
                link=link,
                published_time=str(fc.get("review_date", ""))
            ))

    # Add matching retrieved chunk sources
    for ev in evidence_items:
        cid = ev.get("id")
        link = ev.get("url", "")
        if (not supporting_chunk_ids or cid in supporting_chunk_ids) and link and link not in seen_links:
            seen_links.add(link)
            sources.append(SourceItem(
                outlet=ev.get("source", "Trusted News"),
                title=ev.get("title") or ev.get("source", "News Article"),
                link=link,
                published_time=str(ev.get("published_at", ""))
            ))

    return final_verdict, final_reason, final_confidence, sources
