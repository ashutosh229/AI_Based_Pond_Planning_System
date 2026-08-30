export default function ResultsSummary({ result }) {
  const {
    source_filename,
    contour_interval_m,
    elevation_range_m,
    total_contours_parsed,
    closed_contours_used,
    candidate_basins_found,
    notes,
  } = result;

  return (
    <>
      <h2>Analysis Summary — {source_filename}</h2>
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
    </>
  );
}
