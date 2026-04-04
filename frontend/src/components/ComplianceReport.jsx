import { motion } from "framer-motion";

const severityConfig = {
  critical:    { color: "#ff4444", bg: "rgba(255,68,68,0.08)",    icon: "🔴", label: "CRITICAL" },
  major:       { color: "#ff8c00", bg: "rgba(255,140,0,0.08)",    icon: "🟠", label: "MAJOR" },
  minor:       { color: "#f5a623", bg: "rgba(245,166,35,0.08)",   icon: "🟡", label: "MINOR" },
  system_error:{ color: "#888",    bg: "rgba(136,136,136,0.08)",  icon: "⚙",  label: "SYSTEM" },
};

const statusConfig = {
  compliant:     { color: "#00e5a0", icon: "✓" },
  non_compliant: { color: "#ff4444", icon: "✗" },
  needs_review:  { color: "#f5a623", icon: "⚠" },
};

export default function ComplianceReport({ result }) {
  const { translation_analysis, vision_analysis } = result;

  const discrepancies = translation_analysis?.discrepancies || [];
  const sections = translation_analysis?.sections || [];
  const layoutIssues = vision_analysis?.issues || [];
  const compliantElements = vision_analysis?.compliant_elements || [];
  const missingElements = vision_analysis?.missing_elements || [];

  return (
    <div className="report">
      {/* Translation Analysis */}
      <div className="report-block">
        <div className="report-block-header">
          <span className="block-icon">🔤</span>
          <span>TRANSLATION INTEGRITY</span>
          <span className="block-score">
            {translation_analysis?.semantic_score?.toFixed(1) ?? "—"}%
          </span>
        </div>

        {sections.length > 0 && (
          <div className="sections-grid">
            {sections.map((sec, i) => {
              const cfg = statusConfig[sec.status] || statusConfig.needs_review;
              return (
                <motion.div
                  key={i}
                  className="section-chip"
                  style={{ "--chip-color": cfg.color }}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                >
                  <span className="chip-status">{cfg.icon}</span>
                  <span className="chip-name">{sec.section}</span>
                  <span className="chip-conf">{sec.confidence?.toFixed(0) ?? "—"}%</span>
                </motion.div>
              );
            })}
          </div>
        )}

        {discrepancies.length > 0 ? (
          <div className="discrepancy-list">
            <p className="list-title">DISCREPANCIES FOUND ({discrepancies.length})</p>
            {discrepancies.map((d, i) => {
              const sev = severityConfig[d.severity] || severityConfig.minor;
              return (
                <motion.div
                  key={i}
                  className="discrepancy-card"
                  style={{ "--sev-color": sev.color, "--sev-bg": sev.bg }}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.08 }}
                >
                  <div className="disc-header">
                    <span className="disc-severity">{sev.icon} {sev.label}</span>
                    <span className="disc-section">{d.section}</span>
                  </div>
                  <p className="disc-issue">{d.explanation}</p>
                  {d.recommendation && (
                    <p className="disc-rec">→ {d.recommendation}</p>
                  )}
                </motion.div>
              );
            })}
          </div>
        ) : (
          <div className="all-clear">✓ No translation discrepancies detected</div>
        )}

        {translation_analysis?.back_translated_text && (
          <details className="backtranslation-details">
            <summary>View back-translation</summary>
            <pre className="backtranslation-text">{translation_analysis.back_translated_text}</pre>
          </details>
        )}
      </div>

      {/* Vision / Layout Analysis */}
      <div className="report-block">
        <div className="report-block-header">
          <span className="block-icon">👁</span>
          <span>LAYOUT & FORMATTING</span>
          <span className="block-score">
            {vision_analysis?.layout_score?.toFixed(1) ?? "—"}%
          </span>
        </div>

        {compliantElements.length > 0 && (
          <div className="compliant-list">
            {compliantElements.map((el, i) => (
              <motion.div
                key={i}
                className="compliant-item"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.04 }}
              >
                <span className="comp-icon">✓</span>
                <span className="comp-name">{el.element}</span>
                {el.note && <span className="comp-note">{el.note}</span>}
              </motion.div>
            ))}
          </div>
        )}

        {layoutIssues.length > 0 ? (
          <div className="discrepancy-list">
            <p className="list-title">LAYOUT ISSUES ({layoutIssues.length})</p>
            {layoutIssues.map((issue, i) => {
              const sev = severityConfig[issue.severity] || severityConfig.minor;
              return (
                <motion.div
                  key={i}
                  className="discrepancy-card"
                  style={{ "--sev-color": sev.color, "--sev-bg": sev.bg }}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.08 }}
                >
                  <div className="disc-header">
                    <span className="disc-severity">{sev.icon} {sev.label}</span>
                    <span className="disc-section">{issue.element}</span>
                    {issue.location && <span className="disc-loc">@ {issue.location}</span>}
                  </div>
                  <p className="disc-issue">{issue.issue}</p>
                  {issue.recommendation && (
                    <p className="disc-rec">→ {issue.recommendation}</p>
                  )}
                </motion.div>
              );
            })}
          </div>
        ) : (
          <div className="all-clear">✓ No layout compliance issues detected</div>
        )}

        {missingElements.length > 0 && (
          <div className="missing-list">
            <p className="list-title">MISSING REQUIRED ELEMENTS</p>
            {missingElements.map((el, i) => (
              <div key={i} className="missing-item">⊗ {el.element || el}</div>
            ))}
          </div>
        )}

        {vision_analysis?.regulatory_context && (
          <div className="reg-context">
            📋 {vision_analysis.regulatory_context}
          </div>
        )}
      </div>
    </div>
  );
}
