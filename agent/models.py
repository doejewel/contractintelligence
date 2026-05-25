from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExtractedClause(BaseModel):
    clause_type: str = Field(description="Type of clause e.g. liability, payment, termination")
    content: str = Field(description="The clause text or summary")
    risk_flag: bool = Field(description="Whether this clause is flagged as risky")
    risk_reason: Optional[str] = Field(default=None, description="Why this clause is risky")


class ContractAnalysis(BaseModel):
    contract_title: str = Field(description="Title or name of the contract")
    parties: list[str] = Field(description="Parties involved in the contract")
    contract_type: str = Field(description="Type: NDA, vendor, service, employment, etc.")
    effective_date: Optional[str] = Field(default=None, description="Contract start date if found")
    expiry_date: Optional[str] = Field(default=None, description="Contract end/renewal date if found")
    total_value: Optional[str] = Field(default=None, description="Contract value or payment terms")
    key_clauses: list[ExtractedClause] = Field(description="Extracted and analyzed clauses")
    risk_score: int = Field(description="Overall risk score 0-100. 0=no risk, 100=extreme risk", ge=0, le=100)
    risk_level: RiskLevel = Field(description="Risk classification based on score")
    risk_summary: str = Field(description="Plain English summary of the key risks")
    recommended_action: str = Field(description="auto_approve, human_review, or reject")
    reviewer_notes: str = Field(description="Notes to help the human reviewer if escalated")
    confidence_score: float = Field(description="Agent confidence in its analysis 0.0-1.0", ge=0.0, le=1.0)