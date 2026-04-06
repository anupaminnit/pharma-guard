"""
Scan quality pre-processor for uploaded packaging images.

When a user uploads a scanned (not digital) packaging PDF or image, quality
may be insufficient for reliable OCR. This module:
  1. Estimates scan quality score (0-100) using image statistics
  2. Applies Pillow-based preprocessing if quality is below threshold
  3. Returns enhanced image bytes + quality score for the vision agent

Usage:
    processor = ScanQualityProcessor()
    result = processor.process(image_bytes)
    if result.quality_score < 70:
        # Use result.enhanced_bytes instead of original
        file_bytes = result.enhanced_bytes
"""

from __future__ import annotations

import io
import statistics
from dataclasses import dataclass

from PIL import Image, ImageEnhance, ImageFilter


@dataclass
class ScanResult:
    quality_score: float      # 0-100 (higher = better)
    needs_enhancement: bool
    enhanced_bytes: bytes     # original if enhancement not needed
    enhancements_applied: list[str]


class ScanQualityProcessor:
    def __init__(self, quality_threshold: float = 70.0):
        self.threshold = quality_threshold

    def estimate_quality(self, img: Image.Image) -> float:
        """
        Estimate image quality using:
        - Sharpness (Laplacian variance via a high-pass filter)
        - Contrast (standard deviation of pixel values)
        - Resolution (pixel area normalized to a reference)

        Returns a score 0-100.
        """
        # Convert to grayscale for analysis
        gray = img.convert("L")

        pixels = list(gray.getdata())
        if not pixels:
            return 0.0

        # ── Contrast score (0-40 pts) ─────────────────────────────────────
        try:
            std = statistics.stdev(pixels)
        except statistics.StatisticsError:
            std = 0
        contrast_score = min(std / 80 * 40, 40)

        # ── Sharpness score (0-40 pts) via simple edge detection ─────────
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_pixels = list(edges.getdata())
        mean_edge = sum(edge_pixels) / len(edge_pixels) if edge_pixels else 0
        sharpness_score = min(mean_edge / 30 * 40, 40)

        # ── Resolution score (0-20 pts) ───────────────────────────────────
        w, h = img.size
        area = w * h
        ref_area = 800 * 1200   # reference: 800x1200px at 150dpi
        res_score = min(area / ref_area * 20, 20)

        total = contrast_score + sharpness_score + res_score
        return round(total, 1)

    def enhance(self, img: Image.Image) -> tuple[Image.Image, list[str]]:
        """Apply a sequence of Pillow enhancements for scanned images."""
        applied = []

        # 1. Upscale if too small
        w, h = img.size
        if w < 600 or h < 800:
            scale = max(600 / w, 800 / h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            applied.append(f"upscale_{scale:.1f}x")

        # 2. Greyscale conversion for text clarity
        if img.mode != "L":
            img_gray = img.convert("L")
        else:
            img_gray = img

        # 3. Contrast enhancement (1.0 = no change; 2.0 = double)
        enhancer = ImageEnhance.Contrast(img_gray)
        img_gray = enhancer.enhance(1.8)
        applied.append("contrast_1.8x")

        # 4. Sharpness enhancement
        enhancer = ImageEnhance.Sharpness(img_gray)
        img_gray = enhancer.enhance(2.0)
        applied.append("sharpen_2.0x")

        # 5. Adaptive thresholding via median filter then binarise
        img_filtered = img_gray.filter(ImageFilter.MedianFilter(size=3))
        applied.append("median_filter")

        # Convert back to RGB so Claude's vision API accepts it
        img_out = img_filtered.convert("RGB")

        return img_out, applied

    def process(self, image_bytes: bytes) -> ScanResult:
        """
        Main entry point. Pass raw image bytes; returns ScanResult.

        If quality_score >= threshold, returns original bytes unchanged.
        If quality_score < threshold, applies enhancement pipeline.
        """
        img = Image.open(io.BytesIO(image_bytes))
        quality_score = self.estimate_quality(img)

        if quality_score >= self.threshold:
            return ScanResult(
                quality_score=quality_score,
                needs_enhancement=False,
                enhanced_bytes=image_bytes,
                enhancements_applied=[],
            )

        enhanced_img, applied = self.enhance(img)

        buf = io.BytesIO()
        enhanced_img.save(buf, format="JPEG", quality=92)
        enhanced_bytes = buf.getvalue()

        return ScanResult(
            quality_score=quality_score,
            needs_enhancement=True,
            enhanced_bytes=enhanced_bytes,
            enhancements_applied=applied,
        )
