import { useRef, useState } from "react";

export default function FileUpload({ onUpload, disabled }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [filename, setFilename] = useState(null);

  function handleFile(file) {
    if (!file) return;
    if (!file.name.toLowerCase().match(/\.(kml|kmz)$/)) {
      alert("Please upload a .kml or .kmz file");
      return;
    }
    setFilename(file.name);
    onUpload(file);
  }

  return (
    <div
      className={`dropzone ${dragOver ? "dragover" : ""}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        if (disabled) return;
        handleFile(e.dataTransfer.files[0]);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".kml,.kmz"
        disabled={disabled}
        onChange={(e) => handleFile(e.target.files[0])}
      />
      <p>Drop a KML / KMZ contour map here, or click to browse</p>
      {filename && <p className="filename">{filename}</p>}
    </div>
  );
}
