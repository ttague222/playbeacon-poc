import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import AdminStatusPanel from '../components/AdminStatusPanel';
import '../styles/Admin.css';

const scheduleLabels = {
  queue_worker: 'Queue worker (hourly)',
  keywords: 'Daily keywords',
  sorts: 'Daily sorts',
  graph: 'Daily graph expansion',
  embed_sweep: 'Daily embed sweep',
  thumb_fix: 'Daily thumbnail fix',
  weekly: 'Weekly deep crawl',
};

const Admin = () => {
  const [keywords, setKeywords] = useState('adventure, tycoon, horror, simulator, roleplay');
  const [limitPerKeyword, setLimitPerKeyword] = useState(50);
  const [crawling, setCrawling] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [crawlResult, setCrawlResult] = useState(null);
  const [embedResult, setEmbedResult] = useState(null);
  const [games, setGames] = useState([]);
  const [loadingGames, setLoadingGames] = useState(false);
  const [crawlerStatus, setCrawlerStatus] = useState(null);
  const [crawlerLoading, setCrawlerLoading] = useState(false);
  const [crawlerResult, setCrawlerResult] = useState(null);
  const [enqueueIds, setEnqueueIds] = useState('');
  const [processLimit, setProcessLimit] = useState(10);
  const [embedLimit, setEmbedLimit] = useState(50);
  const [keywordInput, setKeywordInput] = useState('adventure, horror, simulator');
  const [keywordLimit, setKeywordLimit] = useState(20);
  const [sortsInput, setSortsInput] = useState('popular, top_rated, recommended');
  const [sortLimit, setSortLimit] = useState(50);
  const [graphIds, setGraphIds] = useState('');
  const [fixThumbLimit, setFixThumbLimit] = useState(50);
  const [runningFull, setRunningFull] = useState(false);
  const [regenLimit, setRegenLimit] = useState(200);
  const [workerStatus, setWorkerStatus] = useState('--');
  const [nextRuns, setNextRuns] = useState({});
  const [scheduleEnabled, setScheduleEnabled] = useState({});
  const [scheduleToggles, setScheduleToggles] = useState({
    queue_worker: true,
    keywords: true,
    sorts: true,
    graph: true,
    embed_sweep: true,
    thumb_fix: true,
    weekly: true,
  });
  const [savingSchedules, setSavingSchedules] = useState(false);

  const handleCrawl = async () => {
    setCrawling(true);
    setCrawlResult(null);

    try {
      const keywordList = keywords.split(',').map((k) => k.trim());
      const result = await api.crawlGames(keywordList, limitPerKeyword);
      setCrawlResult(result);
    } catch (error) {
      console.error('Crawl error:', error);
      setCrawlResult({
        success: false,
        message: error.response?.data?.detail || 'Failed to crawl games',
      });
    } finally {
      setCrawling(false);
    }
  };

  const handleGenerateEmbeddings = async () => {
    setGenerating(true);
    setEmbedResult(null);

    try {
      const result = await api.generateEmbeddings();
      setEmbedResult(result);
    } catch (error) {
      console.error('Embedding generation error:', error);
      setEmbedResult({
        success: false,
        message: error.response?.data?.detail || 'Failed to generate embeddings',
      });
    } finally {
      setGenerating(false);
    }
  };

  const loadCrawlerStatus = async () => {
    setCrawlerLoading(true);
    try {
      const status = await api.crawlerStatus();
      setCrawlerStatus(status);
      setWorkerStatus(status.worker_status || '--');
      setNextRuns(status.next_runs || {});
      const enabled = status.schedule_enabled || {};
      setScheduleEnabled(enabled);
      setScheduleToggles((prev) => ({
        ...prev,
        ...enabled,
      }));
    } catch (err) {
      console.error('Error loading crawler status:', err);
    } finally {
      setCrawlerLoading(false);
    }
  };

  const handleProcessBatch = async () => {
    setCrawlerResult(null);
    try {
      const res = await api.crawlerProcessBatch(processLimit);
      setCrawlerResult(res);
      await loadCrawlerStatus();
    } catch (err) {
      console.error('Error processing batch:', err);
      setCrawlerResult({ success: false, message: 'Failed to process batch' });
    }
  };

  const handleEmbedMissing = async () => {
    setCrawlerResult(null);
    try {
      const res = await api.crawlerEmbedMissing(embedLimit);
      setCrawlerResult(res);
      await loadCrawlerStatus();
    } catch (err) {
      console.error('Error embedding missing:', err);
      setCrawlerResult({ success: false, message: 'Failed to embed missing games' });
    }
  };

  const handleEnqueue = async () => {
    setCrawlerResult(null);
    const ids = enqueueIds
      .split(',')
      .map((i) => i.trim())
      .filter(Boolean)
      .map((i) => Number(i));
    if (ids.length === 0) {
      setCrawlerResult({ success: false, message: 'Please enter at least one universeId' });
      return;
    }
    try {
      const res = await api.crawlerEnqueue(ids, 'manual', 7);
      setCrawlerResult(res);
      await loadCrawlerStatus();
    } catch (err) {
      console.error('Error enqueueing ids:', err);
      setCrawlerResult({ success: false, message: 'Failed to enqueue ids' });
    }
  };

  const handleEnqueueKeywords = async () => {
    setCrawlerResult(null);
    const keywordsList = keywordInput
      .split(',')
      .map((k) => k.trim())
      .filter(Boolean);
    if (keywordsList.length === 0) {
      setCrawlerResult({ success: false, message: 'Please enter at least one keyword' });
      return;
    }
    try {
      const res = await api.crawlerEnqueueKeywords(keywordsList, keywordLimit, 6);
      setCrawlerResult(res);
      await loadCrawlerStatus();
    } catch (err) {
      console.error('Error enqueuing keywords:', err);
      setCrawlerResult({ success: false, message: 'Failed to enqueue keywords' });
    }
  };

  const handleEnqueueSorts = async () => {
    setCrawlerResult(null);
    const sortsList = sortsInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (sortsList.length === 0) {
      setCrawlerResult({ success: false, message: 'Please enter at least one sort' });
      return;
    }
    try {
      const res = await api.crawlerEnqueueSorts(sortsList, sortLimit, 6);
      setCrawlerResult(res);
      await loadCrawlerStatus();
    } catch (err) {
      console.error('Error enqueuing sorts:', err);
      setCrawlerResult({ success: false, message: 'Failed to enqueue sorts' });
    }
  };

  const handleEnqueueGraph = async () => {
    setCrawlerResult(null);
    const ids = graphIds
      .split(',')
      .map((i) => i.trim())
      .filter(Boolean)
      .map((i) => Number(i));
    if (ids.length === 0) {
      setCrawlerResult({ success: false, message: 'Please enter universeIds to expand' });
      return;
    }
    try {
      const res = await api.crawlerEnqueueGraph(ids, 6);
      setCrawlerResult(res);
      await loadCrawlerStatus();
    } catch (err) {
      console.error('Error enqueuing graph expansion:', err);
      setCrawlerResult({ success: false, message: 'Failed to enqueue graph expansion' });
    }
  };

  const handleFixThumbnails = async () => {
    setCrawlerResult(null);
    try {
      const res = await api.crawlerFixThumbnails(fixThumbLimit);
      setCrawlerResult(res);
      await loadCrawlerStatus();
    } catch (err) {
      console.error('Error fixing thumbnails:', err);
      setCrawlerResult({ success: false, message: 'Failed to fix thumbnails' });
    }
  };

  const handleRegenEmbeddings = async () => {
    setCrawlerResult(null);
    try {
      const res = await api.crawlerRegenEmbeddings(regenLimit);
      setCrawlerResult(res);
      await loadCrawlerStatus();
    } catch (err) {
      console.error('Error regenerating embeddings:', err);
      setCrawlerResult({ success: false, message: 'Failed to regenerate embeddings' });
    }
  };

  const handleRunFullCrawler = async () => {
    setRunningFull(true);
    setCrawlerResult(null);
    try {
      const res = await api.crawlerRunFull();
      setCrawlerResult(res);
      await loadCrawlerStatus();
    } catch (err) {
      console.error('Error running full crawler:', err);
      setCrawlerResult({ success: false, message: 'Failed to run full crawler' });
    } finally {
      setRunningFull(false);
    }
  };

  const handleToggleChange = (key) => {
    setScheduleToggles((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleSaveScheduleToggles = async () => {
    setSavingSchedules(true);
    setCrawlerResult(null);
    try {
      const res = await api.crawlerToggleSchedule(scheduleToggles);
      setScheduleEnabled(res.enabled || {});
      setCrawlerResult({ success: true, message: 'Schedules updated' });
      await loadCrawlerStatus();
    } catch (err) {
      console.error('Error updating schedules:', err);
      setCrawlerResult({ success: false, message: 'Failed to update schedules' });
    } finally {
      setSavingSchedules(false);
    }
  };

  useEffect(() => {
    loadCrawlerStatus();
  }, []);

  const formatNextRuns = (runs) => {
    if (!runs || Object.entries(runs).length === 0) return '--';
    return Object.entries(runs)
      .map(([k, v]) => `${k}: ${v ? new Date(v).toLocaleString() : '--'}`)
      .join(' | ');
  };

  const formatScheduleEnabled = (enabled) => {
    if (!enabled || Object.entries(enabled).length === 0) return '--';
    return Object.entries(enabled)
      .map(([k, v]) => `${k}: ${v ? 'on' : 'off'}`)
      .join(' | ');
  };

  const loadGames = async () => {
    setLoadingGames(true);
    try {
      const result = await api.getGames(20, 0);
      setGames(result);
    } catch (error) {
      console.error('Error loading games:', error);
    } finally {
      setLoadingGames(false);
    }
  };

  return (
    <div className="admin">
      <div className="admin-container">
        {/* System Status */}
        <AdminStatusPanel />

        <div className="admin-header">
          <h1>Admin Panel</h1>
          <p>Manage game database, crawler, and embeddings</p>
          <p className="admin-note">Admin-only actions require an admin Firebase token.</p>
        </div>

        {/* Crawler Dashboard */}
        <div className="admin-section">
          <h2>Crawler Dashboard</h2>
          <p className="section-description">
            Monitor queue health and run crawler actions.
          </p>

          <div className="crawler-stats">
            {crawlerLoading && <p>Loading crawler status...</p>}
            {crawlerStatus && (
              <div className="crawler-grid">
                <div className="crawler-card">
                  <div className="crawler-label">Queue Length</div>
                  <div className="crawler-value">{crawlerStatus.queue_length || 0}</div>
                </div>
                <div className="crawler-card">
                  <div className="crawler-label">Missing Embeddings</div>
                  <div className="crawler-value">{crawlerStatus.missing_embeddings || 0}</div>
                </div>
                <div className="crawler-card">
                  <div className="crawler-label">Crawl Errors</div>
                  <div className="crawler-value">{crawlerStatus.crawl_errors || 0}</div>
                </div>
                <div className="crawler-card">
                  <div className="crawler-label">New Today</div>
                  <div className="crawler-value">{crawlerStatus.new_today || 0}</div>
                </div>
                <div className="crawler-card">
                  <div className="crawler-label">Last Crawl</div>
                  <div className="crawler-value small">{crawlerStatus.last_crawl || '--'}</div>
                </div>
                <div className="crawler-card">
                  <div className="crawler-label">Last Embedding</div>
                  <div className="crawler-value small">{crawlerStatus.last_embed || '--'}</div>
                </div>
                <div className="crawler-card">
                  <div className="crawler-label">Worker</div>
                  <div className="crawler-value small">{workerStatus}</div>
                </div>
                <div className="crawler-card">
                  <div className="crawler-label">Next Runs</div>
                  <div className="crawler-value small">
                    {formatNextRuns(nextRuns)}
                  </div>
                </div>
                <div className="crawler-card">
                  <div className="crawler-label">Schedules</div>
                  <div className="crawler-value small">
                    {formatScheduleEnabled(scheduleEnabled)}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="crawler-actions">
            <div className="crawler-action">
              <label>Scheduler toggles</label>
              <div className="schedule-toggle-grid">
                {Object.keys(scheduleToggles).map((key) => (
                  <label key={key} className="toggle-pill">
                    <input
                      type="checkbox"
                      checked={!!scheduleToggles[key]}
                      onChange={() => handleToggleChange(key)}
                    />
                    <span className="toggle-label">
                      {scheduleLabels[key] || key}
                    </span>
                  </label>
                ))}
              </div>
              <div className="crawler-inline">
                <button
                  className="primary-button"
                  onClick={handleSaveScheduleToggles}
                  disabled={savingSchedules}
                >
                  {savingSchedules ? 'Saving...' : 'Save Scheduler Settings'}
                </button>
                <span className="helper-text">Applies to background schedules and hourly worker.</span>
              </div>
            </div>

            <div className="crawler-action">
              <label>Run full crawler (defaults: sorts + keywords + process)</label>
              <div className="crawler-inline">
                <button className="primary-button" onClick={handleRunFullCrawler} disabled={runningFull}>
                  {runningFull ? 'Running...' : 'Run Full Crawler'}
                </button>
              </div>
            </div>

            <div className="crawler-action">
              <label>Process queue batch</label>
              <div className="crawler-inline">
                <input
                  type="number"
                  value={processLimit}
                  onChange={(e) => setProcessLimit(Number(e.target.value))}
                  min={1}
                  max={100}
                />
                <button className="primary-button" onClick={handleProcessBatch}>
                  Run Batch
                </button>
              </div>
            </div>

            <div className="crawler-action">
              <label>Embed missing games</label>
              <div className="crawler-inline">
                <input
                  type="number"
                  value={embedLimit}
                  onChange={(e) => setEmbedLimit(Number(e.target.value))}
                  min={1}
                  max={500}
                />
                <button className="primary-button" onClick={handleEmbedMissing}>
                  Embed Missing
                </button>
              </div>
            </div>

            <div className="crawler-action">
              <label>Add universeIds to queue (comma-separated)</label>
              <div className="crawler-inline">
                <input
                  type="text"
                  value={enqueueIds}
                  onChange={(e) => setEnqueueIds(e.target.value)}
                  placeholder="12345,67890"
                />
                <button className="secondary-button" onClick={handleEnqueue}>
                  Enqueue IDs
                </button>
              </div>
            </div>

            <div className="crawler-action">
              <label>Enqueue keyword crawl</label>
              <div className="crawler-inline">
                <input
                  type="text"
                  value={keywordInput}
                  onChange={(e) => setKeywordInput(e.target.value)}
                  placeholder="adventure, horror, simulator"
                />
                <input
                  type="number"
                  value={keywordLimit}
                  onChange={(e) => setKeywordLimit(Number(e.target.value))}
                  min={1}
                  max={100}
                />
                <button className="secondary-button" onClick={handleEnqueueKeywords}>
                  Enqueue Keywords
                </button>
              </div>
            </div>

            <div className="crawler-action">
              <label>Enqueue official sorts (comma-separated)</label>
              <div className="crawler-inline">
                <input
                  type="text"
                  value={sortsInput}
                  onChange={(e) => setSortsInput(e.target.value)}
                  placeholder="popular, top_rated, recommended"
                />
                <input
                  type="number"
                  value={sortLimit}
                  onChange={(e) => setSortLimit(Number(e.target.value))}
                  min={1}
                  max={200}
                />
                <button className="secondary-button" onClick={handleEnqueueSorts}>
                  Enqueue Sorts
                </button>
              </div>
            </div>

            <div className="crawler-action">
              <label>Graph expansion (related + creator games) for universeIds</label>
              <div className="crawler-inline">
                <input
                  type="text"
                  value={graphIds}
                  onChange={(e) => setGraphIds(e.target.value)}
                  placeholder="12345,67890"
                />
                <button className="secondary-button" onClick={handleEnqueueGraph}>
                  Enqueue Graph
                </button>
              </div>
            </div>

            <div className="crawler-action">
              <label>Fix missing thumbnails</label>
              <div className="crawler-inline">
                <input
                  type="number"
                  value={fixThumbLimit}
                  onChange={(e) => setFixThumbLimit(Number(e.target.value))}
                  min={1}
                  max={200}
                />
                <button className="secondary-button" onClick={handleFixThumbnails}>
                  Fix Thumbnails
                </button>
              </div>
            </div>

            <div className="crawler-action">
              <label>Regenerate embeddings (recent games)</label>
              <div className="crawler-inline">
                <input
                  type="number"
                  value={regenLimit}
                  onChange={(e) => setRegenLimit(Number(e.target.value))}
                  min={10}
                  max={1000}
                />
                <button className="secondary-button" onClick={handleRegenEmbeddings}>
                  Regen Embeddings
                </button>
              </div>
            </div>
          </div>

          {crawlerResult && (
            <div className={`result ${crawlerResult.success ? 'success' : 'error'}`}>
              <p>{crawlerResult.message || (crawlerResult.success ? 'Done' : 'Error')}</p>
              {crawlerResult.enqueued !== undefined && <p>Enqueued: {crawlerResult.enqueued}</p>}
              {crawlerResult.updated !== undefined && <p>Updated: {crawlerResult.updated}</p>}
              {crawlerResult.imported !== undefined && <p>Imported: {crawlerResult.imported}</p>}
              {crawlerResult.embedded !== undefined && <p>Embedded: {crawlerResult.embedded}</p>}
              {crawlerResult.errors !== undefined && <p>Errors: {crawlerResult.errors}</p>}
              {crawlerResult.skipped !== undefined && <p>Skipped: {crawlerResult.skipped}</p>}
            </div>
          )}
        </div>

        {/* Crawl Games Section */}
        <div className="admin-section">
          <h2>1. Crawl Roblox Games</h2>
          <p className="section-description">
            Search for games by keywords and add them to the database.
          </p>

          <div className="form-group">
            <label>Keywords (comma-separated):</label>
            <input
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="adventure, tycoon, horror"
              disabled={crawling}
            />
          </div>

          <div className="form-group">
            <label>Games per keyword:</label>
            <input
              type="number"
              value={limitPerKeyword}
              onChange={(e) => setLimitPerKeyword(Number(e.target.value))}
              min="1"
              max="100"
              disabled={crawling}
            />
          </div>

          <button
            className="primary-button"
            onClick={handleCrawl}
            disabled={crawling}
          >
            {crawling ? 'Crawling...' : 'Start Crawl'}
          </button>

          {crawlResult && (
            <div className={`result ${crawlResult.success ? 'success' : 'error'}`}>
              <p>{crawlResult.message}</p>
              {crawlResult.games_stored !== undefined && (
                <p>Games stored: {crawlResult.games_stored}</p>
              )}
            </div>
          )}
        </div>

        {/* Generate Embeddings Section */}
        <div className="admin-section">
          <h2>2. Generate AI Embeddings</h2>
          <p className="section-description">
            Generate vector embeddings for games that don't have them yet.
            This uses OpenAI's API and may take some time.
          </p>

          <button
            className="primary-button"
            onClick={handleGenerateEmbeddings}
            disabled={generating}
          >
            {generating ? 'Generating...' : 'Generate Embeddings'}
          </button>

          {embedResult && (
            <div className={`result ${embedResult.success ? 'success' : 'error'}`}>
              <p>{embedResult.message}</p>
              {embedResult.embeddings_generated !== undefined && (
                <p>Embeddings generated: {embedResult.embeddings_generated}</p>
              )}
            </div>
          )}
        </div>

        {/* View Games Section */}
        <div className="admin-section">
          <h2>3. View Games</h2>
          <p className="section-description">
            View games currently in the database.
          </p>

          <button
            className="secondary-button"
            onClick={loadGames}
            disabled={loadingGames}
          >
            {loadingGames ? 'Loading...' : 'Load Games'}
          </button>

          {games.length > 0 && (
            <div className="games-list">
              <p className="games-count">Showing {games.length} games</p>
              <div className="games-grid">
                {games.map((game) => (
                  <div key={game.universe_id} className="game-item">
                    {game.thumbnail_url && (
                      <img
                        src={game.thumbnail_url}
                        alt={game.title}
                        className="game-thumbnail"
                      />
                    )}
                    <div className="game-item-info">
                      <h3>{game.title}</h3>
                      <p className="game-item-creator">{game.creator_name}</p>
                      <p className="game-item-stats">
                        {game.active_players} playing | {game.visits} visits
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Instructions */}
        <div className="admin-section instructions">
          <h2>Getting Started</h2>
          <ol>
            <li>First, crawl games using keywords to populate the database</li>
            <li>Then, generate embeddings for all crawled games</li>
            <li>Finally, go to the Discovery Queue to start getting recommendations!</li>
          </ol>
          <p className="note">
            <strong>Note:</strong> You need an OpenAI API key set in your backend
            .env file to generate embeddings.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Admin;
