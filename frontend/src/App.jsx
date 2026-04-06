import { useState, useCallback, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import UploadZone from "./components/UploadZone";
import ComplianceReport from "./components/ComplianceReport";
import AgentLog from "./components/AgentLog";
import PDFViewer from "./components/PDFViewer";
import DiffView from "./components/DiffView";
import { exportComplianceReport } from "./utils/exportReport";

// ── Master label presets ──────────────────────────────────────────────────────
const MASTER_LABEL_EN = `IBUPROFEN 400mg Film-coated Tablets

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

// Simulated agent log stages used while request is in-flight
const LOADING_STAGES = [
  { agent: "Orchestrator",       step: "Initialising agents",        detail: "Starting Vision Agent and Translation Agent pipelines...",          status: "info" },
  { agent: "Vision Agent",       step: "Text extraction",            detail: "Scanning packaging artwork with multimodal LLM...",                  status: "running" },
  { agent: "Vision Agent",       step: "OCR complete",               detail: "Extracted text from packaging image.",                               status: "success" },
  { agent: "Translation Agent",  step: "Back-translation",           detail: "Translating regional text → English for semantic comparison...",     status: "running" },
  { agent: "Translation Agent",  step: "Semantic comparison",        detail: "Comparing medical intent across sections...",                        status: "running" },
  { agent: "Vision Agent",       step: "Layout analysis",            detail: "Checking font sizes, warning placement, regulatory elements...",     status: "running" },
  { agent: "Vision Agent",       step: "Layout analysis complete",   detail: "Regulatory element positions verified.",                             status: "success" },
  { agent: "Translation Agent",  step: "Scoring complete",           detail: "Semantic score calculated. Discrepancies identified.",               status: "warning" },
  { agent: "Orchestrator",       step: "Finalising report",          detail: "Combining agent results into compliance report...",                  status: "info" },
];

// Animated score counter hook
function useCountUp(target, duration = 1200) {
  const [displayed, setDisplayed] = useState(0);
  const raf = useRef(null);

  useEffect(() => {
    if (target === null || target === undefined) { setDisplayed(0); return; }
    const start = performance.now();
    const animate = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayed(Math.round(eased * target));
      if (progress < 1) raf.current = requestAnimationFrame(animate);
    };
    raf.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration]);

  return displayed;
}

export default function App() {
  const [masterLabel, setMasterLabel]       = useState(MASTER_LABEL_EN);
  const [targetLanguage, setTargetLanguage] = useState("French");
  const [uploadedFile, setUploadedFile]     = useState(null);
  const [uploadedFileUrl, setUploadedFileUrl] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [agentLog, setAgentLog]             = useState([]);
  const [isAnalyzing, setIsAnalyzing]       = useState(false);
  const [activeTab, setActiveTab]           = useState("report");
  const [apiError, setApiError]             = useState(null);
  const [isExporting, setIsExporting]       = useState(false);

  const streamTimers = useRef([]);
  const displayedScore = useCountUp(analysisResult?.compliance_score ?? null);

  // ── Simulated streaming log while request is in-flight ──────────────────
  const startStreamingLog = () => {
    streamTimers.current.forEach(clearTimeout);
    streamTimers.current = [];
    setAgentLog([]);
    LOADING_STAGES.forEach((stage, i) => {
      const t = setTimeout(() => {
        setAgentLog(prev => [...prev, { ...stage, timestamp: new Date().toISOString() }]);
      }, i * 2200);
      streamTimers.current.push(t);
    });
  };

  const stopStreamingLog = () => {
    streamTimers.current.forEach(clearTimeout);
    streamTimers.current = [];
  };

  // ── Demo presets ──────────────────────────────────────────────────────────
  const applyFrenchPreset = () => {
    setMasterLabel(MASTER_LABEL_EN);
    setTargetLanguage("French");
    setAnalysisResult(null);
    setAgentLog([]);
    setApiError(null);
  };

  const applyJapanesePreset = () => {
    setMasterLabel(MASTER_LABEL_EN);
    setTargetLanguage("Japanese");
    setAnalysisResult(null);
    setAgentLog([]);
    setApiError(null);
  };

  const handleFileDrop = useCallback((file) => {
    setUploadedFile(file);
    setUploadedFileUrl(URL.createObjectURL(file));
    setAnalysisResult(null);
    setAgentLog([]);
    setApiError(null);
  }, []);

  // ── Main analysis request ─────────────────────────────────────────────────
  const handleAnalyze = async () => {
    if (!uploadedFile || !masterLabel.trim()) return;

    setIsAnalyzing(true);
    setApiError(null);
    setAnalysisResult(null);
    startStreamingLog();

    const formData = new FormData();
    formData.append("master_label", masterLabel);
    formData.append("target_language", targetLanguage);
    formData.append("packaging_pdf", uploadedFile);

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Analysis failed");
      }

      const result = await response.json();
      stopStreamingLog();
      setAnalysisResult(result);
      setAgentLog(result.agent_log || []);
      setActiveTab("report");
    } catch (err) {
      stopStreamingLog();
      setApiError(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleExport = async () => {
    if (!analysisResult || isExporting) return;
    setIsExporting(true);
    try {
      await exportComplianceReport(analysisResult, targetLanguage);
    } finally {
      setIsExporting(false);
    }
  };

  const statusColor = analysisResult
    ? { compliant: "#00e5a0", needs_review: "#f5a623", non_compliant: "#ff4444" }[analysisResult.overall_status] || "#888"
    : null;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-icon">⊕</div>
          <div>
            <h1>PHARMA<span className="brand-accent">GUARD</span></h1>
            <p className="brand-sub">Multilingual Packaging Compliance Agent</p>
          </div>
        </div>
        <div className="header-meta">
          <span className="badge badge-live">● LIVE DEMO</span>
          <span className="badge">Powered by Claude Sonnet</span>
        </div>
      </header>

      <main className="app-main">
        {/* ── Left Panel ── */}
        <section className="panel panel-left">

          {/* Demo quick-select chips */}
          <div className="panel-section">
            <label className="section-label">DEMO PRESETS</label>
            <div className="preset-chips">
              <button className="preset-chip preset-chip-fr" onClick={applyFrenchPreset} title="Sets language to French — upload ibuprofen_french_NONCOMPLIANT.png">
                🇫🇷 French Demo
              </button>
              <button className="preset-chip preset-chip-ja" onClick={applyJapanesePreset} title="Sets language to Japanese — upload ibuprofen_japanese_NONCOMPLIANT.png">
                🇯🇵 Japanese Demo
              </button>
            </div>
          </div>

          <div className="panel-section">
            <label className="section-label">SOURCE OF TRUTH — MASTER ENGLISH LABEL</label>
            <textarea
              className="master-label-input"
              value={masterLabel}
              onChange={(e) => setMasterLabel(e.target.value)}
              rows={14}
              placeholder="Paste the approved English master label text here..."
            />
          </div>

          <div className="panel-section">
            <label className="section-label">TARGET LANGUAGE</label>
            <select
              className="lang-select"
              value={targetLanguage}
              onChange={(e) => setTargetLanguage(e.target.value)}
            >
              {["French","German","Japanese","Spanish","Portuguese","Arabic","Chinese","Russian","Italian","Korean"].map(l => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>

          <div className="panel-section">
            <label className="section-label">REGIONAL PACKAGING ARTWORK</label>
            <UploadZone onFileDrop={handleFileDrop} uploadedFile={uploadedFile} />
          </div>

          <button
            className={`analyze-btn ${isAnalyzing ? "analyzing" : ""} ${!uploadedFile ? "disabled" : ""}`}
            onClick={handleAnalyze}
            disabled={isAnalyzing || !uploadedFile}
          >
            {isAnalyzing ? (
              <span className="btn-content"><span className="spinner" />RUNNING AGENTS...</span>
            ) : (
              <span className="btn-content">⊛ RUN COMPLIANCE CHECK</span>
            )}
          </button>

          {apiError && (
            <div className="error-banner">
              <strong>⚠ Error:</strong> {apiError}
            </div>
          )}
        </section>

        {/* ── Right Panel ── */}
        <section className="panel panel-right">
          {analysisResult ? (
            <>
              <div className="score-header" style={{ "--status-color": statusColor }}>
                <div className="score-ring">
                  <svg viewBox="0 0 100 100" className="score-svg">
                    <circle cx="50" cy="50" r="42" fill="none" stroke="#1a1f2e" strokeWidth="8" />
                    <circle
                      cx="50" cy="50" r="42" fill="none"
                      stroke={statusColor} strokeWidth="8"
                      strokeDasharray={`${(analysisResult.compliance_score / 100) * 264} 264`}
                      strokeLinecap="round"
                      transform="rotate(-90 50 50)"
                    />
                  </svg>
                  <div className="score-value">{displayedScore}</div>
                </div>
                <div className="score-meta">
                  <div className="score-status" style={{ color: statusColor }}>
                    {analysisResult.overall_status.replace("_", " ").toUpperCase()}
                  </div>
                  <div className="score-lang">{targetLanguage} packaging vs. English master</div>
                  <div className="score-summary">{analysisResult.summary}</div>
                  <button
                    className={`export-btn ${isExporting ? "exporting" : ""}`}
                    onClick={handleExport}
                    disabled={isExporting}
                    title="Download compliance report as PDF"
                  >
                    {isExporting ? "Exporting..." : "↓ Export Report"}
                  </button>
                </div>
              </div>

              <div className="tabs">
                {[
                  { id: "report", label: "📋 Report" },
                  { id: "diff",   label: "📊 Text Diff" },
                  { id: "pdf",    label: "📄 Artwork" },
                  { id: "log",    label: "🤖 Agent Log" },
                ].map(tab => (
                  <button
                    key={tab.id}
                    className={`tab-btn ${activeTab === tab.id ? "active" : ""}`}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <div className="tab-content">
                {activeTab === "report" && (
                  <div id="compliance-report-export">
                    <ComplianceReport result={analysisResult} />
                  </div>
                )}
                {activeTab === "diff" && (
                  <DiffView result={analysisResult} />
                )}
                {activeTab === "pdf" && (
                  <PDFViewer
                    fileUrl={uploadedFileUrl}
                    fileType={uploadedFile?.type}
                    result={analysisResult}
                  />
                )}
                {activeTab === "log" && (
                  <AgentLog log={agentLog} />
                )}
              </div>
            </>
          ) : (
            <div className="empty-state">
              {isAnalyzing ? (
                <motion.div className="analyzing-state" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <div className="pulse-ring" />
                  <p>Agents running...</p>
                  <AgentLog log={agentLog} mini />
                </motion.div>
              ) : (
                <div className="idle-state">
                  <div className="idle-icon">⊕</div>
                  <p>Upload packaging artwork and run compliance check</p>
                  <p className="idle-sub">Use a demo preset above, then upload the matching PNG from demo/sample_labels/</p>
                </div>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
