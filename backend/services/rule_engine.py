"""
Regulatory Rule Engine — DB-backed, versioned compliance rules.

Rules are stored in the regulatory_rules table. When a regulatory body updates
a requirement (e.g. EU raises minimum font size from 7pt to 8pt), a single DB
row update with a new effective_date propagates to all future analyses without
requiring a code deploy. Past analyses retain their audit trail against the rules
active at the time of analysis.

Usage:
    engine = RegulatoryRuleEngine(db_session)
    context = await engine.build_vision_prompt_context("EU")
    violations = await engine.validate_result_against_rules(vision_result, "EU")
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import RegulatoryRule


@dataclass
class RuleViolation:
    rule_key: str
    rule_type: str
    expected: Any
    observed: Any
    severity: str  # "critical" | "major" | "minor"
    message: str


class RegulatoryRuleEngine:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._cache: dict[str, list[RegulatoryRule]] = {}

    async def get_rules_for_region(
        self, region: str, as_of: date | None = None
    ) -> list[RegulatoryRule]:
        """Load active rules for a region, optionally as of a historical date."""
        cache_key = f"{region}:{as_of or 'now'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        effective = as_of or date.today()
        stmt = (
            select(RegulatoryRule)
            .where(
                RegulatoryRule.region == region,
                RegulatoryRule.is_active == True,  # noqa: E712
                RegulatoryRule.effective_date <= effective,
            )
            .where(
                (RegulatoryRule.expiry_date == None) | (RegulatoryRule.expiry_date >= effective)  # noqa: E711
            )
            .order_by(RegulatoryRule.effective_date.desc())
        )
        result = await self._db.execute(stmt)
        rules = list(result.scalars().all())
        self._cache[cache_key] = rules
        return rules

    async def build_vision_prompt_context(self, region: str) -> str:
        """
        Convert active rules into natural language for injection into the
        vision agent system prompt.

        Example output:
            Regulatory requirements for EU:
            - warning_box_position: Warning box must appear in the top third of the main display panel.
            - font_minimum_body: Body text minimum font size is 7pt.
            - braille_required: Braille embossing required on outer carton.
        """
        rules = await self.get_rules_for_region(region)
        if not rules:
            return ""

        lines = [f"Regulatory requirements for {region}:"]
        for rule in rules:
            value = rule.rule_value
            description = value.get("description") or json.dumps(value)
            lines.append(f"- {rule.rule_key}: {description}")

        return "\n".join(lines)

    async def validate_result_against_rules(
        self, vision_result: dict, region: str
    ) -> list[RuleViolation]:
        """
        Post-process vision agent output against explicit DB rules.
        Returns a list of violations not already caught by the LLM.
        """
        rules = await self.get_rules_for_region(region)
        violations: list[RuleViolation] = []

        issues = vision_result.get("issues", [])
        detected_elements = {el.get("element", "").lower() for el in vision_result.get("compliant_elements", [])}

        for rule in rules:
            if rule.rule_type == "required_element":
                required_key = rule.rule_value.get("element_key", "").lower()
                if required_key and required_key not in detected_elements:
                    # Check if it's already in issues list
                    already_flagged = any(required_key in str(i).lower() for i in issues)
                    if not already_flagged:
                        violations.append(RuleViolation(
                            rule_key=rule.rule_key,
                            rule_type="required_element",
                            expected=rule.rule_value,
                            observed="not detected",
                            severity=rule.rule_value.get("severity", "major"),
                            message=f"Required element '{rule.rule_key}' not detected on packaging ({region} requirement).",
                        ))

            elif rule.rule_type == "font_minimum":
                min_pt = rule.rule_value.get("min_pt", 7)
                layout_score = vision_result.get("layout_score", 100)
                # Font size violations are estimated from layout score
                # A proper implementation uses backend/services/font_size_estimator.py
                if layout_score < 70:
                    violations.append(RuleViolation(
                        rule_key=rule.rule_key,
                        rule_type="font_minimum",
                        expected=f">= {min_pt}pt",
                        observed="estimated below minimum (low layout score)",
                        severity="major",
                        message=f"Font size may be below {region} minimum of {min_pt}pt. Manual verification required.",
                    ))

        return violations


# ── Seed helpers ──────────────────────────────────────────────────────────────

SEED_RULES: list[dict] = [
    # EU / EMA QRD Rev.11
    {"region": "EU",  "rule_type": "required_element", "rule_key": "warning_box",         "rule_value": {"element_key": "warning box", "description": "Warning box must appear in the top third of the main display panel.", "severity": "critical"}, "effective_date": "2020-01-01", "source_document": "EMA/CHMP/QRD/20 Rev.11"},
    {"region": "EU",  "rule_type": "font_minimum",     "rule_key": "font_minimum_body",   "rule_value": {"min_pt": 7, "description": "Body text minimum font size is 7pt (Commission Directive 2004/27/EC)."}, "effective_date": "2004-05-31", "source_document": "2004/27/EC"},
    {"region": "EU",  "rule_type": "required_element", "rule_key": "braille_outer_carton","rule_value": {"element_key": "braille", "description": "Braille embossing of product name required on outer carton.", "severity": "major"}, "effective_date": "2006-10-30", "source_document": "Dir 2004/27/EC Art.56a"},
    {"region": "EU",  "rule_type": "required_element", "rule_key": "inn_name",            "rule_value": {"element_key": "inn", "description": "INN (International Nonproprietary Name) must appear immediately below the brand name.", "severity": "critical"}, "effective_date": "2004-05-31", "source_document": "EMA/CHMP/QRD/20 Rev.11"},
    # FDA
    {"region": "FDA", "rule_type": "required_element", "rule_key": "black_box_warning",   "rule_value": {"element_key": "black box", "description": "Black box warning must appear before all other warnings, in a box with bold text.", "severity": "critical"}, "effective_date": "1979-01-01", "source_document": "21 CFR 201.57(c)(1)"},
    {"region": "FDA", "rule_type": "font_minimum",     "rule_key": "font_minimum_body",   "rule_value": {"min_pt": 6, "description": "Minimum font size 6pt for principal display panel text."}, "effective_date": "2006-06-30", "source_document": "21 CFR 201.60"},
    {"region": "FDA", "rule_type": "required_element", "rule_key": "ndc_number",          "rule_value": {"element_key": "ndc", "description": "NDC (National Drug Code) must appear on the label.", "severity": "major"}, "effective_date": "1972-01-01", "source_document": "21 CFR 201.2"},
    # PMDA (Japan)
    {"region": "PMDA","rule_type": "required_element", "rule_key": "inn_roman_script",    "rule_value": {"element_key": "inn", "description": "INN must appear in both Japanese (katakana) and Roman script.", "severity": "critical"}, "effective_date": "2005-04-01", "source_document": "MHLW Notification 0331015"},
    {"region": "PMDA","rule_type": "required_element", "rule_key": "approval_number",     "rule_value": {"element_key": "approval", "description": "PMDA approval number (承認番号) must appear on the outer carton.", "severity": "critical"}, "effective_date": "2005-04-01", "source_document": "Pharmaceutical Affairs Law Art.50"},
    {"region": "PMDA","rule_type": "required_element", "rule_key": "storage_temperature", "rule_value": {"element_key": "storage", "description": "Storage temperature must be explicitly stated in °C.", "severity": "major"}, "effective_date": "2005-04-01", "source_document": "MHLW Guidelines"},
    # ANVISA (Brazil)
    {"region": "ANVISA","rule_type":"required_element","rule_key": "dcb_name",            "rule_value": {"element_key": "dcb", "description": "DCB (Denominação Comum Brasileira) must appear on label.", "severity": "critical"}, "effective_date": "2003-01-01", "source_document": "RDC 71/2009"},
    # COFEPRIS (Mexico)
    {"region": "COFEPRIS","rule_type":"required_element","rule_key":"registro_sanitario", "rule_value": {"element_key": "registro", "description": "Registro Sanitario number must appear on packaging.", "severity": "critical"}, "effective_date": "2010-01-01", "source_document": "NOM-072-SSA1-2012"},
]


async def seed_rules(db: AsyncSession) -> int:
    """
    Seed the regulatory_rules table from SEED_RULES if empty.
    Returns number of rows inserted.
    """
    from datetime import date as date_type
    existing = await db.execute(select(RegulatoryRule).limit(1))
    if existing.scalar_one_or_none():
        return 0  # already seeded

    inserted = 0
    for entry in SEED_RULES:
        rule = RegulatoryRule(
            region=entry["region"],
            rule_type=entry["rule_type"],
            rule_key=entry["rule_key"],
            rule_value=entry["rule_value"],
            effective_date=date_type.fromisoformat(entry["effective_date"]),
            source_document=entry.get("source_document"),
            is_active=True,
        )
        db.add(rule)
        inserted += 1

    await db.commit()
    return inserted
