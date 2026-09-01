import { useRef, useState } from "react";
import { importJSON } from "../store/import";

interface DropZoneProps {
  onImport: () => void;
}

export default function DropZone({ onImport }: DropZoneProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const handleFile = async (file: File) => {
    setStatus("Importing…");
    try {
      const text = await file.text();
      const count = await importJSON(text);
      setStatus(`✓ ${count} workouts`);
      onImport();
      setTimeout(() => setStatus(null), 3000);
    } catch (e) {
      setStatus(`✗ ${e instanceof Error ? e.message : "Import failed"}`);
      setTimeout(() => setStatus(null), 5000);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div
      className={`drop-zone ${dragging ? "dragging" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => fileRef.current?.click()}
    >
      <input
        ref={fileRef}
        type="file"
        accept=".json"
        style={{ display: "none" }}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />
      {status ? (
        <span className="drop-status">{status}</span>
      ) : (
        <span>📂 Import JSON</span>
      )}
    </div>
  );
}
