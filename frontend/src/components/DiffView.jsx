import { useMemo } from "react";
import DiffMatchPatch from "diff-match-patch";

const dmp = new DiffMatchPatch();

// Returns an array of <span> nodes highlighting word-level differences
function InlineDiff({ master, translated }) {
  const spans = useMemo(() => {
    if (!master || !translated) return [{ type: 0, text: translated || master || "" }];
    const diffs = dmp.diff_main(master, translated);
    dmp.diff_cleanupSemantic(diffs);
    return diffs;
  }, [master, translated]);

  return (
    <span>
      {spans.map(([type, text], i) => {
        if (type === 1)  // insertion (in translated, not in master)
          return <mark key={i} className="diff-ins">{text}</mark>;
        if (type === -1) // deletion (in master, not in translated)
          return <mark key={i} className="diff-del">{text}</mark>;
        return <span key={i}>{text}</span>;
      })}
    </span>
  );
}

const STATUS_COLOR = {
  compliant:     { bg: "rgba(0,229,160,0.08)", border: "#00e5a0", badge: "#00e5a0", label: "✓ Compliant" },
  non_compliant: { bg: "rgba(255,68,68,0.1)",  border: "#ff4444", badge: "#ff4444", label: "✗ Non-compliant" },
  missing:       { bg: "rgba(245,166,35,0.1)", border: "#f5a623", badge: "#f5a623", label: "⚠ Missing" },
};

export default function DiffView({ result }) {
  const sections = result?.translation_analysis?.sections || [];
  const backTranslated = result?.translation_analysis?.back_translated_text || "";
  const masterText = result?.translation_analysis?.master_text || "";

  if (sections.length === 0) {
    return (
      <div className="diff-empty">
        <p>No section-level diff data available.</p>
        {backTranslated && masterText && (
          <div className="diff-full">
            <div className="diff-col-header">
              <span>Master English</span>
              <span>Back-Translation</span>
            </div>
            <div className="diff-full-body">
              <div className="diff-col">{masterText}</div>
              <div className="diff-col">
                <InlineDiff master={masterText} translated={backTranslated} />
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="diff-view">
      <div className="diff-legend">
        <span className="diff-legend-ins">■ Added / Changed</span>
        <span className="diff-legend-del">■ Removed</span>
        <span className="diff-legend-eq">■ Unchanged</span>
      </div>

      {sections.map((sec, i) => {
        const colors = STATUS_COLOR[sec.status] || STATUS_COLOR.compliant;
        const masterSec = sec.master_text || "";
        const backSec   = sec.back_translation || sec.translated_text || "";

        return (
          <div
            key={i}
            className="diff-section"
            style={{ background: colors.bg, borderLeft: `3px solid ${colors.border}` }}
          >
            <div className="diff-section-header">
              <span className="diff-section-name">{sec.section || sec.name || `Section ${i + 1}`}</span>
              <span className="diff-section-badge" style={{ color: colors.badge }}>
                {colors.label}
              </span>
            </div>

            <div className="diff-cols">
              <div className="diff-col-wrap">
                <div className="diff-col-label">Master English</div>
                <div className="diff-col-text">{masterSec}</div>
              </div>
              <div className="diff-col-wrap">
                <div className="diff-col-label">Back-Translation</div>
                <div className="diff-col-text">
                  <InlineDiff master={masterSec} translated={backSec} />
                </div>
              </div>
            </div>

            {sec.discrepancy && (
              <div className="diff-note">
                <strong>Note:</strong> {sec.discrepancy}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
