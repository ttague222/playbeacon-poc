import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom';
import DiscoveryQueue from './pages/DiscoveryQueue';
import Profile from './pages/Profile';
import Admin from './pages/Admin';
import Login from './pages/Login';
import Register from './pages/Register';
import RobloxOnboarding from './pages/RobloxOnboarding';
import ProtectedRoute from './components/ProtectedRoute';
import { useAuth } from './context/AuthContext';
import './styles/App.css';

const Navigation = () => {
  const location = useLocation();
  const { user, logout, loading } = useAuth();

  return (
    <nav className="navbar">
      <div className="navbar-content">
        <h1>PlayBeacon</h1>
        <div>
          <Link to="/" className={location.pathname === '/' ? 'active' : ''}>Queue</Link>
          <Link to="/profile" className={location.pathname === '/profile' ? 'active' : ''}>Profile</Link>
          <Link to="/admin" className={location.pathname === '/admin' ? 'active' : ''}>Admin</Link>
        </div>
        <div className="nav-auth">
          {!loading && user && (
            <>
              <span className="nav-user">
                {user.displayName || user.email || 'Anonymous user'}
              </span>
              <button className="secondary-button" onClick={logout}>Sign out</button>
            </>
          )}
          {!loading && !user && (
            <Link to="/login" className="primary-button">Sign in</Link>
          )}
        </div>
      </div>
    </nav>
  );
};

const RequireRobloxOnboarding = ({ children }) => {
  const { robloxOnboardingNeeded } = useAuth();
  const location = useLocation();

  if (robloxOnboardingNeeded && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }
  return children;
};

function App() {
  return (
    <Router>
      <div className="app">
        <Navigation />
        <main className="main-content">
          <Routes>
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <RequireRobloxOnboarding>
                    <DiscoveryQueue />
                  </RequireRobloxOnboarding>
                </ProtectedRoute>
              }
            />
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <RequireRobloxOnboarding>
                    <Profile />
                  </RequireRobloxOnboarding>
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <ProtectedRoute>
                  <RequireRobloxOnboarding>
                    <Admin />
                  </RequireRobloxOnboarding>
                </ProtectedRoute>
              }
            />
            <Route
              path="/onboarding"
              element={
                <ProtectedRoute>
                  <RobloxOnboarding />
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
