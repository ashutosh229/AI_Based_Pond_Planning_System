import { useState } from "react";
import { analyzeContour } from "./api";
import FileUpload from "./components/FileUpload";
import ResultsSummary from "./components/ResultsSummary";
import BasinList from "./components/BasinList";
import MapView from "./components/MapView";

export default function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedRank, setSelectedRank] = useState(1);

  async function handleUpload(file) {
    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedRank(1);
    try {
      const data = await analyzeContour(file);
      setResult(data);
    } catch (err) {
      setError(err.message || "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  const allSites = result
    ? [
        ...(result.recommended_site ? [result.recommended_site] : []),
        ...result.alternative_sites,
      ]
    : [];

  const selectedSite =
    allSites.find((s) => s.rank === selectedRank) || allSites[0] || null;

  return (
    <div className="app">
      <header className="header">
        <h1>Village Pond Planning System</h1>
        <p className="subtitle">Phase 2 — Contour Catchment Analysis</p>
      </header>

      <main className="main">
        <section className="panel upload-panel">
          <h2>Upload Contour Map</h2>
          <FileUpload onUpload={handleUpload} disabled={loading} />
          {loading && <p className="status">Analysing contours…</p>}
          {error && <p className="error">{error}</p>}
        </section>

        {result && (
          <>
            <section className="panel">
              <ResultsSummary result={result} />
            </section>

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
                  onSelectSite={(rank) => setSelectedRank(rank)}
                />
              </section>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
