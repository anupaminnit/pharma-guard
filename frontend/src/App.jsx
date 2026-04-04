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

export default function App() {
  const [masterLabel, setMasterLabel] = useState(MASTER_LABEL_PLACEHOLDER);
  const [targetLanguage, setTargetLanguage] = useState("French");
  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploadedFileUrl, setUploadedFileUrl] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [agentLog, setAgentLog] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeTab, setActiveTab] = useState("report");
  const [apiError, setApiError] = useState(null);

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

  const statusColor = analysisResult
    ? {
        compliant: "#00e5a0",
        needs_review: "#f5a623",
        non_compliant: "#ff4444",
      }[analysisResult.overall_status] || "#888"
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
          <span className="badge">Powered by Claude claude-sonnet-4-20250514</span>
        </div>
      </header>

      <main className="app-main">
        {/* Left Panel — Inputs */}
        <section className="panel panel-left">
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
              <span className="btn-content">
                <span className="spinner" />
                RUNNING AGENTS...
              </span>
            ) : (
              <span className="btn-content">
                ⊛ RUN COMPLIANCE CHECK
              </span>
            )}
          </button>

          {apiError && (
            <div className="error-banner">
              <strong>⚠ Error:</strong> {apiError}
            </div>
          )}
        </section>

        {/* Right Panel — Results */}
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
                  <div className="score-value">{analysisResult.compliance_score.toFixed(0)}</div>
                </div>
                <div className="score-meta">
                  <div className="score-status" style={{ color: statusColor }}>
                    {analysisResult.overall_status.replace("_", " ").toUpperCase()}
                  </div>
                  <div className="score-lang">{targetLanguage} packaging vs. English master</div>
                  <div className="score-summary">{analysisResult.summary}</div>
                </div>
              </div>

              <div className="tabs">
                {["report", "pdf", "log"].map(tab => (
                  <button
                    key={tab}
                    className={`tab-btn ${activeTab === tab ? "active" : ""}`}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab === "report" ? "📋 Report" : tab === "pdf" ? "📄 Artwork" : "🤖 Agent Log"}
                  </button>
                ))}
              </div>

              <div className="tab-content">
                {activeTab === "report" && (
                  <ComplianceReport result={analysisResult} />
                )}
                {activeTab === "pdf" && (
                  <PDFViewer fileUrl={uploadedFileUrl} result={analysisResult} />
                )}
                {activeTab === "log" && (
                  <AgentLog log={agentLog} />
                )}
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
                  <p>Agents running...</p>
                  <AgentLog log={agentLog} mini />
                </motion.div>
              ) : (
                <div className="idle-state">
                  <div className="idle-icon">⊕</div>
                  <p>Upload packaging artwork and run compliance check</p>
                  <p className="idle-sub">Translation Agent + Vision Agent will analyze in parallel</p>
                </div>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
