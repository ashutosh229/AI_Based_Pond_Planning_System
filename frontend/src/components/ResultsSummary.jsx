function formatTimings(timings_ms) {
  if (!timings_ms) return null;
  const total = Object.values(timings_ms).reduce((sum, v) => sum + v, 0);
  const parts = Object.entries(timings_ms)
    .map(([label, ms]) => `${label.replace(/_ms$/, "").replaceAll("_", " ")}: ${ms} ms`)
    .join(" · ");
  return `${parts} · total: ${Math.round(total)} ms`;
}

export default function ResultsSummary({ result }) {
  const {
    source,
    source_filename, // present on the legacy /api/analyzeContour shape
    contour_interval_m,
    elevation_range_m,
    total_contours_parsed,
    closed_contours_used,
    candidate_basins_found,
    notes,
    timings_ms,
  } = result;

  return (
    <>
      <h2>Analysis Summary — {source || source_filename}</h2>
      <div className="summary-grid">
        <div className="stat">
          <div className="label">Contour interval</div>
          <div className="value">{contour_interval_m} m</div>
        </div>
        <div className="stat">
          <div className="label">Elevation range</div>
          <div className="value">
            {elevation_range_m[0]} – {elevation_range_m[1]} m
          </div>
        </div>
        <div className="stat">
          <div className="label">Contours parsed</div>
          <div className="value">{total_contours_parsed}</div>
        </div>
        <div className="stat">
          <div className="label">Closed rings used</div>
          <div className="value">{closed_contours_used}</div>
        </div>
        <div className="stat">
          <div className="label">Candidate basins</div>
          <div className="value">{candidate_basins_found}</div>
        </div>
      </div>
      <p className="notes">{notes}</p>
      {timings_ms && <p className="notes timings">{formatTimings(timings_ms)}</p>}
    </>
  );
}
