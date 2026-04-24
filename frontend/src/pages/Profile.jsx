import React, { useEffect, useState } from 'react';
import {
  collection,
  doc,
  getDoc,
  getDocs,
} from 'firebase/firestore';
import { firestore } from '../firebase';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import '../styles/Profile.css';

const Profile = () => {
  const { user, logout, upgradeAnonymousWithGoogle } = useAuth();
  const [profile, setProfile] = useState(null);
  const [recentLikes, setRecentLikes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      if (!user) return;
      setLoading(true);
      setError(null);
      try {
        const profileRef = doc(firestore, 'users', user.uid);
        const profileSnap = await getDoc(profileRef);
        setProfile(profileSnap.data() || {});

        const feedbackRef = collection(profileRef, 'feedback');
        // Get all feedback and filter in memory to avoid composite index requirement
        const allFeedback = await getDocs(feedbackRef);

        // Filter for likes (feedback === 1) and sort by timestamp
        const likes = allFeedback.docs
          .filter(doc => doc.data().feedback === 1)
          .sort((a, b) => {
            const aTime = a.data().timestamp?.toMillis?.() || 0;
            const bTime = b.data().timestamp?.toMillis?.() || 0;
            return bTime - aTime;
          })
          .slice(0, 5);

        const likedGames = [];
        for (const like of likes) {
          const universeId = like.id;
          try {
            const game = await api.getGame(universeId);
            likedGames.push({
              ...game,
              timestamp: like.data().timestamp,
            });
          } catch {
            likedGames.push({ universe_id: universeId, title: universeId });
          }
        }
        setRecentLikes(likedGames);
      } catch (err) {
        console.error(err);
        setError('Failed to load profile');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [user]);

  const handleReset = async () => {
    try {
      setResetting(true);
      await api.resetProfile();
      setRecentLikes([]);
      setProfile((prev) => ({
        ...(prev || {}),
        liked_count: 0,
        disliked_count: 0,
        profile_embedding: null,
      }));
    } catch (err) {
      setError('Could not reset profile. Try again.');
    } finally {
      setResetting(false);
    }
  };

  if (loading) {
    return (
      <div className="profile">
        <div className="loading">
          <div className="spinner"></div>
          <span>Loading profile...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="profile">
      <div className="profile-container">
        <div className="profile-header">
          <div className="profile-avatar">
            {user?.photoURL ? (
              <img src={user.photoURL} alt="Profile" style={{ width: '100%', height: '100%', borderRadius: '50%' }} />
            ) : (
              <span className="avatar-icon">🎮</span>
            )}
          </div>
          <h1>{user?.displayName || 'Your Profile'}</h1>
          <p className="user-id">{user?.email || 'Anonymous user'}</p>
          <div className="profile-actions">
            <button className="secondary-button" onClick={logout}>Sign Out</button>
          </div>
        </div>

        {user?.isAnonymous && (
          <div className="upgrade-banner">
            <div>
              <strong>Save your progress</strong>
              <p>Link your account with Google to sync across devices.</p>
            </div>
            <button className="primary-button" onClick={upgradeAnonymousWithGoogle}>
              Sign in with Google
            </button>
          </div>
        )}

        {error && <div className="profile-error">{error}</div>}

        <div className="profile-grid">
          <div className="profile-card">
            <h3>Totals</h3>
            <p>Liked games: {profile?.liked_count ?? 0}</p>
            <p>Disliked games: {profile?.disliked_count ?? 0}</p>
            <p>Joined: {profile?.created_at?.toDate ? profile.created_at.toDate().toLocaleDateString() : '—'}</p>
          </div>

          <div className="profile-card">
            <h3>Recent likes</h3>
            {recentLikes.length === 0 && <p>No likes yet</p>}
            <ul className="recent-list">
              {recentLikes.map((game) => (
                <li key={game.universe_id}>
                  <span className="recent-title">{game.title || game.universe_id}</span>
                  <span className="recent-meta">{game.creator_name}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="profile-card">
            <h3>Actions</h3>
            <button className="secondary-button" onClick={handleReset} disabled={resetting}>
              {resetting ? 'Resetting...' : 'Reset my recommendations'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Profile;
