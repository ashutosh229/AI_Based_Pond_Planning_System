const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

async function throwOnError(res) {
  if (res.ok) return;
  let detail = res.statusText;
  try {
    const body = await res.json();
    detail = body.detail || JSON.stringify(body);
  } catch {
    /* ignore — fall back to statusText */
  }
  throw new Error(detail);
}

/** Legacy Phase 2 endpoint: contour/basin analysis only, no pond sizing.
 * Kept for backward compatibility; the UI itself now calls
 * `recommendPond` for the KML/KMZ upload flow so both input modes return
 * the same full recommendation shape. */
export async function analyzeContour(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/api/analyzeContour`, {
    method: "POST",
    body: formData,
  });
  await throwOnError(res);
  return res.json();
}

/** Phase 3: KML/KMZ upload -> full recommendation (basin + catchment +
 * rainfall-derived pond depth/volume). */
export async function recommendPond(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/api/recommendPond`, {
    method: "POST",
    body: formData,
  });
  await throwOnError(res);
  return res.json();
}

/** Phase 3: a freeform polygon drawn on the map -> the same full
 * recommendation shape as recommendPond.
 * @param {Array<[number, number]>} polygonRing - [[lon, lat], ...] */
export async function analyzeArea(polygonRing, minBasinDepthM) {
  const body = { polygon: polygonRing };
  if (minBasinDepthM != null) body.min_basin_depth_m = minBasinDepthM;

  const res = await fetch(`${API_BASE_URL}/api/analyzeArea`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await throwOnError(res);
  return res.json();
}

/** Phase 4: fetch recent persisted analysis runs (newest-first). */
export async function getRuns(limit = 20, mode) {
  const params = new URLSearchParams({ limit });
  if (mode) params.set("mode", mode);

  const res = await fetch(`${API_BASE_URL}/api/runs?${params}`);
  await throwOnError(res);
  return res.json();
}

/** Phase 4: fetch one persisted run's full stored result payload. */
export async function getRun(runId) {
  const res = await fetch(`${API_BASE_URL}/api/runs/${runId}`);
  await throwOnError(res);
  return res.json();
}
