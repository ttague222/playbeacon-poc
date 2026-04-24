import React from 'react';
import '../styles/GameCard.css';

const GameCard = ({ game, onLike, onDislike, onSkip, loading }) => {
  const openRobloxGame = () => {
    window.open(`https://www.roblox.com/games/${game.universe_id}`, '_blank');
  };

  return (
    <div className="game-card">
      <div className="game-card-content">
        {/* Thumbnail */}
        <div className="game-thumbnail" onClick={openRobloxGame}>
          {game.thumbnail_url ? (
            <img src={game.thumbnail_url} alt={game.title} />
          ) : (
            <div className="no-thumbnail">No Image</div>
          )}
        </div>

        {/* Game Info */}
        <div className="game-info">
          <h2 className="game-title">{game.title}</h2>

          {game.creator_name && (
            <p className="game-creator">by {game.creator_name}</p>
          )}

          {game.description && (
            <p className="game-description">
              {game.description.length > 200
                ? `${game.description.substring(0, 200)}...`
                : game.description}
            </p>
          )}

          {/* Game Stats */}
          <div className="game-stats">
            {game.genre && (
              <span className="stat-badge genre">{game.genre}</span>
            )}
            <span className="stat-badge">
              {game.active_players?.toLocaleString() || 0} Playing
            </span>
            <span className="stat-badge">
              {game.visits?.toLocaleString() || 0} Visits
            </span>
            {game.votes_up > 0 && (
              <span className="stat-badge">
                {game.votes_up?.toLocaleString()} Likes
              </span>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="game-actions">
          <button
            className="action-button dislike"
            onClick={onDislike}
            disabled={loading}
            title="Dislike"
          >
            <span className="action-icon">👎</span>
            <span className="action-text">Dislike</span>
          </button>

          <button
            className="action-button skip"
            onClick={onSkip}
            disabled={loading}
            title="Skip"
          >
            <span className="action-icon">⏭️</span>
            <span className="action-text">Skip</span>
          </button>

          <button
            className="action-button like"
            onClick={onLike}
            disabled={loading}
            title="Like"
          >
            <span className="action-icon">👍</span>
            <span className="action-text">Like</span>
          </button>
        </div>

        {/* Open in Roblox button */}
        <button className="open-game-button" onClick={openRobloxGame}>
          Open in Roblox
        </button>
      </div>
    </div>
  );
};

export default GameCard;
