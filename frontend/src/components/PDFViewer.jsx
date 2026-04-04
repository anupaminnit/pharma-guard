import { useState } from "react";

export default function PDFViewer({ fileUrl, result }) {
  const [imageError, setImageError] = useState(false);

  if (!fileUrl) return <div className="pdf-empty">No file uploaded</div>;

  const layoutIssues = result?.vision_analysis?.issues || [];
  const compliantElements = result?.vision_analysis?.compliant_elements || [];

  // Build overlay elements from bounding boxes
  const overlays = [
    ...compliantElements.map(el => ({
      ...el,
      type: "compliant",
      color: "rgba(0,229,160,0.25)",
      border: "#00e5a0",
    })),
    ...layoutIssues.map(el => ({
      ...el,
      type: "issue",
      color: "rgba(255,68,68,0.2)",
      border: "#ff4444",
    })),
  ].filter(el => el.bounding_box);

  const isImage = fileUrl && !fileUrl.includes(".pdf");

  return (
    <div className="pdf-viewer">
      <div className="pdf-container">
        {isImage || !imageError ? (
          <div className="pdf-image-wrap">
            <img
              src={fileUrl}
              alt="Packaging artwork"
              className="pdf-image"
              onError={() => setImageError(true)}
            />
            {/* Compliance Overlays */}
            {overlays.map((el, i) => {
              const bb = el.bounding_box;
              return (
                <div
                  key={i}
                  className="pdf-overlay"
                  style={{
                    left: `${bb.x}%`,
                    top: `${bb.y}%`,
                    width: `${bb.width}%`,
                    height: `${bb.height}%`,
                    background: el.color,
                    border: `2px solid ${el.border}`,
                  }}
                  title={el.issue || el.note || el.element}
                >
                  <span className="overlay-label" style={{ color: el.border }}>
                    {el.type === "compliant" ? "✓" : "✗"} {el.element}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="pdf-fallback">
            <p>📄 PDF uploaded — open in browser to view</p>
            <a href={fileUrl} target="_blank" rel="noopener noreferrer" className="pdf-link">
              Open PDF ↗
            </a>
          </div>
        )}
      </div>

      <div className="pdf-legend">
        <div className="legend-item">
          <span className="legend-swatch" style={{ background: "rgba(0,229,160,0.3)", border: "2px solid #00e5a0" }} />
          <span>Compliant Element</span>
        </div>
        <div className="legend-item">
          <span className="legend-swatch" style={{ background: "rgba(255,68,68,0.2)", border: "2px solid #ff4444" }} />
          <span>Flagged Issue</span>
        </div>
      </div>
    </div>
  );
}
