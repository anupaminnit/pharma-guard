"""
Veeva Vault integration stub.

Veeva Vault is the pharmaceutical industry-standard document management system
(DMS). Baxter uses it to store packaging artwork PDFs and manage their lifecycle.

Two integration modes:
  1. Pull (scheduled): Cron queries Vault for documents in "Artwork Review"
     lifecycle state → download → enqueue compliance analysis → write results back.
  2. Push (webhook): Vault triggers POST /api/webhook/veeva when a document
     enters the review lifecycle state.

Authentication: Veeva uses short-lived session tokens (24h). The client handles
automatic token refresh.

Required env vars:
    VEEVA_VAULT_URL      — e.g. https://baxter.veevavault.com
    VEEVA_USERNAME       — service account username
    VEEVA_PASSWORD       — service account password
    VEEVA_CLIENT_ID      — application client ID registered in Vault

All HTTP calls use httpx.AsyncClient to avoid blocking the FastAPI event loop.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

VAULT_URL   = os.environ.get("VEEVA_VAULT_URL", "")
USERNAME    = os.environ.get("VEEVA_USERNAME", "")
PASSWORD    = os.environ.get("VEEVA_PASSWORD", "")
CLIENT_ID   = os.environ.get("VEEVA_CLIENT_ID", "pharma-guard")
API_VERSION = "v21.2"


class VeevaVaultClient:
    """
    Async Veeva Vault API client with automatic session token refresh.

    Usage:
        async with VeevaVaultClient() as vault:
            pdf_bytes = await vault.get_document_file(doc_id, major_ver, minor_ver)
            await vault.update_document_field(doc_id, "Compliance_Status__c", "ai_reviewed")
    """

    def __init__(self) -> None:
        self._base = f"{VAULT_URL}/api/{API_VERSION}"
        self._session_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._http: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._http = httpx.AsyncClient(timeout=60.0)
        await self._ensure_authenticated()
        return self

    async def __aexit__(self, *args):
        if self._http:
            await self._http.aclose()

    async def _ensure_authenticated(self) -> None:
        """Obtain or refresh session token."""
        if self._session_token and self._token_expiry and datetime.now(timezone.utc) < self._token_expiry:
            return

        resp = await self._http.post(
            f"{self._base}/auth",
            data={
                "username": USERNAME,
                "password": PASSWORD,
                "client_id": CLIENT_ID,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("responseStatus") != "SUCCESS":
            errors = data.get("errors", [])
            raise RuntimeError(f"Veeva auth failed: {errors}")

        self._session_token = data["sessionId"]
        # Vault session tokens are valid for 24h
        self._token_expiry = datetime.now(timezone.utc) + timedelta(hours=23)

    def _headers(self) -> dict:
        return {
            "Authorization": self._session_token,
            "Accept": "application/json",
        }

    # ── Document retrieval ────────────────────────────────────────────────────

    async def get_document_metadata(self, document_id: str) -> dict:
        """
        Retrieve document metadata including lifecycle state, version, and custom fields.

        Returns dict with keys: id, name, version_id, lifecycle_state__v,
        Compliance_Status__c, last_modified_date__v, etc.
        """
        await self._ensure_authenticated()
        resp = await self._http.get(
            f"{self._base}/objects/documents/{document_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("responseStatus") != "SUCCESS":
            raise RuntimeError(f"Failed to get document {document_id}: {data.get('errors')}")
        return data.get("document", {})

    async def get_document_file(
        self,
        document_id: str,
        major_version: int = 0,
        minor_version: int = 1,
    ) -> bytes:
        """
        Download the PDF file for a specific document version.
        Returns raw PDF bytes.
        """
        await self._ensure_authenticated()
        resp = await self._http.get(
            f"{self._base}/objects/documents/{document_id}/versions/{major_version}/{minor_version}/file",
            headers={**self._headers(), "Accept": "application/octet-stream"},
        )
        resp.raise_for_status()
        return resp.content

    async def list_documents_in_review(self, lifecycle_state: str = "Artwork Review") -> list[dict]:
        """
        Query Vault for documents currently in a specific lifecycle state.
        Used by the scheduled pull integration.

        Returns list of {id, name, lifecycle_state, last_modified_date}.
        """
        await self._ensure_authenticated()
        # VQL (Vault Query Language) query
        vql = f"SELECT id, name__v, lifecycle_state__v, last_modified_date__v FROM documents WHERE lifecycle_state__v = '{lifecycle_state}'"
        resp = await self._http.get(
            f"{self._base}/query",
            params={"q": vql},
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    # ── Write back results ────────────────────────────────────────────────────

    async def update_document_field(
        self,
        document_id: str,
        field_name: str,
        value: Any,
    ) -> None:
        """
        Update a custom field on a Vault document.

        Common fields:
            Compliance_Status__c  — "compliant" | "needs_review" | "non_compliant"
            AI_Score__c           — numeric compliance score
            Last_AI_Review__c     — timestamp
        """
        await self._ensure_authenticated()
        resp = await self._http.put(
            f"{self._base}/objects/documents/{document_id}",
            headers={**self._headers(), "Content-Type": "application/x-www-form-urlencoded"},
            data={field_name: str(value)},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("responseStatus") != "SUCCESS":
            raise RuntimeError(f"Failed to update field {field_name} on {document_id}: {data.get('errors')}")

    async def create_document_annotation(
        self,
        document_id: str,
        page_number: int,
        comment: str,
        color: str = "red",
        x: float = 0.1,
        y: float = 0.1,
    ) -> str:
        """
        Write a compliance finding back to Vault as a document annotation.
        Returns the annotation ID.

        Note: Vault annotation API requires the document to be in a lifecycle
        state that permits annotations (usually not "Approved").
        """
        await self._ensure_authenticated()
        resp = await self._http.post(
            f"{self._base}/objects/documents/{document_id}/annotations",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={
                "type__v": "note__v",
                "comment__v": comment,
                "page_number__v": page_number,
                "x_coordinate__v": x,
                "y_coordinate__v": y,
                "color__v": color,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("id", "")

    async def write_compliance_result(
        self,
        document_id: str,
        compliance_result: dict,
    ) -> None:
        """
        High-level helper: write full compliance result back to Vault.
        Updates custom fields and creates annotations for critical issues.
        """
        # Update summary fields
        await self.update_document_field(document_id, "Compliance_Status__c", compliance_result["overall_status"])
        await self.update_document_field(document_id, "AI_Compliance_Score__c", compliance_result["compliance_score"])
        await self.update_document_field(document_id, "Last_AI_Review__c", datetime.now(timezone.utc).isoformat())

        # Create an annotation for each critical discrepancy
        discrepancies = compliance_result.get("translation_analysis", {}).get("discrepancies", [])
        for disc in discrepancies:
            if disc.get("severity") in ("critical", "major"):
                await self.create_document_annotation(
                    document_id=document_id,
                    page_number=1,
                    comment=f"[PharmaGuard AI] {disc.get('severity', '').upper()}: {disc.get('description', '')}",
                    color="red" if disc.get("severity") == "critical" else "orange",
                )

    # ── Lifecycle transition ───────────────────────────────────────────────────

    async def transition_lifecycle(
        self,
        document_id: str,
        action: str,
    ) -> None:
        """
        Trigger a lifecycle action on a document.
        E.g. action="send_to_approval" moves document from Review → Approval.
        """
        await self._ensure_authenticated()
        resp = await self._http.put(
            f"{self._base}/objects/documents/{document_id}/lifecycle_actions/{action}",
            headers=self._headers(),
        )
        resp.raise_for_status()


# ── Webhook handler (to be registered in main.py) ────────────────────────────

async def handle_vault_webhook(payload: dict) -> dict:
    """
    Process a webhook event from Veeva Vault.

    Veeva sends a webhook when a document changes lifecycle state.
    This function extracts the document ID and enqueues a compliance analysis job.

    Register in main.py:
        @app.post("/api/webhook/veeva")
        async def veeva_webhook(payload: dict = Body(...)):
            return await handle_vault_webhook(payload)
    """
    from tasks.analysis_task import run_compliance_analysis
    import base64

    doc_id = payload.get("document_id") or payload.get("id")
    if not doc_id:
        return {"status": "ignored", "reason": "no document_id"}

    lifecycle_state = payload.get("lifecycle_state__v", "")
    if "review" not in lifecycle_state.lower():
        return {"status": "ignored", "reason": f"lifecycle state '{lifecycle_state}' not in review"}

    # Download the document from Vault
    async with VeevaVaultClient() as vault:
        metadata = await vault.get_document_metadata(doc_id)
        pdf_bytes = await vault.get_document_file(doc_id)

    # Enqueue analysis (master label would come from SKU table lookup)
    file_b64 = base64.b64encode(pdf_bytes).decode()
    import uuid
    run_compliance_analysis.delay(
        job_id=str(uuid.uuid4()),  # In production: create AnalysisJob row first
        master_label="",           # Lookup from SKU table by Veeva document_id
        target_language=metadata.get("language__v", "French"),
        file_bytes_b64=file_b64,
        file_type="application/pdf",
    )

    return {"status": "queued", "document_id": doc_id}
