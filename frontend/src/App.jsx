import { useState, useRef, useCallback, useEffect } from "react";
import "./App.css";
import { redactText, redactFile } from "./api";

const ENTITY_CATALOG = [
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "pan", label: "PAN" },
  { key: "aadhaar", label: "Aadhaar" },
  { key: "gstin", label: "GSTIN" },
  { key: "passport_in", label: "Passport" },
  { key: "credit_card", label: "Card no." },
  { key: "ssn", label: "SSN" },
  { key: "ifsc", label: "IFSC" },
  { key: "ip", label: "IP address" },
  { key: "dob", label: "Date" },
];

function useEntityFilters() {
  const [enabled, setEnabled] = useState(() => new Set(ENTITY_CATALOG.map((e) => e.key)));
  const toggle = (key) =>
    setEnabled((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  return { enabled, toggle };
}

function EntityChips({ enabled, onToggle }) {
  return (
    <div className="chip-row" role="group" aria-label="Entity types to redact">
      {ENTITY_CATALOG.map((e) => (
        <button
          key={e.key}
          className={`chip ${enabled.has(e.key) ? "chip--on" : ""}`}
          onClick={() => onToggle(e.key)}
          type="button"
          aria-pressed={enabled.has(e.key)}
        >
          <span className="chip__swatch" />
          {e.label}
        </button>
      ))}
    </div>
  );
}

function RedactionSweep({ label }) {
  const lines = [88, 64, 76, 45, 82];
  return (
    <div className="sweep" role="status" aria-live="polite">
      <div className="sweep__lines">
        {lines.map((w, i) => (
          <div key={i} className="sweep__line" style={{ width: `${w}%`, animationDelay: `${i * 0.18}s` }}>
            <span className="sweep__bar" style={{ animationDelay: `${i * 0.18}s` }} />
          </div>
        ))}
      </div>
      <p className="sweep__label">{label || "Scanning for sensitive data…"}</p>
    </div>
  );
}

function ResultStats({ result }) {
  if (!result) return null;
  return (
    <div className="stats">
      <div className="stat">
        <span className="stat__value">{result.total_redactions}</span>
        <span className="stat__label">redaction{result.total_redactions === 1 ? "" : "s"}</span>
      </div>
      {"page_count" in result && (
        <div className="stat">
          <span className="stat__value">{result.page_count}</span>
          <span className="stat__label">page{result.page_count === 1 ? "" : "s"}</span>
        </div>
      )}
      {result.used_ocr && <span className="badge badge--ocr">Azure OCR used</span>}
      <div className="stat-breakdown">
        {result.entities_found.map((f) => (
          <span key={f.label} className="tape">
            {f.label} <b>×{f.count}</b>
          </span>
        ))}
        {result.entities_found.length === 0 && (
          <span className="stat-breakdown__empty">No sensitive entities matched.</span>
        )}
      </div>
    </div>
  );
}

function SettingsDrawer({ open, onClose, azure, setAzure }) {
  return (
    <>
      <div className={`scrim ${open ? "scrim--visible" : ""}`} onClick={onClose} />
      <aside className={`drawer ${open ? "drawer--open" : ""}`} aria-hidden={!open}>
        <div className="drawer__head">
          <h3>Azure Document Intelligence</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close settings">
            ✕
          </button>
        </div>
        <p className="drawer__copy">
          Used only to OCR image files and scanned PDFs that have no selectable text layer.
          Your endpoint and key are kept in this browser tab only — never written to a
          server or a database.
        </p>
        <label className="field">
          <span>Endpoint</span>
          <input
            type="text"
            placeholder="https://your-resource.cognitiveservices.azure.com"
            value={azure.endpoint}
            onChange={(e) => setAzure((a) => ({ ...a, endpoint: e.target.value }))}
          />
        </label>
        <label className="field">
          <span>API key</span>
          <input
            type="password"
            placeholder="Your subscription key"
            value={azure.key}
            onChange={(e) => setAzure((a) => ({ ...a, key: e.target.value }))}
          />
        </label>
        <label className="switch-row">
          <span>
            Use Azure OCR
            <small>Required for image uploads &amp; scanned PDFs</small>
          </span>
          <span
            className={`switch ${azure.enabled ? "switch--on" : ""}`}
            onClick={() => setAzure((a) => ({ ...a, enabled: !a.enabled }))}
            role="switch"
            aria-checked={azure.enabled}
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && setAzure((a) => ({ ...a, enabled: !a.enabled }))}
          >
            <span className="switch__knob" />
          </span>
        </label>
        <a
          className="drawer__link"
          href="https://learn.microsoft.com/azure/ai-services/document-intelligence/"
          target="_blank"
          rel="noreferrer"
        >
          Don't have a resource? Set one up in Azure AI Foundry →
        </a>
      </aside>
    </>
  );
}

function TextTab({ entities }) {
  const [input, setInput] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await redactText(input, [...entities.enabled]);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="split">
      <section className="pane">
        <div className="pane__head">
          <h2>Source text</h2>
          <span className="pane__count">{input.length.toLocaleString()} chars</span>
        </div>
        <EntityChips enabled={entities.enabled} onToggle={entities.toggle} />
        <textarea
          className="textarea"
          placeholder="Paste an email thread, a form, a chat log — anything with PII you need stripped before it leaves this room."
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <div className="pane__actions">
          <button className="btn btn--primary" onClick={run} disabled={loading || !input.trim()}>
            {loading ? "Redacting…" : "Redact text"}
          </button>
          {error && <span className="error-text">{error}</span>}
        </div>
      </section>

      <section className="pane">
        <div className="pane__head">
          <h2>Redacted output</h2>
        </div>
        {loading && <RedactionSweep />}
        {!loading && result && (
          <>
            <ResultStats result={result} />
            <textarea className="textarea textarea--output" readOnly value={result.redacted_text} />
          </>
        )}
        {!loading && !result && (
          <div className="empty">
            <p>Redacted text will appear here, mirror-lined with what you pasted.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function FileTab({ entities, azure, openSettings }) {
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const inputRef = useRef(null);

  const isImage = file && file.type.startsWith("image/");
  const isPdf = file && (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf"));

  const pickFile = (f) => {
    if (!f) return;
    setFile(f);
    setResult(null);
    setError(null);
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) pickFile(f);
  }, []);

  const run = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await redactFile({
        file,
        entities: [...entities.enabled],
        useAzure: azure.enabled,
        azureEndpoint: azure.endpoint,
        azureKey: azure.key,
      });
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const download = () => {
    if (!result) return;
    const link = document.createElement("a");
    link.href = `data:${result.mime};base64,${result.redacted_base64}`;
    link.download = result.filename;
    link.click();
  };

  const needsOcrHint =
    file && ((isImage && !azure.enabled) || error?.toLowerCase().includes("scanned"));

  return (
    <div className="split">
      <section className="pane">
        <div className="pane__head">
          <h2>Upload</h2>
        </div>
        <EntityChips enabled={entities.enabled} onToggle={entities.toggle} />

        <div
          className={`dropzone ${dragOver ? "dropzone--active" : ""} ${file ? "dropzone--filled" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp,.tiff,.bmp,application/pdf,image/*"
            hidden
            onChange={(e) => pickFile(e.target.files?.[0])}
          />
          {!file && (
            <>
              <div className="dropzone__mark">＋</div>
              <p className="dropzone__title">Drop a PDF or image</p>
              <p className="dropzone__sub">or click to browse — PDF, PNG, JPG, WEBP, TIFF, BMP</p>
            </>
          )}
          {file && (
            <div className="file-chip" onClick={(e) => e.stopPropagation()}>
              <span className="file-chip__icon">{isPdf ? "PDF" : "IMG"}</span>
              <div className="file-chip__meta">
                <span className="file-chip__name">{file.name}</span>
                <span className="file-chip__size">{(file.size / 1024).toFixed(0)} KB</span>
              </div>
              <button
                className="icon-btn"
                onClick={() => {
                  setFile(null);
                  setResult(null);
                  setError(null);
                }}
                aria-label="Remove file"
              >
                ✕
              </button>
            </div>
          )}
        </div>

        <label className="switch-row switch-row--compact">
          <span>
            Azure OCR
            <small>For scans &amp; images</small>
          </span>
          <span
            className={`switch ${azure.enabled ? "switch--on" : ""}`}
            onClick={() =>
              azure.endpoint && azure.key
                ? azure.setAzure((a) => ({ ...a, enabled: !a.enabled }))
                : openSettings()
            }
            role="switch"
            aria-checked={azure.enabled}
            tabIndex={0}
          >
            <span className="switch__knob" />
          </span>
        </label>

        <div className="pane__actions">
          <button className="btn btn--primary" onClick={run} disabled={loading || !file}>
            {loading ? "Redacting…" : "Redact file"}
          </button>
          <button className="btn btn--ghost" onClick={openSettings} type="button">
            Configure Azure
          </button>
        </div>
        {error && <p className="error-text error-text--block">{error}</p>}
        {needsOcrHint && !error && (
          <p className="hint-text">
            Images need OCR to find text — turn on Azure OCR above and add your credentials.
          </p>
        )}
      </section>

      <section className="pane">
        <div className="pane__head">
          <h2>Redacted output</h2>
          {result && (
            <button className="btn btn--small" onClick={download}>
              Download
            </button>
          )}
        </div>
        {loading && <RedactionSweep label="Locating PII and burning it out…" />}
        {!loading && result && (
          <>
            <ResultStats result={result} />
            <div className="preview">
              {result.mime === "application/pdf" ? (
                <iframe
                  title="Redacted PDF preview"
                  src={`data:${result.mime};base64,${result.redacted_base64}`}
                  className="preview__frame"
                />
              ) : (
                <img
                  className="preview__image"
                  alt="Redacted document"
                  src={`data:${result.mime};base64,${result.redacted_base64}`}
                />
              )}
            </div>
          </>
        )}
        {!loading && !result && (
          <div className="empty">
            <p>Your redacted file — with a real, unrecoverable blackout, not a sticker on top — will preview here.</p>
          </div>
        )}
      </section>
    </div>
  );
}

export default function App() {
  const [mode, setMode] = useState("file");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [azureState, setAzureState] = useState({ endpoint: "", key: "", enabled: false });
  const entities = useEntityFilters();

  useEffect(() => {
    const saved = sessionStorage.getItem("redact.azure");
    if (saved) {
      try {
        setAzureState(JSON.parse(saved));
      } catch {
        /* ignore */
      }
    }
  }, []);

  useEffect(() => {
    sessionStorage.setItem("redact.azure", JSON.stringify(azureState));
  }, [azureState]);

  const azure = { ...azureState, setAzure: setAzureState };

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true" />
          <span className="brand__word">REDACT</span>
        </div>
        <nav className="tabs" role="tablist">
          <button
            role="tab"
            aria-selected={mode === "file"}
            className={`tab ${mode === "file" ? "tab--active" : ""}`}
            onClick={() => setMode("file")}
          >
            Upload file
          </button>
          <button
            role="tab"
            aria-selected={mode === "text"}
            className={`tab ${mode === "text" ? "tab--active" : ""}`}
            onClick={() => setMode("text")}
          >
            Paste text
          </button>
        </nav>
        <button className="settings-toggle" onClick={() => setSettingsOpen(true)}>
          <span className={`dot ${azureState.enabled && azureState.endpoint ? "dot--on" : ""}`} />
          Azure OCR
        </button>
      </header>

      <main className="workspace">
        {mode === "text" ? (
          <TextTab entities={entities} />
        ) : (
          <FileTab entities={entities} azure={azure} openSettings={() => setSettingsOpen(true)} />
        )}
      </main>

      <footer className="foot">
        <span>Nothing you upload is stored — files are processed in memory and discarded after the response.</span>
      </footer>

      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        azure={azureState}
        setAzure={setAzureState}
      />
    </div>
  );
}
