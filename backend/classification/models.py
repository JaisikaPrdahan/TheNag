from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedFact:
    value: Any
    confidence: str
    fact_type: str
    source: str
    evidence: str = ""
    timestamp: float | None = None

    def to_dict(self):
        """
        Matches the opportunities.extracted_facts jsonb element shape
        documented in docs/database-schema.md:
            {"value": ..., "confidence": ..., "type": ..., "source": ...}
        `fact_type` is renamed to `type` here (kept as fact_type on the
        Python object since `type` shadows a builtin).
        """
        return {
            "value": self.value,
            "confidence": self.confidence,
            "type": self.fact_type,
            "source": self.source,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
        }


@dataclass
class ClassifiedFacts:
    primary_category: str
    secondary_categories: list[str] = field(default_factory=list)
    extracted_facts: list[ExtractedFact] = field(default_factory=list)
    resolved_dates: list[dict] = field(default_factory=list)
    overall_confidence: str = "yellow"
    clarification_questions: list[str] = field(default_factory=list)

    def to_opportunity_row(self):
        """
        Shapes this result into the columns db_writes.create_opportunity()
        needs for the `opportunities` table (docs/database-schema.md
        Table 3): primary_category, secondary_categories, extracted_facts.
        `resolved_dates`, `overall_confidence` and `clarification_questions`
        aren't their own columns -- they're folded into extracted_facts
        so nothing Person 2 computed is lost on the way into the DB.
        """
        facts = [f.to_dict() for f in self.extracted_facts]

        for resolved in self.resolved_dates:
            facts.append({
                "value": resolved.get("date") or (
                    f"{resolved.get('start_date')} to {resolved.get('end_date')}"
                ),
                "confidence": resolved.get("confidence", "yellow"),
                "type": resolved.get("date_type", "unknown"),
                "source": resolved.get("source", "unknown"),
                "evidence": resolved.get("raw_text", ""),
                "timestamp": resolved.get("timestamp"),
            })

        if self.clarification_questions:
            facts.append({
                "value": self.clarification_questions,
                "confidence": "red",
                "type": "clarification_questions",
                "source": "classifier",
                "evidence": "",
                "timestamp": None,
            })

        return {
            "primary_category": self.primary_category,
            "secondary_categories": self.secondary_categories,
            "extracted_facts": facts,
        }
