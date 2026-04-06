/**
 * ReviewQueue — Human-in-the-loop approval workflow page.
 *
 * Lists analysis jobs awaiting human review with approve/reject actions.
 * Accessible to: qa_reviewer, regulatory_affairs, admin roles.
 *
 * To add to app routing:
 *   import ReviewQueue from "./pages/ReviewQueue";
 *   // Add a route or navigation link in App.jsx
 */

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";

const STATUS_COLORS = {
  compliant:     "#00e5a0",
  needs_review:  "#f5a623",
  non_compliant: "#ff4444",
};

const WORKFLOW_LABELS = {
  draft:        { label: "Draft",        color: "#888" },
  ai_reviewed:  { label: "AI Reviewed",  color: "#4a9eff" },
  human_review: { label: "Needs Review", color: "#f5a623" },
  approved:     { label: "Approved",     color: "#00e5a0" },
  rejected:     { label: "Rejected",     color: "#ff4444" },
};

function Badge({ state }) {
  const cfg = WORKFLOW_LABELS[state] || { label: state, color: "#888" };
  return (
    <span style={{
      fontSize: 10, fontFamily: "monospace", textTransform: "uppercase",
      letterSpacing: "0.08em", color: cfg.color,
      border: `1px solid ${cfg.color}`,
      borderRadius: 4, padding: "2px 6px",
    }}>
      {cfg.label}
    </span>
  );
}

function ScorePill({ score, status }) {
  const color = STATUS_COLORS[status] || "#888";
  return (
    <span style={{
      fontSize: 12, fontFamily: "monospace", fontWeight: 700,
      color, background: `${color}22`,
      borderRadius: 12, padding: "2px 10px",
    }}>
      {score != null ? `${score.toFixed(0)}%` : "—"}
    </span>
  );
}

