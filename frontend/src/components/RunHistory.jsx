import { useEffect, useState } from "react";
import { getRun, getRuns } from "../api";

function formatArea(m2) {
  if (m2 == null) return "—";
  if (m2 >= 1_000_000) return `${(m2 / 1_000_000).toFixed(2)} km²`;
  if (m2 >= 10_000) return `${(m2 / 10_000).toFixed(2)} ha`;
  return `${Math.round(m2).toLocaleString()} m²`;
}

function formatWhen(unixSeconds) {
  return new Date(unixSeconds * 1000).toLocaleString();
}

/**
 * Lists past persisted analysis runs from the SQLite REST DB server, and
 * lets the user reload one's full result back into the main view without
 * re-running the analysis (README roadmap: "past requests don't need to
 * be re-run"). Loading failures are shown inline rather than thrown,
 * since run history is a convenience, not a blocking dependency.
 */
export default function RunHistory({ onLoadRun }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loadingId, setLoadingId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getRuns(20)
      .then((data) => {
        if (!cancelled) setRuns(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Could not load run history");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleReload(runId) {
    setLoadingId(runId);
    try {
      const full = await getRun(runId);
      onLoadRun(full.result);
    } catch (err) {
      setError(err.message || "Could not load that run");
    } finally {
      setLoadingId(null);
    }
  }

  if (loading) return <p className="status">Loading run history…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!runs.length) return <p className="notes">No past runs yet.</p>;

  return (
    <>
      <h2>Recent Runs</h2>
      <ul className="basin-list">
        {runs.map((run) => (
          <li
            key={run.id}
            className="basin-card"
            onClick={() => handleReload(run.id)}
          >
            <div className="rank">
              {run.mode === "area" ? "Drawn area" : "KML upload"} ·{" "}
              {formatWhen(run.created_at)}
            </div>
            <div className="title">{run.source}</div>
            <div className="basin-meta">
              <span>
                Basins found:{" "}
                <strong>{run.candidate_basins_found ?? "—"}</strong>
              </span>
              <span>
                Catchment:{" "}
                <strong>{formatArea(run.recommended_catchment_area_m2)}</strong>
              </span>
              <span>
                Feasible:{" "}
                <strong>
                  {run.is_feasible === null
                    ? "—"
                    : run.is_feasible
                      ? "Yes"
                      : "No"}
                </strong>
              </span>
            </div>
            {loadingId === run.id && <p className="status">Loading…</p>}
          </li>
        ))}
      </ul>
    </>
  );
}
