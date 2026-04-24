import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import '../styles/AdminStatusPanel.css';

const AdminStatusPanel = () => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getAdminStatus();
      setStatus(data);
    } catch (err) {
      console.error('Error fetching admin status:', err);
      setError('Failed to load status data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();

    // Auto-refresh every 10 seconds
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  if (loading && !status) {
    return (
      <div className="admin-status-panel">
        <div className="status-header">
          <h2>System Status</h2>
        </div>
        <div className="loading">Loading status...</div>
      </div>
    );
  }

  if (error && !status) {
    return (
      <div className="admin-status-panel">
        <div className="status-header">
          <h2>System Status</h2>
        </div>
        <div className="error">{error}</div>
      </div>
    );
  }

  const missingEmbeddings = status?.firestore?.games_missing_embeddings || 0;

  return (
    <div className="admin-status-panel">
      <div className="status-header">
        <h2>System Status</h2>
        <button className="refresh-button" onClick={fetchStatus} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="status-grid">
        {/* Total Games */}
        <div className="status-card">
          <div className="status-label">Games in Database</div>
          <div className="status-value">{status?.firestore?.total_games || 0}</div>
        </div>

        {/* Games with Embeddings */}
        <div className="status-card">
          <div className="status-label">Games with Embeddings</div>
          <div className="status-value">{status?.firestore?.games_with_embeddings || 0}</div>
        </div>

        {/* Missing Embeddings */}
        <div className="status-card">
          <div className="status-label">Missing Embeddings</div>
          <div className={`status-value ${missingEmbeddings > 0 ? 'status-warning' : ''}`}>
            {missingEmbeddings}
          </div>
        </div>

        {/* Pinecone Vectors */}
        <div className="status-card">
          <div className="status-label">Vectors in Pinecone</div>
          <div className="status-value">{status?.pinecone?.total_vectors || 0}</div>
        </div>

        {/* Last Crawl */}
        <div className="status-card">
          <div className="status-label">Last Crawl Run</div>
          <div className="status-value status-timestamp">
            {formatTimestamp(status?.jobs?.last_crawl)}
          </div>
        </div>

        {/* Last Embedding */}
        <div className="status-card">
          <div className="status-label">Last Embedding Run</div>
          <div className="status-value status-timestamp">
            {formatTimestamp(status?.jobs?.last_embedding)}
          </div>
        </div>
      </div>

      {/* Error Log */}
      <div className="error-log-section">
        <h3>Recent Errors</h3>
        {status?.errors && status.errors.length > 0 ? (
          <table className="error-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {status.errors.map((error, index) => (
                <tr key={index}>
                  <td className="error-timestamp">{formatTimestamp(error.timestamp)}</td>
                  <td className="error-message">{error.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="no-errors">No recent errors</div>
        )}
      </div>
    </div>
  );
};

export default AdminStatusPanel;