export default function ReviewQueue() {
  const [jobs, setJobs]             = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [filter, setFilter]         = useState("human_review");
  const [selectedJob, setSelectedJob] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [rejectComment, setRejectComment] = useState("");
  const [actionDialog, setActionDialog]   = useState(null); // "approve" | "reject"

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = filter ? `?workflow_state=${filter}` : "";
      const res = await fetch(`/api/jobs${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setJobs(await res.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);

  const handleApprove = async (jobId, comment) => {
    setActionLoading(true);
    try {
      const res = await fetch(`/api/jobs/${jobId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment }),
      });
      if (!res.ok) throw new Error((await res.json()).detail);
      setActionDialog(null);
      await fetchJobs();
    } catch (err) {
      alert(`Approval failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (jobId, comment) => {
    if (!comment.trim()) { alert("A rejection comment is required."); return; }
    setActionLoading(true);
    try {
      const res = await fetch(`/api/jobs/${jobId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment }),
      });
      if (!res.ok) throw new Error((await res.json()).detail);
      setActionDialog(null);
      setRejectComment("");
      await fetchJobs();
    } catch (err) {
      alert(`Rejection failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 16px", fontFamily: "system-ui, sans-serif" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, color: "#e0e8ff", fontSize: 22 }}>Review Queue</h2>
          <p style={{ margin: "4px 0 0", color: "#8899bb", fontSize: 13 }}>Human-in-the-loop approval for AI compliance findings</p>
        </div>
        <button onClick={fetchJobs} style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid #2a3560", background: "#12274e", color: "#8899bb", cursor: "pointer", fontSize: 12 }}>
          ↻ Refresh
        </button>
      </div>

      {/* Filter chips */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {[["human_review", "Needs Review"], ["ai_reviewed", "AI Reviewed"], ["approved", "Approved"], ["rejected", "Rejected"], [null, "All"]].map(([val, label]) => (
          <button
            key={label}
            onClick={() => setFilter(val)}
            style={{
              padding: "5px 14px", borderRadius: 20, fontSize: 12, cursor: "pointer",
              border: `1px solid ${filter === val ? "#00e5a0" : "#2a3560"}`,
              background: filter === val ? "rgba(0,229,160,0.1)" : "#0d1b3e",
              color: filter === val ? "#00e5a0" : "#8899bb",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Job list */}
      {loading && <p style={{ color: "#8899bb" }}>Loading...</p>}
      {error && <p style={{ color: "#ff4444" }}>Error: {error}</p>}
      {!loading && !error && jobs.length === 0 && (
        <p style={{ color: "#8899bb", textAlign: "center", padding: "40px 0" }}>No jobs in this queue.</p>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {jobs.map(job => (
          <motion.div
            key={job.job_id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              background: "#0d1b3e",
              border: "1px solid #1e2f5e",
              borderRadius: 10,
              padding: "14px 18px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 16,
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                <span style={{ fontFamily: "monospace", fontSize: 12, color: "#4a9eff" }}>{job.job_id.slice(0, 8)}…</span>
                <Badge state={job.workflow_state} />
                {job.compliance_score != null && (
                  <ScorePill score={job.compliance_score} status={job.overall_status} />
                )}
              </div>
              <div style={{ color: "#c8d8f0", fontSize: 14 }}>
                {job.target_language} · {job.overall_status?.replace("_", " ") || "pending"}
              </div>
              <div style={{ color: "#4a6090", fontSize: 11, marginTop: 2 }}>
                Submitted: {job.created_at ? new Date(job.created_at).toLocaleString() : "—"}
              </div>
            </div>

            {job.workflow_state === "human_review" || job.workflow_state === "ai_reviewed" ? (
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => { setSelectedJob(job); setActionDialog("approve"); }}
                  style={{ padding: "6px 16px", borderRadius: 6, border: "1px solid #00e5a0", background: "rgba(0,229,160,0.1)", color: "#00e5a0", cursor: "pointer", fontSize: 13 }}
                >
                  ✓ Approve
                </button>
                <button
                  onClick={() => { setSelectedJob(job); setActionDialog("reject"); setRejectComment(""); }}
                  style={{ padding: "6px 16px", borderRadius: 6, border: "1px solid #ff4444", background: "rgba(255,68,68,0.1)", color: "#ff4444", cursor: "pointer", fontSize: 13 }}
                >
                  ✗ Reject
                </button>
              </div>
            ) : (
              <span style={{ color: WORKFLOW_LABELS[job.workflow_state]?.color || "#888", fontSize: 12, fontFamily: "monospace" }}>
                {WORKFLOW_LABELS[job.workflow_state]?.label || job.workflow_state}
              </span>
            )}
          </motion.div>
        ))}
      </div>

      {/* Approve dialog */}
      <AnimatePresence>
        {actionDialog === "approve" && selectedJob && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}
            onClick={() => setActionDialog(null)}
          >
            <motion.div
              initial={{ scale: 0.95 }} animate={{ scale: 1 }} exit={{ scale: 0.95 }}
              onClick={e => e.stopPropagation()}
              style={{ background: "#0d1b3e", border: "1px solid #1e2f5e", borderRadius: 12, padding: 28, width: 420 }}
            >
              <h3 style={{ margin: "0 0 12px", color: "#00e5a0" }}>Approve Analysis</h3>
              <p style={{ color: "#8899bb", fontSize: 13, margin: "0 0 16px" }}>
                Job <code style={{ color: "#4a9eff" }}>{selectedJob.job_id.slice(0, 8)}</code> — {selectedJob.target_language}
              </p>
              <textarea
                placeholder="Optional comment..."
                value={rejectComment}
                onChange={e => setRejectComment(e.target.value)}
                rows={3}
                style={{ width: "100%", background: "#0a1430", border: "1px solid #2a3560", color: "#c8d8f0", borderRadius: 6, padding: 10, fontSize: 13, resize: "vertical", boxSizing: "border-box" }}
              />
              <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 16 }}>
                <button onClick={() => setActionDialog(null)} style={{ padding: "7px 16px", borderRadius: 6, border: "1px solid #2a3560", background: "transparent", color: "#8899bb", cursor: "pointer" }}>Cancel</button>
                <button
                  onClick={() => handleApprove(selectedJob.job_id, rejectComment)}
                  disabled={actionLoading}
                  style={{ padding: "7px 20px", borderRadius: 6, border: "none", background: "#00e5a0", color: "#0a1430", fontWeight: 700, cursor: "pointer" }}
                >
                  {actionLoading ? "Approving…" : "Confirm Approval"}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}

        {actionDialog === "reject" && selectedJob && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}
            onClick={() => setActionDialog(null)}
          >
            <motion.div
              initial={{ scale: 0.95 }} animate={{ scale: 1 }} exit={{ scale: 0.95 }}
              onClick={e => e.stopPropagation()}
              style={{ background: "#0d1b3e", border: "1px solid #1e2f5e", borderRadius: 12, padding: 28, width: 420 }}
            >
              <h3 style={{ margin: "0 0 12px", color: "#ff4444" }}>Reject Analysis</h3>
              <p style={{ color: "#8899bb", fontSize: 13, margin: "0 0 16px" }}>
                Job <code style={{ color: "#4a9eff" }}>{selectedJob.job_id.slice(0, 8)}</code> — {selectedJob.target_language}
              </p>
              <textarea
                placeholder="Rejection reason (required)..."
                value={rejectComment}
                onChange={e => setRejectComment(e.target.value)}
                rows={4}
                style={{ width: "100%", background: "#0a1430", border: "1px solid #ff444455", color: "#c8d8f0", borderRadius: 6, padding: 10, fontSize: 13, resize: "vertical", boxSizing: "border-box" }}
              />
              <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 16 }}>
                <button onClick={() => setActionDialog(null)} style={{ padding: "7px 16px", borderRadius: 6, border: "1px solid #2a3560", background: "transparent", color: "#8899bb", cursor: "pointer" }}>Cancel</button>
                <button
                  onClick={() => handleReject(selectedJob.job_id, rejectComment)}
                  disabled={actionLoading || !rejectComment.trim()}
                  style={{ padding: "7px 20px", borderRadius: 6, border: "none", background: "#ff4444", color: "#fff", fontWeight: 700, cursor: "pointer", opacity: !rejectComment.trim() ? 0.5 : 1 }}
                >
                  {actionLoading ? "Rejecting…" : "Confirm Rejection"}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
