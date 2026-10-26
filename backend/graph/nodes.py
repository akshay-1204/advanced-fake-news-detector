"""Node implementations for Satyavani AI LangGraph workflow."""
import json
import logging
from typing import Dict, Any, List

from backend.graph.state import SatyavaniState
from backend.schemas.chat import (
    IntentClassificationResult,
    ClaimJudgeResult,
    NewsSummarizerResult,
    IntentType,
    VerdictType,
    ConfidenceType,
    SourceItem,
)
from backend.services.prompt_loader import render_prompt
from backend.services.llm import call_llm_json, call_llm, clean_json_text
from backend.services.weather import get_weather_for_city
from backend.services.fact_check_api import search_google_fact_check
from backend.services.retriever import retrieve_evidence_for_claim, retrieve_today_news
from backend.services.verdict import merge_verdict

logger = logging.getLogger(__name__)


def classify_intent_node(state: SatyavaniState) -> SatyavaniState:
    """Classifies user intent using prompts/intent_classifier.md. Defaults to CLAIM_CHECK on failure."""
    user_msg = state.get("user_message", "")
    prompt = render_prompt("intent_classifier.md", {"USER_MESSAGE": user_msg})

    result: IntentClassificationResult = call_llm_json(prompt, IntentClassificationResult)

    if result is None:
        logger.warning("Intent classification failed or produced invalid JSON. Defaulting to CLAIM_CHECK.")
        state["intent"] = IntentType.CLAIM_CHECK.value
        state["topic"] = "general"
        state["city"] = None
        state["language"] = "en"
        state["claim"] = user_msg
    else:
        state["intent"] = result.intent.value
        state["topic"] = result.topic or "general"
        state["city"] = result.city
        state["language"] = result.language or "en"
        state["claim"] = result.claim or user_msg

    return state


def today_news_node(state: SatyavaniState) -> SatyavaniState:
    """Summarizes articles published in the last 24 hours."""
    db = state.get("db")
    topic = state.get("topic", "general")
    user_lang = state.get("language", "en")

    articles: List[Dict[str, Any]] = []
    if db is not None:
        articles = retrieve_today_news(db=db, topic=topic, max_items=25)

    if not articles:
        empty_messages = {
            "en": f"No news articles found in the last 24 hours under '{topic}'. News updates automatically every 45 minutes.",
            "hi": f"पिछले 24 घंटों में '{topic}' श्रेणी में कोई लेख नहीं मिला। समाचार हर 45 मिनट में स्वतः अपडेट होता है।",
            "te": f"గత 24 గంటల్లో '{topic}' అంశంలో ఎటువంటి వార్తలు లేవు. వార్తలు ప్రతి 45 నిమిషాలకు స్వయంచాలకంగా అప్‌డేట్ అవుతాయి."
        }
        state["reply"] = empty_messages.get(user_lang, empty_messages["en"])
        state["sources"] = []
        return state

    # Format numbered articles for prompt
    formatted_articles = []
    for idx, art in enumerate(articles, start=1):
        time_str = art["published_at"].strftime("%Y-%m-%d %H:%M") if hasattr(art["published_at"], "strftime") else str(art["published_at"])
        formatted_articles.append(f"[{idx}] {art['source']} | {time_str} | {art['title']}\n{art['content'][:250]}")
    articles_str = "\n".join(formatted_articles)

    prompt = render_prompt("news_summarizer.md", {
        "MAX_ITEMS": 10,
        "USER_LANGUAGE": user_lang,
        "ARTICLES": articles_str
    })

    res: NewsSummarizerResult = call_llm_json(prompt, NewsSummarizerResult)

    if res and res.items:
        lines = []
        sources_list = []
        seen_links = set()

        for itm in res.items:
            outlets_str = ", ".join(itm.sources) if itm.sources else "Trusted Outlets"
            lines.append(f"• **{itm.headline}**\n  {itm.summary} *(Sources: {outlets_str})*\n")

        state["reply"] = "\n".join(lines).strip()

        # Collect sources from referenced articles
        for art in articles[:10]:
            if art["url"] not in seen_links:
                seen_links.add(art["url"])
                sources_list.append({
                    "outlet": art["source"],
                    "title": art["title"],
                    "link": art["url"],
                    "published_time": str(art["published_at"])
                })
        state["sources"] = sources_list
    else:
        # Fallback if summarizer JSON fails
        lines = [f"• **{a['title']}** ({a['source']})" for a in articles[:8]]
        state["reply"] = "Recent news in the last 24 hours:\n\n" + "\n".join(lines)
        state["sources"] = [
            {"outlet": a["source"], "title": a["title"], "link": a["url"], "published_time": str(a["published_at"])}
            for a in articles[:8]
        ]

    return state


