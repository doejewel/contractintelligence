import os
import re
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .models import ContractAnalysis
from .extractor import extract_text_from_pdf, extract_text_from_string, truncate_for_context


# NOTE: {{ and }} are escaped braces — LangChain uses {var} for template variables
# so any literal { } in the prompt must be doubled to {{ }}
SYSTEM_PROMPT = """You are a senior contract analyst AI with expertise in corporate law,
risk assessment, and business compliance. Your job is to analyze contracts and return
a structured JSON analysis that will be used by an automated workflow system.

You MUST respond with valid JSON only — no preamble, no markdown, no explanation.
The JSON must match this exact schema:

{{
  "contract_title": "string",
  "parties": ["string"],
  "contract_type": "string (NDA | vendor | service | employment | partnership | other)",
  "effective_date": "string or null",
  "expiry_date": "string or null",
  "total_value": "string or null",
  "key_clauses": [
    {{
      "clause_type": "string",
      "content": "string (brief summary, max 2 sentences)",
      "risk_flag": true/false,
      "risk_reason": "string or null"
    }}
  ],
  "risk_score": integer 0-100,
  "risk_level": "low | medium | high | critical",
  "risk_summary": "string (plain English, 2-3 sentences)",
  "recommended_action": "auto_approve | human_review | reject",
  "reviewer_notes": "string (actionable notes if escalated to human)",
  "confidence_score": float 0.0-1.0
}}

Risk scoring guide:
- 0-25 (low): Standard clauses, nothing unusual, auto-approvable
- 26-50 (medium): Some clauses need attention but within normal range
- 51-75 (high): Significant risk clauses, unusual terms, requires human review
- 76-100 (critical): Extreme liability, missing protections, reject or major renegotiation

Key risk signals to watch:
- Unlimited liability clauses
- Missing indemnification caps
- Auto-renewal with price escalation
- IP ownership ambiguity
- Unilateral termination rights (especially one-sided)
- Jurisdiction in unfavorable locations
- Missing data protection / GDPR clauses
- Payment terms longer than 60 days
- Penalty clauses and liquidated damages
- Non-compete clauses that are overly broad"""

HUMAN_PROMPT = """Analyze the following contract text and return a structured JSON analysis.

CONTRACT TEXT:
{contract_text}

Remember: Return ONLY valid JSON. No text before or after the JSON object."""


class ContractAnalysisAgent:
    """
    LangChain-powered contract analysis agent using Google Gemini (free tier).
    Extracts clauses, scores risk, and recommends routing actions
    for the UiPath Maestro BPMN workflow.

    Free API key: https://aistudio.google.com/app/apikey
    Free tier: 15 req/min, 1M tokens/day — plenty for this hackathon.
    """

    def __init__(self, api_key: str = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GOOGLE_API_KEY not set.\n"
                "Get a free key at: https://aistudio.google.com/app/apikey\n"
                "Then add it to your .env file: GOOGLE_API_KEY=your-key-here"
            )

        self.llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=self.api_key,
            temperature=0.1,
            max_output_tokens=4096,
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ])

        self.chain = self.prompt | self.llm | JsonOutputParser()

    def analyze_pdf(self, pdf_path: str) -> ContractAnalysis:
        """Analyze a contract from a PDF file path."""
        raw_text = extract_text_from_pdf(pdf_path)
        return self._run_analysis(raw_text)

    def analyze_text(self, contract_text: str) -> ContractAnalysis:
        """Analyze a contract from raw text (useful for testing)."""
        raw_text = extract_text_from_string(contract_text)
        return self._run_analysis(raw_text)

    def _run_analysis(self, raw_text: str) -> ContractAnalysis:
        """Run the LLM analysis pipeline."""
        contract_text = truncate_for_context(raw_text, max_chars=12000)
        result_dict = self.chain.invoke({"contract_text": contract_text})

        # Gemini occasionally wraps output in markdown fences — strip defensively
        if isinstance(result_dict, str):
            result_dict = re.sub(r"```json|```", "", result_dict).strip()
            result_dict = json.loads(result_dict)

        return ContractAnalysis(**result_dict)

    def get_uipath_payload(self, analysis: ContractAnalysis) -> dict:
        """
        Format the analysis as a payload for UiPath Maestro.
        This dict is POSTed to the UiPath API Workflow webhook.
        """
        return {
            "contractTitle": analysis.contract_title,
            "parties": analysis.parties,
            "contractType": analysis.contract_type,
            "effectiveDate": analysis.effective_date,
            "expiryDate": analysis.expiry_date,
            "totalValue": analysis.total_value,
            "riskScore": analysis.risk_score,
            "riskLevel": analysis.risk_level.value,
            "riskSummary": analysis.risk_summary,
            "recommendedAction": analysis.recommended_action,
            "reviewerNotes": analysis.reviewer_notes,
            "confidenceScore": analysis.confidence_score,
            "flaggedClauses": [
                {
                    "clauseType": c.clause_type,
                    "content": c.content,
                    "riskReason": c.risk_reason,
                }
                for c in analysis.key_clauses
                if c.risk_flag
            ],
            "totalClausesAnalyzed": len(analysis.key_clauses),
            "totalFlagged": sum(1 for c in analysis.key_clauses if c.risk_flag),
        }