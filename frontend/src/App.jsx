import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import UploadZone from "./components/UploadZone";
import ComplianceReport from "./components/ComplianceReport";
import AgentLog from "./components/AgentLog";
import PDFViewer from "./components/PDFViewer";

const MASTER_LABEL_PLACEHOLDER = `IBUPROFEN 400mg Film-coated Tablets

ACTIVE INGREDIENT: Ibuprofen 400mg per tablet

INDICATIONS: For the relief of mild to moderate pain including headache,
dental pain, period pain, back pain. Symptomatic relief of osteoarthritis
and rheumatoid arthritis. Reduction of fever.

DOSAGE: Adults and children 12 years+: 1-2 tablets up to 3 times daily.
Do not exceed 6 tablets (2400mg) in 24 hours.

WARNINGS:
⚠ Do not use if allergic to ibuprofen, aspirin or other NSAIDs.
⚠ Not recommended in patients with renal impairment (CrCl <30 mL/min).
⚠ Increased risk of serious cardiovascular thrombotic events at higher doses.
⚠ Contains lactose. Consult doctor if lactose intolerant.
⚠ Do not use during last 3 months of pregnancy.

CONTRAINDICATIONS: Active peptic ulcer, severe hepatic failure,
severe renal failure, severe heart failure.

STORAGE: Store below 25°C. Keep out of reach of children.
Keep in original packaging to protect from moisture.

MANUFACTURER: Viatris Pharmaceuticals Ltd.
Batch/Lot: See base of pack. Expiry: See base of pack.`;

const LANGUAGES = [
  "French","German","Japanese","Spanish","Portuguese",
  "Arabic","Chinese","Russian","Italian","Korean",
];

const STATUS_COLORS = {
  compliant:     { color: "#00e5a0", bg: "rgba(0,229,160,0.08)",   border: "rgba(0,229,160,0.28)" },
  needs_review:  { color: "#f5a623", bg: "rgba(245,166,35,0.08)",  border: "rgba(245,166,35,0.28)" },
  non_compliant: { color: "#ff4444", bg: "rgba(255,68,68,0.08)",   border: "rgba(255,68,68,0.28)" },
};

// ── Score Ring ───────────────────────────────────────────────
function ScoreRing({ score, color }) {
  const R = 42;
  const circ = 2 * Math.PI * R;
  const filled = (score / 100) * circ;

  return (
    <div style={{ position: "relative", width: 104, height: 104, flexShrink: 0 }}>
      <svg
        viewBox="0 0 100 100"
        style={{ width: "100%", height: "100%", transform: "rotate(-90deg)", overflow: "visible" }}
      >
        <defs>
          <filter id="ring-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="3.5" result="blurred" />
            <feMerge>
              <feMergeNode in="blurred" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        {/* Track */}
        <circle cx="50" cy="50" r={R} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="9" />
        {/* Progress */}
        <motion.circle
          cx="50" cy="50" r={R}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          filter="url(#ring-glow)"
          initial={{ strokeDasharray: `0 ${circ}` }}
          animate={{ strokeDasharray: `${filled} ${circ}` }}
          transition={{ duration: 1.4, ease: [0.4, 0, 0.2, 1] }}
        />
      </svg>
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: "var(--font-mono)",
        fontSize: 26, fontWeight: 700,
        color,
        textShadow: `0 0 18px ${color}`,
        letterSpacing: "-0.02em",
      }}>
        {Math.round(score)}
      </div>
    </div>
  );
}

