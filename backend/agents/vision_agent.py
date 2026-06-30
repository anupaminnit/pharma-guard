"""
Vision Agent — Packaging Layout & Formatting Compliance

Uses a multimodal LLM to scan the actual packaging artwork (PDF/image)
and verify that safety warnings appear in the correct location, font size,
and formatting as required by local regulatory guidelines.
"""

import json
import re
from typing import Any

import anthropic


TEXT_EXTRACTION_SYSTEM = """You are a pharmaceutical packaging OCR expert. 
Extract ALL text from this packaging image/document, preserving:
- Section structure and hierarchy
- Any warnings or highlighted text
- Ingredient lists, dosage instructions
- Regulatory markings

Respond ONLY with JSON in this exact format:
{
  "extracted_text": "full extracted text here with \\n for line breaks",
  "sections_detected": ["Active Ingredients", "Warnings", "Dosage", ...],
  "language_detected": "French",
  "confidence": 95.0
}"""


LAYOUT_SYSTEM_PROMPT = """You are a pharmaceutical regulatory compliance expert 
specializing in packaging artwork review for global drug launches.

You analyze packaging images to check:
1. WARNING BOX: Must be prominently placed, typically top-third of back panel
2. FONT SIZE COMPLIANCE: Warnings ≥ 8pt equivalent; active ingredients ≥ 6pt
3. REQUIRED ELEMENTS: Lot number, expiry date, manufacturer address, barcode
4. VISUAL HIERARCHY: Safety-critical text must be most prominent after brand name
5. COLOR CONTRAST: Safety warnings must meet minimum contrast ratio
6. REGULATORY SYMBOLS: CE marks, recycling symbols, country-specific icons

Local regulatory requirements vary:
- EU/France: Must include Braille for brand name, blue border on warnings
- Japan: Kanji drug name must appear above romanized name
- US: "Rx Only" symbol, NDC number format
- Brazil: ANVISA number prominently displayed

Respond ONLY with valid JSON. No markdown.
"""

LAYOUT_SCHEMA = """
{
  "layout_score": 85.0,
  "issues": [
    {
      "element": "Warning Box",
      "location": "bottom-left",
      "status": "non_compliant",
      "severity": "critical",
      "issue": "Warning box is at bottom of panel; EU regulations require top-third placement",
      "recommendation": "Relocate warning box to top section of back panel",
      "bounding_box": {"x": 5, "y": 75, "width": 90, "height": 15}
    }
  ],
  "compliant_elements": [
    {
      "element": "Active Ingredients List",
      "location": "center panel",
      "status": "compliant",
      "note": "Font size appears adequate, all ingredients listed",
      "bounding_box": {"x": 10, "y": 30, "width": 80, "height": 20}
    }
  ],
  "missing_elements": [],
  "regulatory_context": "EU/France packaging requirements applied",
  "overall_observations": "..."
}"""


class VisionAgent:
    def __init__(self, client: anthropic.Anthropic):
        self.client = client
        self.model = "claude-sonnet-4-6"

    def extract_text_from_image(
        self, image_b64: str, media_type: str, language: str = "French"
    ) -> tuple[str, dict[str, Any]]:
        """
        Extract all text from packaging image using multimodal LLM.
        Returns (extracted_text_string, full_json_response)
        """
        # Handle PDF by treating first page; for demo we accept images directly
        if "pdf" in media_type:
            media_type = "image/jpeg"  # Backend converts; demo uses images

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=TEXT_EXTRACTION_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": f"Extract all text from this {language} pharmaceutical packaging.",
                        },
                    ],
                }
            ],
        )

        raw = response.content[0].text
        parsed = self._parse_json(raw)
        extracted = parsed.get("extracted_text", raw)
        return extracted, parsed

    def analyze_layout_compliance(
        self, image_b64: str, media_type: str, language: str = "French"
    ) -> dict[str, Any]:
        """
        Analyze packaging layout against regulatory requirements.
        Returns detailed compliance report with bounding box coordinates.
        """
        if "pdf" in media_type:
            media_type = "image/jpeg"

        region = self._detect_regulatory_region(language)

        prompt = f"""Analyze this pharmaceutical packaging image for layout compliance.
        
Regulatory context: {region}
Local language: {language}

Check each element and provide precise bounding box coordinates as percentage of image dimensions 
(x, y = top-left corner; width, height = percentage of total image size).

Respond with this exact JSON schema:
{LAYOUT_SCHEMA}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            system=LAYOUT_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        raw = response.content[0].text
        return self._parse_json(raw)

    def _detect_regulatory_region(self, language: str) -> str:
        lang_map = {
            "French": "EU/France — EMA guidelines, Braille requirement",
            "German": "EU/Germany — EMA guidelines, German Drug Act",
            "Japanese": "Japan — PMDA, JMHLW regulations",
            "Spanish": "EU/Spain or LATAM — EMA or ANMAT/COFEPRIS",
            "Portuguese": "Brazil — ANVISA RDC 71/2009",
            "Chinese": "China — NMPA guidelines",
            "Arabic": "GCC — Gulf Health Council standards",
            "Russian": "Russia — Roszdravnadzor",
        }
        return lang_map.get(language, "General ICH guidelines")

    def _parse_json(self, raw: str) -> dict[str, Any]:
        cleaned = re.sub(r"```(?:json)?\n?", "", raw).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "layout_score": 0,
                "issues": [{"element": "Parser", "severity": "system_error",
                             "issue": f"Failed to parse: {raw[:300]}",
                             "recommendation": "Retry analysis"}],
                "compliant_elements": [],
                "missing_elements": [],
                "overall_observations": "Parse error — manual review required",
            }
