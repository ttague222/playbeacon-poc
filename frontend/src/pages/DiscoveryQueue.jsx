import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import GameCard from '../components/GameCard';
import { useAuth } from '../context/AuthContext';
import '../styles/DiscoveryQueue.css';

const DiscoveryQueue = () => {
  const { user, loading: authLoading } = useAuth();
  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Fetch queue after auth is ready and a user exists
  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setLoading(false);
      setError('You must be signed in to load recommendations.');
      return;
    }
    fetchQueue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, user?.uid]);

  const fetchQueue = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getQueue(20);

      if (response.games && response.games.length > 0) {
        setQueue(response.games);
        setCurrentIndex(0);
      } else {
        setError('No games available. Try crawling some games first!');
      }
    } catch (err) {
      console.error('Error fetching queue:', err);
      if (err?.response?.status === 401) {
        setError('Authentication failed. Please sign in again.');
      } else {
        setError('Failed to load games. Make sure the backend is running and games are available.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (feedback) => {
    if (submitting || currentIndex >= queue.length) return;

    const currentGame = queue[currentIndex];
    setSubmitting(true);

    try {
      await api.submitFeedback(currentGame.universe_id, feedback);

      // Move to next game
      if (currentIndex + 1 < queue.length) {
        setCurrentIndex(currentIndex + 1);
      } else {
        // Fetch more games
        await fetchQueue();
      }
    } catch (err) {
      console.error('Error submitting feedback:', err);
      setError('Failed to submit feedback. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleLike = () => handleFeedback(1);
  const handleDislike = () => handleFeedback(-1);
  const handleSkip = () => handleFeedback(0);

  if (loading) {
    return (
      <div className="discovery-queue">
        <div className="loading">
          <div className="spinner"></div>
          <span>Loading games...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="discovery-queue">
        <div className="error">
          <h2>Error</h2>
          <p>{error}</p>
          <button className="primary-button" onClick={fetchQueue}>
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (queue.length === 0 || currentIndex >= queue.length) {
    return (
      <div className="discovery-queue">
        <div className="empty-queue">
          <h2>Queue Empty</h2>
          <p>You've seen all available games!</p>
          <button className="primary-button" onClick={fetchQueue}>
            Refresh Queue
          </button>
        </div>
      </div>
    );
  }

  const currentGame = queue[currentIndex];
  const progress = ((currentIndex + 1) / queue.length) * 100;

  return (
    <div className="discovery-queue">
      {/* Header */}
      <div className="queue-header">
        <h1>Discovery Queue</h1>
        <p className="queue-subtitle">
          Swipe through games to build your personalized recommendations
        </p>

        {/* Progress bar */}
        <div className="progress-container">
          <div className="progress-bar" style={{ width: `${progress}%` }}></div>
        </div>
        <p className="progress-text">
          {currentIndex + 1} of {queue.length}
        </p>
      </div>

      {/* Game Card */}
      <GameCard
        game={currentGame}
        onLike={handleLike}
        onDislike={handleDislike}
        onSkip={handleSkip}
        loading={submitting}
      />

      {/* Instructions */}
      <div className="instructions">
        <p>
          Like games you enjoy, dislike ones you don't, or skip to see later.
          Your recommendations will improve based on your feedback!
        </p>
      </div>
    </div>
  );
};

export default DiscoveryQueue;