def weather_node(state: SatyavaniState) -> SatyavaniState:
    """Fetches real weather for requested city from Open-Meteo without hallucinating."""
    city = state.get("city") or state.get("user_message", "")
    weather_info = get_weather_for_city(city)

    if weather_info.get("success"):
        state["reply"] = weather_info["message"]
        state["sources"] = [{
            "outlet": "Open-Meteo",
            "title": f"Weather Forecast for {weather_info['city']}",
            "link": "https://open-meteo.com",
            "published_time": "Live"
        }]
    else:
        state["reply"] = f"Could not retrieve weather: {weather_info.get('error', 'Unknown error')}."
        state["sources"] = []

    state["verdict"] = None
    state["confidence"] = None
    return state


def claim_check_node(state: SatyavaniState) -> SatyavaniState:
    """Executes the full anti-hallucination fact checking pipeline for claims."""
    claim = state.get("claim") or state.get("user_message", "")
    user_lang = state.get("language", "en")
    db = state.get("db")

    # Step a: Google Fact Check Tools API query
    fact_checks = search_google_fact_check(claim, language_code=user_lang)
    state["fact_checks"] = fact_checks

    # Step b: Semantic chunk retrieval from pgvector / database
    evidence = []
    if db is not None:
        evidence = retrieve_evidence_for_claim(claim, db=db)
    state["evidence"] = evidence

    # Step c: Anti-hallucination rule: If nothing is retrieved and no fact check, return UNVERIFIED WITHOUT calling LLM
    if not evidence and not fact_checks:
        logger.info("No evidence retrieved and no fact check found for claim. Returning UNVERIFIED without LLM call.")
        unverified_text = {
            "en": "No verified reports or fact-checks found matching this claim in trusted news outlets. Absence of evidence does not prove the claim is false; it may be very new or very local.",
            "hi": "विश्वसनीय समाचार स्रोतों में इस दावे से मेल खाने वाला कोई सत्यापित रिकॉर्ड नहीं मिला। साक्ष्य की अनुपस्थिति यह साबित नहीं करती कि दावा झूठा है; यह बहुत नया या स्थानीय हो सकता है।",
            "te": "విశ్వసనీయ వార్తా వనరులలో ఈ వాదనకు సంబంధించి ఎటువంటి ఆధారాలు లభించలేదు. ఆధారాలు లభించకపోవడం వలన ఈ వాదన అసత్యమని చెప్పలేము; ఇది చాలా తాజాది లేదా స్థానికమైనది కావచ్చు."
        }
        state["verdict"] = VerdictType.UNVERIFIED.value
        state["confidence"] = ConfidenceType.LOW.value
        state["reason"] = unverified_text.get(user_lang, unverified_text["en"])
        state["reply"] = state["reason"]
        state["sources"] = []
        return state

    # Step d: Format evidence passages for LLM judge
    formatted_evidence_lines = []
    for idx, ev in enumerate(evidence, start=1):
        date_str = str(ev.get("published_at", ""))[:10]
        formatted_evidence_lines.append(
            f"[{idx}] source: {ev.get('source')} | type: {ev.get('doc_type', 'news')} | time: {date_str} | text: {ev.get('text')}"
        )

    for idx, fc in enumerate(fact_checks, start=len(evidence) + 1):
        formatted_evidence_lines.append(
            f"[{idx}] source: {fc.get('publisher')} | type: factcheck | time: {str(fc.get('review_date'))[:10]} | text: Rating: {fc.get('rating')}. {fc.get('title')}"
        )

    evidence_str = "\n".join(formatted_evidence_lines)

    prompt = render_prompt("claim_judge.md", {
        "CLAIM": claim,
        "EVIDENCE": evidence_str,
        "USER_LANGUAGE": user_lang,
    })

    judge_result: ClaimJudgeResult = call_llm_json(prompt, ClaimJudgeResult)

    if judge_result is None:
        # Fallback to UNVERIFIED if judge fails
        judge_verdict = VerdictType.UNVERIFIED.value
        judge_reason = "Unable to verify claim from provided evidence."
        judge_confidence = ConfidenceType.LOW.value
        supporting_ids = []
    else:
        judge_verdict = judge_result.verdict.value
        judge_reason = judge_result.reason
        judge_confidence = judge_result.confidence.value
        supporting_ids = judge_result.supporting_chunk_ids

    # Step e: Verdict merging (enforces fact-check outranking and 2-outlet rule)
    final_verdict, final_reason, final_conf, source_items = merge_verdict(
        judge_verdict=judge_verdict,
        judge_reason=judge_reason,
        judge_confidence=judge_confidence,
        supporting_chunk_ids=supporting_ids,
        evidence_items=evidence,
        fact_check_results=fact_checks,
        user_language=user_lang,
    )

    state["verdict"] = final_verdict
    state["reason"] = final_reason
    state["confidence"] = final_conf
    state["reply"] = final_reason
    state["sources"] = [s.model_dump() for s in source_items]
    return state


