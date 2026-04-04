"""
Translation & Semantic Compliance Agent

Translates foreign-language packaging text back to English and performs
deep semantic comparison against the master English label. Does NOT look
for 1:1 word match — checks for medical intent equivalence.
"""

import json
import re
from typing import Any

import anthropic


SYSTEM_PROMPT = """You are a pharmaceutical regulatory compliance expert specializing in 
multilingual drug packaging review. Your job is to:

1. Back-translate foreign-language packaging text to English
2. Perform semantic medical intent comparison (not word-for-word matching)
3. Identify any changes in medical meaning, omissions, or additions

You must respond ONLY with valid JSON. No markdown, no preamble.

Focus on these critical areas:
- Active ingredients and dosage
- Contraindications
- Warnings and precautions  
- Side effects / adverse reactions
- Administration instructions
- Storage conditions
- Expiry / lot number format

When comparing, flag ANY deviation from the master that could affect patient safety."""


ANALYSIS_SCHEMA = """
{
  "back_translated_text": "English translation of the foreign text",
  "semantic_score": 95.0,
  "sections": [
    {
      "section": "Active Ingredients",
      "master_text": "...",
      "local_text": "...",
      "back_translation": "...",
      "status": "compliant",
      "confidence": 98.0,
      "issue": null
    }
  ],
  "discrepancies": [
    {
      "severity": "critical",
      "section": "Dosage Warning",
      "master_content": "...",
      "local_content": "...",
      "explanation": "The warning about renal impairment is missing from the local label",
      "recommendation": "Add renal impairment dosage adjustment warning"
    }
  ],
  "omissions": [],
  "additions": [],
  "overall_assessment": "..."
}
"""


class TranslationAgent:
    def __init__(self, client: anthropic.Anthropic):
        self.client = client
        self.model = "claude-sonnet-4-20250514"

    def analyze(
        self,
        master_label_text: str,
        foreign_text: str,
        source_language: str = "French",
    ) -> dict[str, Any]:
        """
        Core analysis: back-translate and semantically compare against master.
        """
        prompt = f"""MASTER ENGLISH LABEL (Source of Truth):
---
{master_label_text}
---

LOCAL PACKAGING TEXT ({source_language}):
---
{foreign_text}
---

Task:
1. Back-translate the {source_language} text to English
2. Compare each section against the master label for semantic equivalence
3. Flag any discrepancies that alter medical meaning
4. Score semantic compliance (0-100)

Respond with this exact JSON schema:
{ANALYSIS_SCHEMA}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text
        return self._parse_json(raw)

    def _parse_json(self, raw: str) -> dict[str, Any]:
        """Clean and parse JSON response."""
        # Strip markdown fences if present
        cleaned = re.sub(r"```(?:json)?\n?", "", raw).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Return a structured error result
            return {
                "back_translated_text": "Parse error — see raw output",
                "semantic_score": 0,
                "sections": [],
                "discrepancies": [
                    {
                        "severity": "system_error",
                        "section": "Parser",
                        "explanation": f"Failed to parse agent response: {raw[:500]}",
                        "recommendation": "Retry analysis",
                    }
                ],
                "omissions": [],
                "additions": [],
                "overall_assessment": "Analysis failed — manual review required",
            }
