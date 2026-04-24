import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import '../styles/RobloxOnboarding.css';

const RobloxOnboarding = () => {
  const navigate = useNavigate();
  const { markRobloxOnboardingComplete } = useAuth();
  const [currentScreen, setCurrentScreen] = useState(1);
  const [username, setUsername] = useState('');
  const [userData, setUserData] = useState(null);
  const [importData, setImportData] = useState(null);
  const [selectedGames, setSelectedGames] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Screen 1: Username prompt
  const handleUsernameSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const user = await api.resolveRobloxUsername(username.trim());
      setUserData(user);

      // Fetch import data
      const data = await api.getRobloxImportData(user.userId);
      setImportData(data);

      // Auto-select strong matches
      const strongMatches = new Set(
        (data.strong_matches || []).map(g => g.universeId)
      );
      setSelectedGames(strongMatches);

      setCurrentScreen(2);
    } catch (err) {
      setError('Username not found. Please check and try again.');
    } finally {
      setLoading(false);
    }
  };

  // Screen 2: Verification - move to game selection
  const handleProceedToSelection = () => {
    setCurrentScreen(3);
  };

  // Screen 3: Game selection
  const toggleGameSelection = (universeId) => {
    setSelectedGames(prev => {
      const newSet = new Set(prev);
      if (newSet.has(universeId)) {
        newSet.delete(universeId);
      } else {
        newSet.add(universeId);
      }
      return newSet;
    });
  };

  const handleImport = async () => {
    setLoading(true);
    setError(null);

    try {
      const gamesToImport = Array.from(selectedGames).map(universeId => {
        const pool = importData?.aggregated_games || [];
        const game = pool.find(g => g.universeId === universeId);
        return {
          universeId,
          score: game?.score || 1,
        };
      });

      await api.importRobloxGames(userData.userId, userData.username, gamesToImport);
      markRobloxOnboardingComplete();
      setCurrentScreen(4);
    } catch (err) {
      setError('Failed to import games. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSkip = async () => {
    try {
      setLoading(true);
      await api.skipRobloxImport();
      markRobloxOnboardingComplete();
      navigate('/');
    } catch (err) {
      setError('Unable to skip right now. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleFinish = () => {
    markRobloxOnboardingComplete();
    navigate('/');
  };

  // Screen 1: Username Prompt
  if (currentScreen === 1) {
    return (
      <div className="onboarding">
        <div className="onboarding-container">
          <div className="onboarding-header">
            <h1>Import Your Roblox Favorites</h1>
            <p>Get personalized recommendations based on games you already love</p>
          </div>

          <form onSubmit={handleUsernameSubmit} className="username-form">
            <label htmlFor="roblox-username">Enter your Roblox username</label>
            <input
              id="roblox-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              disabled={loading}
              autoFocus
            />

            {error && <div className="error-message">{error}</div>}

            <div className="form-actions">
              <button
                type="submit"
                className="primary-button"
                disabled={loading || !username.trim()}
              >
                {loading ? 'Finding account...' : 'Continue'}
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={handleSkip}
                disabled={loading}
              >
                Skip for now
              </button>
            </div>
          </form>

          <div className="onboarding-info">
            <h3>Why import?</h3>
            <ul>
              <li>Get instant personalized recommendations</li>
              <li>Discover similar games you might love</li>
              <li>Skip the cold-start and dive right in</li>
            </ul>
            <p className="privacy-note">
              We only read public data from your Roblox profile (favorites, badges, groups).
              We never access private information.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Screen 2: Account Verification
  if (currentScreen === 2) {
    return (
      <div className="onboarding">
        <div className="onboarding-container">
          <div className="onboarding-header">
            <h1>Verify Your Account</h1>
            <p>Is this your Roblox account?</p>
          </div>

          <div className="account-preview">
            {userData.avatarUrl && (
              <img
                src={userData.avatarUrl}
                alt={userData.username}
                className="account-avatar"
              />
            )}
            <h2>{userData.displayName}</h2>
            <p className="account-username">@{userData.username}</p>
            {userData.description && (
              <p className="account-description">{userData.description}</p>
            )}

            <div className="import-stats">
              <div className="stat">
                <span className="stat-value">{importData.favorite_count}</span>
                <span className="stat-label">Favorites</span>
              </div>
              <div className="stat">
                <span className="stat-value">{importData.badge_count}</span>
                <span className="stat-label">Badge Games</span>
              </div>
              <div className="stat">
                <span className="stat-value">{importData.total_games}</span>
                <span className="stat-label">Total Games</span>
              </div>
            </div>
          </div>

          <div className="form-actions">
            <button
              className="primary-button"
              onClick={handleProceedToSelection}
            >
              Yes, that's me
            </button>
            <button
              className="secondary-button"
              onClick={() => {
                setCurrentScreen(1);
                setUsername('');
                setUserData(null);
                setImportData(null);
                setError(null);
              }}
            >
              No, go back
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Screen 3: Game Selection
  if (currentScreen === 3) {
    const allGames = importData.aggregated_games || [];
    const strongMatches = importData.strong_matches || [];
    const mediumMatches = importData.medium_matches || [];

    return (
      <div className="onboarding">
        <div className="onboarding-container wide">
          <div className="onboarding-header">
            <h1>Select Games to Import</h1>
            <p>
              We found {allGames.length} games from your profile.
              Select which ones you'd like to import as "liked" games.
            </p>
            <p className="selection-count">
              {selectedGames.size} game{selectedGames.size !== 1 ? 's' : ''} selected
            </p>
          </div>

          <div className="game-selection-container">
            {strongMatches.length > 0 && (
              <div className="game-category">
                <h3>Strong Matches (Auto-selected)</h3>
                <p className="category-description">
                  Games with high engagement (favorites + multiple badges)
                </p>
                <div className="game-grid">
                  {strongMatches.map(game => (
                    <div
                      key={game.universeId}
                      className={`game-selection-card ${selectedGames.has(game.universeId) ? 'selected' : ''}`}
                      onClick={() => toggleGameSelection(game.universeId)}
                    >
                      <div className="game-selection-info">
                        <h4>{game.name || game.universeId}</h4>
                        <div className="game-meta">
                          <span className="game-source">{game.source}</span>
                          <span className="game-score">Score: {game.score}</span>
                          {game.badgeCount && (
                            <span className="badge-count">{game.badgeCount} badges</span>
                          )}
                        </div>
                      </div>
                      <div className="selection-indicator">
                        {selectedGames.has(game.universeId) ? '✓' : '+'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {mediumMatches.length > 0 && (
              <div className="game-category">
                <h3>Other Games</h3>
                <p className="category-description">
                  Games from favorites or badges
                </p>
                <div className="game-grid">
                  {mediumMatches.map(game => (
                    <div
                      key={game.universeId}
                      className={`game-selection-card ${selectedGames.has(game.universeId) ? 'selected' : ''}`}
                      onClick={() => toggleGameSelection(game.universeId)}
                    >
                      <div className="game-selection-info">
                        <h4>{game.name || game.universeId}</h4>
                        <div className="game-meta">
                          <span className="game-source">{game.source}</span>
                          <span className="game-score">Score: {game.score}</span>
                          {game.badgeCount && (
                            <span className="badge-count">{game.badgeCount} badges</span>
                          )}
                        </div>
                      </div>
                      <div className="selection-indicator">
                        {selectedGames.has(game.universeId) ? '✓' : '+'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {error && <div className="error-message">{error}</div>}

          <div className="form-actions sticky">
            <button
              className="primary-button"
              onClick={handleImport}
              disabled={loading || selectedGames.size === 0}
            >
              {loading ? 'Importing...' : `Import ${selectedGames.size} game${selectedGames.size !== 1 ? 's' : ''}`}
            </button>
            <button
              className="secondary-button"
              onClick={handleSkip}
              disabled={loading}
            >
              Skip import
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Screen 4: Success
  if (currentScreen === 4) {
    return (
      <div className="onboarding">
        <div className="onboarding-container">
          <div className="onboarding-header">
            <div className="success-icon">✓</div>
            <h1>Import Complete!</h1>
            <p>
              Successfully imported {selectedGames.size} game{selectedGames.size !== 1 ? 's' : ''} from your Roblox profile.
            </p>
          </div>

          <div className="success-info">
            <h3>What happens next?</h3>
            <ul>
              <li>Your recommendations are now personalized based on your imported games</li>
              <li>Our AI will find similar games you might enjoy</li>
              <li>The more you rate games, the better your recommendations become</li>
            </ul>
          </div>

          <div className="form-actions">
            <button
              className="primary-button"
              onClick={handleFinish}
            >
              Start Discovering Games
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default RobloxOnboarding;
