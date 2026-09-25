function formatVolume(m3) {
  if (m3 >= 1_000_000) return `${(m3 / 1_000_000).toFixed(2)} million m³`;
  return `${Math.round(m3).toLocaleString()} m³`;
}

export default function PondRecommendationCard({ recommendation }) {
  const {
    annual_rainfall_m,
    rainfall_years_used,
    rainfall_source,
    annual_runoff_volume_m3,
    design_storage_volume_m3,
    usable_volume_m3,
    recommended_depth_m,
    is_feasible,
    notes,
  } = recommendation;

  return (
    <>
      <h2>Water Volume &amp; Pond Sizing</h2>
      <div className="summary-grid">
        <div className="stat">
          <div className="label">Avg. annual rainfall</div>
          <div className="value">{Math.round(annual_rainfall_m * 1000)} mm</div>
        </div>
        <div className="stat">
          <div className="label">Annual runoff volume</div>
          <div className="value">{formatVolume(annual_runoff_volume_m3)}</div>
        </div>
        <div className="stat">
          <div className="label">Design storage volume</div>
          <div className="value">{formatVolume(design_storage_volume_m3)}</div>
        </div>
        <div className="stat">
          <div className="label">Usable volume</div>
          <div className="value">{formatVolume(usable_volume_m3)}</div>
        </div>
        <div className="stat">
          <div className="label">Recommended depth</div>
          <div className="value">{recommended_depth_m} m</div>
        </div>
        <div className="stat">
          <div className="label">Feasibility</div>
          <div className={`value ${is_feasible ? "" : "warn"}`}>
            {is_feasible ? "Feasible" : "Not feasible"}
          </div>
        </div>
      </div>
      <p className="notes">
        {notes} Based on {rainfall_years_used} years of {rainfall_source} data.
      </p>
    </>
  );
}
