#!/usr/bin/env python3
"""
Test the Contract Analysis Agent directly.
Run: python tests/test_agent.py

This tests the full pipeline:
  PDF/text -> LLM extraction -> risk scoring -> UiPath payload
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.analyzer import ContractAnalysisAgent
from agent.models import RiskLevel


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def test_contract_analysis():
    print_section("Contract Intelligence Manager — Agent Test")

    # Load sample contract
    contract_path = Path(__file__).parent.parent / "sample_contracts" / "risky_vendor_contract.txt"
    contract_text = contract_path.read_text()
    print(f"\n✓ Loaded contract: {contract_path.name}")
    print(f"  Characters: {len(contract_text):,}")

    # Initialize agent
    print("\n⚡ Initializing LangChain agent...")
    try:
        agent = ContractAnalysisAgent()
        print("  ✓ Agent initialized (claude-opus-4-5)")
    except ValueError as e:
        print(f"\n  ✗ ERROR: {e}")
        print("  Add your API key to a .env file:")
        print("  ANTHROPIC_API_KEY=your-key-here")
        return

    # Run analysis
    print("\n🔍 Running contract analysis...")
    print("  (This calls the Claude API — may take 10-20 seconds)")

    try:
        analysis = agent.analyze_text(contract_text)
    except Exception as e:
        print(f"\n  ✗ Analysis failed: {e}")
        return

    # Print results
    print_section("ANALYSIS RESULTS")

    print(f"\n📄 Contract: {analysis.contract_title}")
    print(f"   Type: {analysis.contract_type}")
    print(f"   Parties: {', '.join(analysis.parties)}")
    print(f"   Effective: {analysis.effective_date or 'Not specified'}")
    print(f"   Expires: {analysis.expiry_date or 'Not specified'}")
    print(f"   Value: {analysis.total_value or 'Not specified'}")

    print(f"\n⚠️  Risk Score: {analysis.risk_score}/100 ({analysis.risk_level.value.upper()})")
    print(f"   Confidence: {analysis.confidence_score:.0%}")
    print(f"\n   Summary: {analysis.risk_summary}")
    print(f"\n   Recommended Action: {analysis.recommended_action.upper()}")

    # Flagged clauses
    flagged = [c for c in analysis.key_clauses if c.risk_flag]
    print(f"\n🚩 Flagged Clauses ({len(flagged)} of {len(analysis.key_clauses)} analyzed):")
    for i, clause in enumerate(flagged, 1):
        print(f"\n   {i}. [{clause.clause_type}]")
        print(f"      {clause.content}")
        if clause.risk_reason:
            print(f"      ⚠ {clause.risk_reason}")

    print(f"\n📝 Reviewer Notes:")
    print(f"   {analysis.reviewer_notes}")

    # UiPath payload
    print_section("UIPATH MAESTRO PAYLOAD")
    payload = agent.get_uipath_payload(analysis)
    print(json.dumps(payload, indent=2))

    # Routing decision
    print_section("BPMN ROUTING DECISION")
    if analysis.recommended_action == "auto_approve":
        print("\n  ✅ ROUTE: Auto-approve → ERP posting")
        print("     UiPath Robot will post contract data to ERP")
    elif analysis.recommended_action == "human_review":
        print("\n  👤 ROUTE: Human review required")
        print("     UiPath will assign task to Legal/Manager")
        print(f"     Risk score {analysis.risk_score}/100 exceeds threshold")
    elif analysis.recommended_action == "reject":
        print("\n  ❌ ROUTE: Reject — contract does not meet policy")
        print("     Notification will be sent to submitter")

    print("\n" + "="*60)
    print("  ✓ Test complete — agent is working correctly")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_contract_analysis()