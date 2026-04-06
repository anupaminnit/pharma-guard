"""
Deterministic pharmaceutical unit extractor and comparator.

This is a safety-critical pre-processing step that runs BEFORE the LLM call.
It catches unit changes (mg → mcg, mg → IU) and large numeric discrepancies
using regex — independent of LLM judgment. This provides a hard safety net
for the most dangerous class of labelling error.

A 1000x dose error (mg vs mcg) or a 10x error (mg vs g) can be lethal.
We never rely solely on an LLM to catch this.

Usage:
    extractor = UnitExtractor()
    master_vals = extractor.extract(master_text)
    foreign_vals = extractor.extract(back_translated_text)
    violations = extractor.compare(master_vals, foreign_vals)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NamedTuple


# ── Canonical unit conversions to micrograms ─────────────────────────────────
# Used to detect dangerous cross-unit errors (e.g., "400mg" vs "400mcg")

UNIT_TO_MCG: dict[str, float] = {
    # mass
    "g":    1_000_000,
    "mg":       1_000,
    "mcg":          1,
    "µg":           1,
    "ug":           1,
    "ng":           0.001,
    # volume (approximation for liquids)
    "ml":       1_000,    # treated as mg equivalent for comparison
    "l":    1_000_000,
    # international units — context-dependent; flag any IU ↔ mass conversion
    "iu":       None,     # None = incompatible; always flag
    "units":    None,
    # percentage — flag if unit changes
    "%":        None,
}

# Regex: number + unit, e.g. "400mg", "0.5 mcg", "1,000 mg"
_NUMBER  = r"(\d[\d,\.]*)"
_UNITS   = r"(g|mg|mcg|µg|ug|ng|ml|mL|L|IU|iu|units?|%)"
_UNIT_RE = re.compile(
    rf"{_NUMBER}\s*{_UNITS}\b",
    re.IGNORECASE,
)


class MeasuredValue(NamedTuple):
    raw: str       # original string "400mg"
    number: float  # 400.0
    unit: str      # "mg"
    mcg: float | None  # canonical value in mcg, or None if incompatible


@dataclass
class UnitViolation:
    master_raw: str
    foreign_raw: str
    severity: str     # "critical" | "major"
    message: str


def _parse_number(s: str) -> float:
    """Parse a number that may contain commas or dots as thousand separators."""
    s = s.replace(" ", "")
    # Detect European notation: "1.000,5" → "1000.5"
    if re.match(r"^\d{1,3}(\.\d{3})+(,\d+)?$", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    return float(s)


def _to_mcg(number: float, unit: str) -> float | None:
    factor = UNIT_TO_MCG.get(unit.lower())
    if factor is None:
        return None
    return number * factor


class UnitExtractor:
    def extract(self, text: str) -> list[MeasuredValue]:
        """Extract all dose/quantity values from a text string."""
        results = []
        for match in _UNIT_RE.finditer(text):
            raw_num, raw_unit = match.group(1), match.group(2)
            try:
                number = _parse_number(raw_num)
            except ValueError:
                continue
            mcg = _to_mcg(number, raw_unit)
            results.append(MeasuredValue(
                raw=match.group(0).strip(),
                number=number,
                unit=raw_unit,
            mcg=mcg,
            ))
        return results

    def compare(
        self,
        master_values: list[MeasuredValue],
        foreign_values: list[MeasuredValue],
        tolerance_pct: float = 1.0,   # allow 1% rounding difference
    ) -> list[UnitViolation]:
        """
        Compare master and back-translated values.
        Returns violations for:
          - unit changes (mg → mcg) — always CRITICAL
          - numeric changes > tolerance — CRITICAL if > 20%, MAJOR otherwise
          - incompatible units (mass → IU) — always CRITICAL
        """
        violations = []

        if not master_values or not foreign_values:
            return violations

        # Pair up values by position (simple heuristic — assumes same order)
        for i, mv in enumerate(master_values):
            if i >= len(foreign_values):
                break
            fv = foreign_values[i]

            # ── Unit mismatch ─────────────────────────────────────────────
            if mv.unit.lower() != fv.unit.lower():
                # Incompatible units (mass vs IU)
                if mv.mcg is None or fv.mcg is None:
                    violations.append(UnitViolation(
                        master_raw=mv.raw,
                        foreign_raw=fv.raw,
                        severity="critical",
                        message=(
                            f"Incompatible unit change: master has '{mv.raw}', "
                            f"label has '{fv.raw}'. Cannot convert between these units."
                        ),
                    ))
                    continue

                # Same scale but different notation — check if equivalent
                ratio = fv.mcg / mv.mcg if mv.mcg else 0
                if abs(ratio - 1.0) > tolerance_pct / 100:
                    violations.append(UnitViolation(
                        master_raw=mv.raw,
                        foreign_raw=fv.raw,
                        severity="critical",
                        message=(
                            f"Unit change with value discrepancy: master '{mv.raw}' ≠ label '{fv.raw}'. "
                            f"Ratio: {ratio:.1f}x. This may indicate a 1000x dose error."
                        ),
                    ))
                continue

            # ── Same unit, check numeric value ────────────────────────────
            if mv.number == 0:
                continue

            diff_pct = abs((fv.number - mv.number) / mv.number) * 100

            if diff_pct > tolerance_pct:
                severity = "critical" if diff_pct > 20 else "major"
                violations.append(UnitViolation(
                    master_raw=mv.raw,
                    foreign_raw=fv.raw,
                    severity=severity,
                    message=(
                        f"Numeric discrepancy: master '{mv.raw}' vs label '{fv.raw}' "
                        f"({diff_pct:.1f}% difference)."
                    ),
                ))

        return violations
