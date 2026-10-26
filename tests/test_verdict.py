"""Unit tests for verdict merging, downgrading rules, and fact-check precedence."""
from backend.services.verdict import merge_verdict


def test_fact_check_false_outranks_everything():
    """Verify published fact-check of 'False' overrides judge and sets CONTRADICTED."""
    verdict, reason, confidence, sources = merge_verdict(
        judge_verdict="VERIFIED",
        judge_reason="The text looks supported.",
        judge_confidence="high",
        supporting_chunk_ids=[1, 2],
        evidence_items=[{"id": 1, "source": "A", "url": "http://a"}, {"id": 2, "source": "B", "url": "http://b"}],
        fact_check_results=[{
            "publisher": "BOOM",
            "rating": "False",
            "review_url": "https://boomlive.in/factcheck",
            "title": "Debunking viral 500 note ban"
        }],
        user_language="en"
    )
    assert verdict == "CONTRADICTED"
    assert confidence == "high"
    assert "BOOM" in reason
    assert len(sources) > 0


def test_verified_downgrades_to_partial_with_single_outlet():
    """Verify that a claim supported by fewer than 2 distinct outlets is downgraded to PARTIAL in code."""
    verdict, reason, confidence, sources = merge_verdict(
        judge_verdict="VERIFIED",
        judge_reason="Single source confirmed.",
        judge_confidence="high",
        supporting_chunk_ids=[1],
        evidence_items=[{"id": 1, "source": "OnlyOneOutlet", "url": "http://one"}],
        fact_check_results=[],
        user_language="en"
    )
    assert verdict == "PARTIAL"
    assert "Downgraded to PARTIAL" in reason


def test_verified_retained_with_two_distinct_outlets():
    """Verify that 2 distinct outlets allows VERIFIED verdict."""
    verdict, reason, confidence, sources = merge_verdict(
        judge_verdict="VERIFIED",
        judge_reason="Two outlets confirmed.",
        judge_confidence="high",
        supporting_chunk_ids=[1, 2],
        evidence_items=[
            {"id": 1, "source": "The Hindu", "url": "http://thehindu"},
            {"id": 2, "source": "NDTV", "url": "http://ndtv"}
        ],
        fact_check_results=[],
        user_language="en"
    )
    assert verdict == "VERIFIED"
    assert confidence == "high"


def test_unverified_contains_absence_of_evidence_disclaimer():
    """Verify UNVERIFIED verdict explicitly states absence of evidence does not prove falsehood."""
    verdict, reason, confidence, sources = merge_verdict(
        judge_verdict="UNVERIFIED",
        judge_reason="No documents found.",
        judge_confidence="low",
        supporting_chunk_ids=[],
        evidence_items=[],
        fact_check_results=[],
        user_language="en"
    )
    assert verdict == "UNVERIFIED"
    assert "Absence of evidence does not prove the claim is false" in reason
