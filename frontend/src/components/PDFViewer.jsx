import { useState, useEffect, useRef } from "react";
import * as pdfjsLib from "pdfjs-dist";

// Use CDN worker to avoid bundler complexity
pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

export default function PDFViewer({ fileUrl, fileType, result }) {
  const canvasRef = useRef(null);
  const [pdfError, setPdfError] = useState(null);
  const [imageError, setImageError] = useState(false);
  const [pdfRendered, setPdfRendered] = useState(false);

  const isPdf = fileType === "application/pdf";

  const layoutIssues = result?.vision_analysis?.issues || [];
  const compliantElements = result?.vision_analysis?.compliant_elements || [];

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

  useEffect(() => {
    if (!isPdf || !fileUrl || !canvasRef.current) return;

    setPdfError(null);
    setPdfRendered(false);

    const renderPage = async () => {
      try {
        const pdfDoc = await pdfjsLib.getDocument(fileUrl).promise;
        const page = await pdfDoc.getPage(1);
        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");

        // Scale to fit the container width (~600px)
        const viewport = page.getViewport({ scale: 1 });
        const scale = Math.min(600 / viewport.width, 900 / viewport.height);
        const scaledViewport = page.getViewport({ scale });

        canvas.width = scaledViewport.width;
        canvas.height = scaledViewport.height;

        await page.render({ canvasContext: ctx, viewport: scaledViewport }).promise;
        setPdfRendered(true);
      } catch (err) {
        setPdfError(`Could not render PDF: ${err.message}`);
      }
    };

    renderPage();
  }, [fileUrl, isPdf]);

  if (!fileUrl) return <div className="pdf-empty">No file uploaded</div>;

  return (
    <div className="pdf-viewer">
      <div className="pdf-container">
        <div className="pdf-image-wrap">
          {isPdf ? (
            <>
              <canvas ref={canvasRef} className="pdf-image" style={{ display: pdfError ? "none" : "block" }} />
              {pdfError && (
                <div className="pdf-fallback">
                  <p>⚠ {pdfError}</p>
                  <a href={fileUrl} target="_blank" rel="noopener noreferrer" className="pdf-link">
                    Open PDF ↗
                  </a>
                </div>
              )}
            </>
          ) : (
            <>
              {!imageError ? (
                <img
                  src={fileUrl}
                  alt="Packaging artwork"
                  className="pdf-image"
                  onError={() => setImageError(true)}
                />
              ) : (
                <div className="pdf-fallback">
                  <p>Could not display image</p>
                  <a href={fileUrl} target="_blank" rel="noopener noreferrer" className="pdf-link">
                    Open file ↗
                  </a>
                </div>
              )}
            </>
          )}

          {/* Compliance overlays — shown when image/canvas is rendered */}
          {(!isPdf || pdfRendered) && !imageError && !pdfError && overlays.map((el, i) => {
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
