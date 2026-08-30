function formatArea(m2) {
  if (m2 >= 1_000_000) return `${(m2 / 1_000_000).toFixed(2)} km²`;
  if (m2 >= 10_000) return `${(m2 / 10_000).toFixed(2)} ha`;
  return `${Math.round(m2).toLocaleString()} m²`;
}

export default function BasinList({ sites, selectedRank, onSelect }) {
  if (!sites.length) {
    return <p className="notes">No basins met the minimum depth threshold.</p>;
  }

  return (
    <>
      <h2>Candidate Sites</h2>
      <ul className="basin-list">
        {sites.map((site) => (
          <li
            key={site.rank}
            className={`basin-card ${site.rank === selectedRank ? "selected" : ""}`}
            onClick={() => onSelect(site.rank)}
          >
            <div className="rank">
              Rank {site.rank}
              {site.rank === 1 ? " · Recommended" : ""}
            </div>
            <div className="title">Pit @ {site.pit_elevation_m} m</div>
            <div className="basin-meta">
              <span>
                Depth: <strong>{site.basin_depth_m} m</strong>
              </span>
              <span>
                Footprint:{" "}
                <strong>{formatArea(site.pond_footprint_area_m2)}</strong>
              </span>
              <span>
                Catchment: <strong>{formatArea(site.catchment_area_m2)}</strong>
              </span>
              <span>
                Boundary elev:{" "}
                <strong>{site.catchment_boundary_elevation_m} m</strong>
              </span>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
