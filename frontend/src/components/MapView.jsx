import { useEffect, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  CircleMarker,
  Popup,
  useMap,
} from "react-leaflet";

const COLORS = [
  "#38bdf8", // rank 1
  "#a78bfa",
  "#f472b6",
  "#fb923c",
  "#4ade80",
  "#facc15",
];

function FitBounds({ geojsons }) {
  const map = useMap();
  useEffect(() => {
    if (!geojsons.length) return;
    const layer = L.geoJSON(geojsons);
    const bounds = layer.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
    }
  }, [map, geojsons]);
  return null;
}

export default function MapView({ sites, selectedSite, onSelectSite }) {
  const geojsons = useMemo(
    () => sites.map((s) => s.catchment_boundary_geojson).filter(Boolean),
    [sites],
  );

  const center = selectedSite
    ? [selectedSite.site.lat, selectedSite.site.lon]
    : [20.5, 78.9]; // rough India centroid fallback

  return (
    <div
      style={{
        position: "relative",
        flex: 1,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <h2 style={{ padding: "1rem 1.25rem 0" }}>Catchment Map</h2>
      <MapContainer
        center={center}
        zoom={13}
        style={{ flex: 1, minHeight: 480 }}
        scrollWheelZoom
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <FitBounds geojsons={geojsons} />

        {sites.map((site) => {
          const color = COLORS[(site.rank - 1) % COLORS.length];
          const isSelected = selectedSite?.rank === site.rank;

          return (
            <div key={site.rank}>
              <GeoJSON
                data={site.catchment_boundary_geojson}
                style={{
                  color,
                  weight: isSelected ? 3 : 1.5,
                  opacity: isSelected ? 1 : 0.7,
                  fillColor: color,
                  fillOpacity: isSelected ? 0.25 : 0.12,
                }}
                eventHandlers={{
                  click: () => onSelectSite(site.rank),
                }}
              />
              <CircleMarker
                center={[site.site.lat, site.site.lon]}
                radius={isSelected ? 9 : 6}
                pathOptions={{
                  color: "#0f172a",
                  weight: 2,
                  fillColor: color,
                  fillOpacity: 1,
                }}
                eventHandlers={{
                  click: () => onSelectSite(site.rank),
                }}
              >
                <Popup>
                  <strong>Rank {site.rank}</strong>
                  <br />
                  Pit: {site.pit_elevation_m} m
                  <br />
                  Depth: {site.basin_depth_m} m
                  <br />
                  Catchment:{" "}
                  {Math.round(site.catchment_area_m2).toLocaleString()} m²
                </Popup>
              </CircleMarker>
            </div>
          );
        })}
      </MapContainer>

      <div className="legend">
        {sites.slice(0, 6).map((s) => (
          <div key={s.rank} style={{ marginBottom: 2 }}>
            <span
              style={{ background: COLORS[(s.rank - 1) % COLORS.length] }}
            />
            Rank {s.rank}
            {s.rank === 1 ? " (recommended)" : ""}
          </div>
        ))}
      </div>
    </div>
  );
}