// ── Tab icons ────────────────────────────────────────────────
function ReportIcon() {
  return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><rect x="1" y="1" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><path d="M3 4h6M3 6h6M3 8h4" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/></svg>;
}
function ArtworkIcon() {
  return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><rect x="1" y="1" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><path d="M1 8.5l2.5-3 2 2 2-3L11 8.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}
function LogIcon() {
  return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><rect x="1" y="1" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><path d="M3 4l1.5 1.5L3 7M6 7h3" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

// ── Main App ─────────────────────────────────────────────────
export default function App() {
  const [masterLabel, setMasterLabel]   = useState(MASTER_LABEL_PLACEHOLDER);
  const [targetLanguage, setTargetLanguage] = useState("French");
  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploadedFileUrl, setUploadedFileUrl] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [agentLog, setAgentLog]         = useState([]);
  const [isAnalyzing, setIsAnalyzing]   = useState(false);
  const [activeTab, setActiveTab]       = useState("report");
  const [apiError, setApiError]         = useState(null);

  const handleFileDrop = useCallback((file) => {
    setUploadedFile(file);
    setUploadedFileUrl(URL.createObjectURL(file));
    setAnalysisResult(null);
    setAgentLog([]);
    setApiError(null);
  }, []);

  const handleAnalyze = async () => {
    if (!uploadedFile || !masterLabel.trim()) return;
    setIsAnalyzing(true);
    setApiError(null);
    setAgentLog([]);
    setAnalysisResult(null);

    const formData = new FormData();
    formData.append("master_label", masterLabel);
    formData.append("target_language", targetLanguage);
    formData.append("packaging_pdf", uploadedFile);

    try {
      const response = await fetch("http://localhost:8000/api/analyze", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Analysis failed");
      }
      const result = await response.json();
      setAnalysisResult(result);
      setAgentLog(result.agent_log || []);
      setActiveTab("report");
    } catch (err) {
      setApiError(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const status    = analysisResult?.overall_status;
  const statusCfg = STATUS_COLORS[status] || {};

  const TABS = [
    { id: "report",  label: "Report",    icon: <ReportIcon /> },
    { id: "pdf",     label: "Artwork",   icon: <ArtworkIcon /> },
    { id: "log",     label: "Agent Log", icon: <LogIcon /> },
  ];

  return (
    <div className="app-shell">

      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-icon">
            <svg width="19" height="19" viewBox="0 0 19 19" fill="none">
              <path d="M9.5 1.5v16M1.5 9.5h16" stroke="#00e5a0" strokeWidth="1.4" strokeLinecap="round"/>
              <circle cx="9.5" cy="9.5" r="3.5" fill="none" stroke="#00e5a0" strokeWidth="1.4"/>
              <circle cx="9.5" cy="9.5" r="7" fill="none" stroke="rgba(0,229,160,0.28)" strokeWidth="1"/>
            </svg>
          </div>
          <div>
            <h1>PHARMA<span className="brand-accent">GUARD</span></h1>
            <p className="brand-sub">Multilingual Packaging Compliance Agent</p>
          </div>
        </div>
        <div className="header-meta">
          <span className="badge badge-live">
            <span className="badge-live-dot" />
            LIVE DEMO
          </span>
          <span className="badge">claude-sonnet-4</span>
        </div>
      </header>

      {/* ── Main Grid ── */}
      <div className="app-main">

        {/* Left Panel */}
        <aside className="panel panel-left">
          {/* Master Label */}
          <div>
            <div className="section-label">
              <div className="section-label-dot" />
              <span className="section-label-text">SOURCE OF TRUTH — MASTER ENGLISH LABEL</span>
            </div>
            <textarea
              className="master-label-input"
              value={masterLabel}
              onChange={(e) => setMasterLabel(e.target.value)}
              rows={13}
              placeholder="Paste the approved English master label text here..."
            />
          </div>

          {/* Language */}
          <div>
            <div className="section-label">
              <div className="section-label-dot" />
              <span className="section-label-text">TARGET LANGUAGE</span>
            </div>
            <div className="lang-select-wrap">
              <select
                className="lang-select"
                value={targetLanguage}
                onChange={(e) => setTargetLanguage(e.target.value)}
              >
                {LANGUAGES.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
              <div className="lang-select-chevron">
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <path d="M2.5 5l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
            </div>
          </div>

          {/* Upload */}
          <div>
            <div className="section-label">
              <div className="section-label-dot" />
              <span className="section-label-text">REGIONAL PACKAGING ARTWORK</span>
            </div>
            <UploadZone onFileDrop={handleFileDrop} uploadedFile={uploadedFile} />
          </div>

          <div style={{ flex: 1 }} />

          {/* CTA */}
          <button
            className={`analyze-btn${isAnalyzing ? " analyzing" : ""}${!uploadedFile ? " disabled" : ""}`}
            onClick={handleAnalyze}
            disabled={isAnalyzing || !uploadedFile}
          >
            {isAnalyzing ? (
              <span className="btn-content">
                <span className="spinner" />
                RUNNING AGENTS…
              </span>
            ) : (
              <span className="btn-content">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.5"/>
                  <path d="M4.5 7l2.5 2.5 3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                RUN COMPLIANCE CHECK
              </span>
            )}
          </button>

          {apiError && (
            <div className="error-banner">
              <strong>⚠ Error:</strong> {apiError}
            </div>
          )}
        </aside>

        {/* Right Panel */}
        <main className="panel panel-right">
          {analysisResult ? (
            <>
              {/* Score Card */}
              <motion.div
                className="score-card"
                style={{
                  "--status-color":  statusCfg.color,
                  "--status-bg":     statusCfg.bg,
                  "--status-border": statusCfg.border,
                }}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <div
                  className="score-card-glow"
                  style={{ background: statusCfg.color }}
                />

                <ScoreRing
                  score={analysisResult.compliance_score}
                  color={statusCfg.color}
                />

                <div className="score-meta">
                  <div className="status-badge">
                    <span className="status-dot" style={{ background: statusCfg.color, boxShadow: `0 0 6px ${statusCfg.color}` }} />
                    <span className="status-label">
                      {status?.replace(/_/g, " ").toUpperCase()}
                    </span>
                  </div>
                  <div className="score-lang">{targetLanguage} packaging vs. English master</div>
                  <div className="score-summary">{analysisResult.summary}</div>

                  <div className="mini-scores">
                    <div className="mini-score">
                      <div className="mini-score-label">TRANSLATION</div>
                      <div className="mini-score-value">
                        {analysisResult.translation_analysis?.semantic_score?.toFixed(1)}%
                      </div>
                    </div>
                    <div className="mini-score">
                      <div className="mini-score-label">LAYOUT</div>
                      <div className="mini-score-value">
                        {analysisResult.vision_analysis?.layout_score?.toFixed(1)}%
                      </div>
                    </div>
                    <div className="mini-score">
                      <div className="mini-score-label">FLAGS</div>
                      <div className="mini-score-value red">
                        {(analysisResult.translation_analysis?.discrepancies?.length ?? 0) +
                         (analysisResult.vision_analysis?.issues?.length ?? 0)}
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>

              {/* Tab Switcher */}
              <div className="tabs">
                {TABS.map((tab) => (
                  <button
                    key={tab.id}
                    className={`tab-btn${activeTab === tab.id ? " active" : ""}`}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.icon}
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="tab-content">
                <AnimatePresence mode="wait">
                  {activeTab === "report" && (
                    <motion.div key="report" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      <ComplianceReport result={analysisResult} />
                    </motion.div>
                  )}
                  {activeTab === "pdf" && (
                    <motion.div key="pdf" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      <PDFViewer fileUrl={uploadedFileUrl} result={analysisResult} />
                    </motion.div>
                  )}
                  {activeTab === "log" && (
                    <motion.div key="log" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      <AgentLog log={agentLog} />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </>
          ) : (
            <div className="empty-state">
              {isAnalyzing ? (
                <motion.div
                  className="analyzing-state"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  <div className="pulse-ring" />
                  <p className="analyzing-label">Agents running…</p>
                  <AgentLog log={agentLog} mini />
                </motion.div>
              ) : (
                <div className="idle-state">
                  <div className="idle-icon">
                    <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                      <path d="M14 4v20M4 14h20" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" strokeLinecap="round"/>
                      <circle cx="14" cy="14" r="5" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="1.5"/>
                      <circle cx="14" cy="14" r="10" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="1"/>
                    </svg>
                  </div>
                  <p className="idle-title">Upload packaging artwork and run compliance check</p>
                  <p className="idle-sub">Translation Agent + Vision Agent will analyze in parallel</p>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