def small_talk_node(state: SatyavaniState) -> SatyavaniState:
    """Handles conversational greetings and capability explanations."""
    user_lang = state.get("language", "en")
    greetings = {
        "en": "Namaste! I am **Satyavani AI** (Voice of Truth), your trusted news fact-checking assistant.\n\n"
              "Here is what I can do:\n"
              "• **Fact-Check Claims**: Paste a rumour, WhatsApp forward, or news statement to verify it against trusted outlets.\n"
              "• **Today's News**: Ask for today's headlines or select a topic like India, Sports, Tech, or World.\n"
              "• **Live Weather**: Ask for current temperature in any city.\n\n"
              "How can I assist you today?",
        "hi": "नमस्ते! मैं **सत्यवाणी एआई** (सत्य की आवाज़) हूँ, आपका विश्वसनीय समाचार और तथ्य-जांच सहायक।\n\n"
              "मैं आपकी क्या सहायता कर सकता हूँ?\n"
              "• **दावों की तथ्य-जांच**: किसी समाचार या सोशल मीडिया संदेश की सच्चाई जांचें।\n"
              "• **आज की ताज़ा ख़बरें**: पिछले 24 घंटों की मुख्य खबरें प्राप्त करें।\n"
              "• **मौसम**: किसी भी शहर का वर्तमान तापमान जानें।",
        "te": "నమస్కారం! నేను **సత్యవాణి AI** (సత్య వాణి), మీ వార్తా వాస్తవ తనిఖీ సహాయకుడిని.\n\n"
              "నేను ఏమి చేయగలను:\n"
              "• **వార్తల వాస్తవ తనిఖీ**: వాట్సాప్ ఫార్వర్డ్ లేదా ఏదైనా వార్త వాస్తవమో కాదో నిర్ధారించండి.\n"
              "• **ఈ రోజు వార్తలు**: గత 24 గంటల ముఖ్యాంశాలు తెలుసుకోండి.\n"
              "• **వాతావరణం**: ఏదైనా నగర ఉష్ణోగ్రత తెలుసుకోండి."
    }
    state["reply"] = greetings.get(user_lang, greetings["en"])
    state["verdict"] = None
    state["confidence"] = None
    state["sources"] = []
    return state
