import { useCallback } from "react";
import { useDropzone } from "react-dropzone";

export default function UploadZone({ onFileDrop, uploadedFile }) {
  const onDrop = useCallback(
    (acceptedFiles) => {
      if (acceptedFiles.length > 0) onFileDrop(acceptedFiles[0]);
    },
    [onFileDrop]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
      "application/pdf": [".pdf"],
    },
    maxFiles: 1,
    multiple: false,
  });

  return (
    <div
      {...getRootProps()}
      className={`upload-zone ${isDragActive ? "drag-active" : ""} ${uploadedFile ? "has-file" : ""}`}
    >
      <input {...getInputProps()} />
      {uploadedFile ? (
        <div className="upload-file-info">
          <span className="upload-file-icon">📄</span>
          <div>
            <div className="upload-file-name">{uploadedFile.name}</div>
            <div className="upload-file-size">{(uploadedFile.size / 1024).toFixed(1)} KB</div>
          </div>
          <span className="upload-replace">Click to replace</span>
        </div>
      ) : (
        <div className="upload-prompt">
          <span className="upload-icon">{isDragActive ? "⬇" : "⊕"}</span>
          <span className="upload-text">
            {isDragActive ? "Drop packaging artwork here" : "Drag PDF or image, or click to browse"}
          </span>
          <span className="upload-hint">PNG, JPG, PDF accepted</span>
        </div>
      )}
    </div>
  );
}
