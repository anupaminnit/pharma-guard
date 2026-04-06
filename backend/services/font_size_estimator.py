"""
Font size estimator from bounding box coordinates.

Claude's vision API cannot directly measure point sizes from an image.
This module estimates font size in points from:
  - Bounding box pixel height (from vision agent output)
  - Image resolution in DPI (from PDF metadata or assumed default)
  - Standard conversion: 1 point = 1/72 inch

Formula:
  font_pt = (bbox_height_px / image_height_px) * physical_height_inches * 72

This is an approximation — leading, line spacing, and font metrics affect the
apparent size. Results are flagged as "estimated" and should trigger manual
review rather than automatic non-compliant status.

Usage:
    estimator = FontSizeEstimator(image_width_px=800, image_height_px=1200, dpi=150)
    pt_size = estimator.estimate_from_bbox_height(bbox_height_pct=0.04)
    # bbox_height_pct: the 'height' field from vision agent bounding boxes (0-100 scale)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FontSizeEstimate:
    estimated_pt: float
    confidence: str    # "high" | "medium" | "low"
    note: str


class FontSizeEstimator:
    def __init__(
        self,
        image_width_px: int,
        image_height_px: int,
        dpi: int = 150,
    ) -> None:
        self.image_width_px  = image_width_px
        self.image_height_px = image_height_px
        self.dpi             = dpi

        # Physical dimensions of the image in inches
        self.physical_width_in  = image_width_px  / dpi
        self.physical_height_in = image_height_px / dpi

    def estimate_from_bbox_height(self, bbox_height_pct: float) -> FontSizeEstimate:
        """
        Estimate font size from a bounding box height expressed as a percentage
        of the image height (0–100 scale, as returned by the vision agent).

        Args:
            bbox_height_pct: height of the text bounding box as % of image height
                             (e.g. 4.0 means the box is 4% of the image height)

        Returns:
            FontSizeEstimate with pt size and confidence level
        """
        if bbox_height_pct <= 0 or bbox_height_pct > 100:
            return FontSizeEstimate(
                estimated_pt=0.0,
                confidence="low",
                note="Invalid bounding box height percentage",
            )

        # Convert % to pixels, then to inches, then to points
        bbox_height_px = (bbox_height_pct / 100.0) * self.image_height_px
        bbox_height_in = bbox_height_px / self.dpi
        estimated_pt   = bbox_height_in * 72

        # Confidence degrades for very small or very large values
        if estimated_pt < 4 or estimated_pt > 120:
            confidence = "low"
            note = f"Estimated {estimated_pt:.1f}pt — outlier range, manual verification recommended"
        elif bbox_height_pct < 1.0:
            confidence = "medium"
            note = f"Estimated {estimated_pt:.1f}pt — small bounding box, ±2pt accuracy"
        else:
            confidence = "high"
            note = f"Estimated {estimated_pt:.1f}pt"

        return FontSizeEstimate(
            estimated_pt=round(estimated_pt, 1),
            confidence=confidence,
            note=note,
        )

    def check_minimum_font_size(
        self,
        bbox_height_pct: float,
        minimum_pt: float,
        region: str,
    ) -> dict:
        """
        Check whether a bounding box meets the regulatory minimum font size.

        Returns a dict suitable for inclusion in vision_analysis.issues.
        """
        estimate = self.estimate_from_bbox_height(bbox_height_pct)

        if estimate.estimated_pt < minimum_pt:
            return {
                "type": "font_size_violation",
                "severity": "major",
                "element": "body_text",
                "estimated_pt": estimate.estimated_pt,
                "minimum_pt": minimum_pt,
                "confidence": estimate.confidence,
                "issue": (
                    f"Estimated font size {estimate.estimated_pt:.1f}pt is below "
                    f"{region} minimum of {minimum_pt}pt. {estimate.note}."
                ),
                "manual_verification_required": estimate.confidence != "high",
            }
        return {}

    @classmethod
    def from_image_bytes(cls, image_bytes: bytes, assumed_dpi: int = 150) -> "FontSizeEstimator":
        """Construct estimator from raw image bytes."""
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        # Try to get actual DPI from image metadata
        dpi_info = img.info.get("dpi")
        if dpi_info:
            try:
                dpi = int(dpi_info[0])
            except (TypeError, IndexError, ValueError):
                dpi = assumed_dpi
        else:
            dpi = assumed_dpi
        return cls(image_width_px=w, image_height_px=h, dpi=dpi)
