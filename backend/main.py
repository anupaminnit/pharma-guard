"""
Multilingual Packaging & Labeling Compliance Agent - Backend
FastAPI server orchestrating translation, semantic, and vision agents.
"""

import os
import base64
import json
import io
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

import anthropic
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.translation_agent import TranslationAgent
from agents.vision_agent import VisionAgent

app = FastAPI(
    title="Packaging Compliance API",
    description="Multilingual pharmaceutical packaging and labeling compliance checker",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
translation_agent = TranslationAgent(client)
vision_agent = VisionAgent(client)


class ComplianceRequest(BaseModel):
    master_label_text: str
    source_language: str = "English"
    target_language: str = "French"


class ComplianceResult(BaseModel):
    overall_status: str  # "compliant", "non_compliant", "needs_review"
    compliance_score: float  # 0-100
    translation_analysis: dict
    vision_analysis: dict
    agent_log: list[dict]
    summary: str


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


@app.post("/api/analyze", response_model=ComplianceResult)
async def analyze_packaging(
    master_label: str = Form(..., description="Master English label text"),
    target_language: str = Form(default="French"),
    packaging_pdf: UploadFile = File(..., description="Regional packaging PDF/image"),
):
    """
    Main compliance analysis endpoint.
    Runs translation agent and vision agent in sequence.
    """
    agent_log = []

    # Read and encode the uploaded file
    file_bytes = await packaging_pdf.read()
    file_type = packaging_pdf.content_type or "image/jpeg"

    # Convert PDF to JPEG image for multimodal analysis — raw PDF bytes cannot be
    # passed to Claude vision with media_type="image/jpeg"
    if "pdf" in file_type.lower():
        try:
            from pdf2image import convert_from_bytes
            pages = convert_from_bytes(file_bytes, first_page=1, last_page=1, dpi=150)
            buf = io.BytesIO()
            pages[0].save(buf, format="JPEG", quality=90)
            file_bytes = buf.getvalue()
            file_type = "image/jpeg"
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Could not render PDF (ensure poppler is installed: brew install poppler): {e}",
            )

    file_b64 = base64.standard_b64encode(file_bytes).decode("utf-8")

    agent_log.append({
        "agent": "Orchestrator",
        "step": "File received",
        "detail": f"Processing {packaging_pdf.filename} ({len(file_bytes) / 1024:.1f} KB)",
        "status": "info",
    })

    # Step 1: Vision Agent - Extract text from packaging
    agent_log.append({
        "agent": "Vision Agent",
        "step": "Text extraction",
        "detail": "Scanning packaging artwork with multimodal LLM...",
        "status": "running",
    })

    extracted_text, vision_raw = vision_agent.extract_text_from_image(
        file_b64, file_type, target_language
    )

    agent_log.append({
        "agent": "Vision Agent",
        "step": "Text extracted",
        "detail": f"Extracted {len(extracted_text)} characters from packaging",
        "status": "success",
    })

    # Step 2: Translation Agent - Back-translate and compare
    agent_log.append({
        "agent": "Translation Agent",
        "step": "Back-translation",
        "detail": f"Translating {target_language} → English for semantic comparison...",
        "status": "running",
    })

    translation_result = translation_agent.analyze(
        master_label_text=master_label,
        foreign_text=extracted_text,
        source_language=target_language,
    )

    agent_log.append({
        "agent": "Translation Agent",
        "step": "Semantic comparison complete",
        "detail": f"Found {len(translation_result.get('discrepancies', []))} discrepancies",
        "status": "success" if not translation_result.get("discrepancies") else "warning",
    })

    # Step 3: Vision Agent - Layout & formatting compliance
    agent_log.append({
        "agent": "Vision Agent",
        "step": "Layout analysis",
        "detail": "Checking font sizes, warning placement, regulatory elements...",
        "status": "running",
    })

    layout_result = vision_agent.analyze_layout_compliance(
        file_b64, file_type, target_language
    )

    agent_log.append({
        "agent": "Vision Agent",
        "step": "Layout analysis complete",
        "detail": f"Found {len(layout_result.get('issues', []))} layout issues",
        "status": "success" if not layout_result.get("issues") else "warning",
    })

    # Calculate overall compliance score
    translation_score = translation_result.get("semantic_score", 100)
    layout_score = layout_result.get("layout_score", 100)
    overall_score = (translation_score * 0.6) + (layout_score * 0.4)

    if overall_score >= 90:
        overall_status = "compliant"
    elif overall_score >= 70:
        overall_status = "needs_review"
    else:
        overall_status = "non_compliant"

    agent_log.append({
        "agent": "Orchestrator",
        "step": "Analysis complete",
        "detail": f"Overall compliance score: {overall_score:.1f}%",
        "status": "success",
    })

    return ComplianceResult(
        overall_status=overall_status,
        compliance_score=round(overall_score, 1),
        translation_analysis=translation_result,
        vision_analysis=layout_result,
        agent_log=agent_log,
        summary=f"Packaging review complete. Score: {overall_score:.1f}%. "
                f"Translation integrity: {translation_score:.1f}%. "
                f"Layout compliance: {layout_score:.1f}%.",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
