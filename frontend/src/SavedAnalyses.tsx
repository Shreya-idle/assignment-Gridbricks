import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { filtersToSearch } from "./analysis";
import { createSavedAnalysis, deleteSavedAnalysis, listSavedAnalyses, renameSavedAnalysis } from "./api";
import { useAuth } from "./auth";
import type { AnalysisFilters, SavedAnalysis } from "./types";

export function SaveAnalysisControl({ filters }: { filters: AnalysisFilters }) {
  const auth = useAuth();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null); setMessage(null);
    try {
      await createSavedAnalysis(auth.accessToken!, name, filters);
      setName(""); setMessage("Analysis saved.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to save analysis."); }
    finally { setBusy(false); }
  }

 

  return (
    <section className="save-panel" aria-labelledby="save-analysis-title">
      <div>
        <strong id="save-analysis-title">Save this analysis</strong>
        <p>Store the currently applied UTC period and decision cutoff.</p>
      </div>
      <form onSubmit={save} className="save-form">
        <label htmlFor="saved-analysis-name" className="sr-only">Analysis name</label>
        <input
          id="saved-analysis-name"
          required
          maxLength={120}
          value={name}
          placeholder="Analysis name"
          onChange={(event) => setName(event.target.value)}
        />
        <button className="primary-button" disabled={busy} type="submit">
          {busy ? "Saving…" : "Save analysis"}
        </button>
      </form>
      {message && <span className="success-message" role="status">{message}</span>}
      {error && <span className="field-error" role="alert">{error}</span>}
    </section>
  );
}

function filtersFromSaved(item: SavedAnalysis): AnalysisFilters {
  const parts = (value: string) => { const iso = new Date(value).toISOString(); return [iso.slice(0, 10), iso.slice(11, 16)] as const; };
  const [startDate, startTime] = parts(item.period_start);
  const [endDate, endTime] = parts(item.period_end);
  const [cutoffDate, cutoffTime] = parts(item.cutoff);
  return { startDate, startTime, endDate, endTime, cutoffDate, cutoffTime };
}

export function SavedAnalysesPanel() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState<SavedAnalysis[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const token = auth.accessToken;
  const enabled = auth.status === "authenticated" && !auth.isGuest && Boolean(token);
  const load = useCallback(async () => {
    if (!enabled || !token) return;
    setBusy(true); setError(null);
    try { setItems(await listSavedAnalyses(token)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load saved analyses."); }
    finally { setBusy(false); }
  }, [enabled, token]);
  useEffect(() => { void load(); }, [load]);



  return (
    <section className="saved-list-panel" aria-labelledby="saved-list-title">
      <div className="section-title-row">
        <div>
          <h2 id="saved-list-title">Saved analyses</h2>
          <p>Open or manage your UTC analysis configurations.</p>
        </div>
        <button className="secondary-button" disabled={busy} onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {error && <div className="inline-alert" role="alert">{error}</div>}
      {!busy && !error && items.length === 0 && <p>No saved analyses yet.</p>}
      <div className="saved-items">
        {items.map((item) => (
          <article className="saved-item" key={item.id}>
            {editing === item.id ? (
              <form
                className="save-form"
                onSubmit={async (event) => {
                  event.preventDefault();
                  setError(null);
                  try {
                    const renamed = await renameSavedAnalysis(token!, item.id, editName);
                    setItems((current) => current.map((entry) => entry.id === item.id ? renamed : entry));
                    setEditing(null);
                  } catch (cause) {
                    setError(cause instanceof Error ? cause.message : "Unable to rename analysis.");
                  }
                }}
              >
                <label className="sr-only" htmlFor={`rename-${item.id}`}>Analysis name</label>
                <input
                  id={`rename-${item.id}`}
                  required
                  maxLength={120}
                  value={editName}
                  onChange={(event) => setEditName(event.target.value)}
                />
                <button className="primary-button" type="submit">Save name</button>
                <button className="ghost-button" type="button" onClick={() => setEditing(null)}>
                  Cancel
                </button>
              </form>
            ) : (
              <>
                <div>
                  <strong>{item.name}</strong>
                  <p>
                    {new Date(item.period_start).toLocaleString("en-GB", { timeZone: "UTC" })}
                    {" – "}
                    {new Date(item.period_end).toLocaleString("en-GB", { timeZone: "UTC" })} UTC
                  </p>
                </div>
                <div className="saved-actions">
                  <button
                    className="secondary-button"
                    onClick={() => navigate(`/forecast-analysis?${filtersToSearch(filtersFromSaved(item))}`)}
                  >
                    Open
                  </button>
                  <button
                    className="ghost-button"
                    onClick={() => { setEditing(item.id); setEditName(item.name); }}
                  >
                    Rename
                  </button>
                  <button
                    className="ghost-button danger-button"
                    onClick={async () => {
                      setError(null);
                      try {
                        await deleteSavedAnalysis(token!, item.id);
                        setItems((current) => current.filter((entry) => entry.id !== item.id));
                      } catch (cause) {
                        setError(cause instanceof Error ? cause.message : "Unable to delete analysis.");
                      }
                    }}
                  >
                    Delete
                  </button>
                </div>
              </>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
