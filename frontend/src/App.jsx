import { useCallback, useState } from "react";

import { analyzeArea, recommendPond } from "./api";

import FileUpload from "./components/FileUpload";
import RunHistory from "./components/RunHistory";
import ResultsSummary from "./components/ResultsSummary";
import BasinList from "./components/BasinList";
import MapView from "./components/MapView";
import PondRecommendationCard from "./components/PondRecommendationCard";

export default function App() {
  const [mode, setMode] = useState("area"); // "area" | "kml"
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedRank, setSelectedRank] = useState(1);
  const [pendingArea, setPendingArea] = useState(null);
  const [resetSignal, setResetSignal] = useState(0);
  const [minDepth, setMinDepth] = useState("");

  async function runAnalysis(promise) {
    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedRank(1);

    try {
      const data = await promise;
      setResult(data);
    } catch (err) {
      setError(err.message || "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  function handleKmlUpload(file) {
    runAnalysis(recommendPond(file));
  }

  function handleAnalyzeArea() {
    if (!pendingArea) return;

    const depth = minDepth === "" ? undefined : Number(minDepth);

    runAnalysis(analyzeArea(pendingArea, depth));
  }

  const handleAreaDrawn = useCallback((ring) => {
    setPendingArea(ring);
  }, []);

  function handleModeSwitch(nextMode) {
    if (nextMode === mode) return;

    setMode(nextMode);
    setPendingArea(null);
    setResult(null);
    setError(null);
    setSelectedRank(1);
    setResetSignal((n) => n + 1);
  }

  const allSites = result
    ? [
        ...(result.recommended_site ? [result.recommended_site] : []),
        ...result.alternative_sites,
      ]
    : [];

  const selectedSite =
    allSites.find((s) => s.rank === selectedRank) || allSites[0] || null;

  const showDrawingMap = mode === "area";

  return (
    <div className="app">
      <header className="header">
        <h1>Village Pond Planning System</h1>
        <p className="subtitle">
          Draw an area or upload a contour map — get a suggested pond site, its
          catchment, and the expected water volume.
        </p>
      </header>

      <main className="main">
        <section className="panel upload-panel">
          <h2>Choose an Input</h2>

          <div className="mode-toggle">
            <button
              type="button"
              className={mode === "area" ? "active" : ""}
              onClick={() => handleModeSwitch("area")}
            >
              Draw area on map
            </button>

            <button
              type="button"
              className={mode === "kml" ? "active" : ""}
              onClick={() => handleModeSwitch("kml")}
            >
              Upload KML / KMZ
            </button>
          </div>

          {mode === "area" ? (
            <div className="area-controls">
              <p className="notes">
                Use the polygon tool in the top-left of the map to draw (or
                freehand-drag) the area you want analyzed, then run the
                analysis. Larger areas are sampled at coarser resolution
                automatically.
              </p>

              <label
                className="notes"
                style={{ display: "block", marginBottom: "0.5rem" }}
              >
                Min basin depth (m, optional):
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  placeholder={`default ${2.0}`}
                  value={minDepth}
                  onChange={(e) => setMinDepth(e.target.value)}
                  style={{ marginLeft: "0.5rem", width: "5rem" }}
                />
              </label>

              <button
                type="button"
                className="primary-button"
                disabled={!pendingArea || loading}
                onClick={handleAnalyzeArea}
              >
                {loading ? "Analysing…" : "Analyze drawn area"}
              </button>
            </div>
          ) : (
            <FileUpload onUpload={handleKmlUpload} disabled={loading} />
          )}

          {loading && <p className="status">Analysing…</p>}
          {error && <p className="error">{error}</p>}

          {/* Persisted analysis history */}
          <details className="run-history">
            <summary>Recent Analysis Runs</summary>
            <div className="run-history-content">
              <RunHistory onLoadRun={setResult} />
            </div>
          </details>
        </section>

        {result && (
          <>
            <section className="panel">
              <ResultsSummary result={result} />
            </section>

            {result.pond_recommendation && (
              <section className="panel">
                <PondRecommendationCard
                  recommendation={result.pond_recommendation}
                />
              </section>
            )}

            <div className="results-grid">
              <section className="panel">
                <BasinList
                  sites={allSites}
                  selectedRank={selectedRank}
                  onSelect={setSelectedRank}
                />
              </section>

              <section className="panel map-panel">
                <MapView
                  sites={allSites}
                  selectedSite={selectedSite}
                  onSelectSite={setSelectedRank}
                  drawEnabled={showDrawingMap}
                  onAreaDrawn={handleAreaDrawn}
                  resetSignal={resetSignal}
                />
              </section>
            </div>
          </>
        )}

        {!result && showDrawingMap && (
          <section className="panel map-panel standalone-map">
            <MapView
              sites={[]}
              selectedSite={null}
              onSelectSite={() => {}}
              drawEnabled
              onAreaDrawn={handleAreaDrawn}
              resetSignal={resetSignal}
            />
          </section>
        )}
      </main>
    </div>
  );
}
