import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  auth,
  googleProvider,
  signInAnonymously,
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  linkWithPopup,
} from '../firebase';
import { doc, getDoc } from 'firebase/firestore';
import { firestore } from '../firebase';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(null);
  const [robloxOnboardingNeeded, setRobloxOnboardingNeeded] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
      setUser(currentUser);
      setLoading(false);
      if (currentUser) {
        await checkRobloxOnboarding(currentUser.uid);
      } else {
        setRobloxOnboardingNeeded(false);
        // Only sign in anonymously if there's no user
        signInAnonymously(auth).catch((err) => {
          console.error('Anonymous sign-in failed', err);
        });
      }
    });

    return () => unsubscribe();
  }, []);

  const loginWithGoogle = async () => {
    setAuthError(null);
    await signInWithPopup(auth, googleProvider);
    if (auth.currentUser) {
      await checkRobloxOnboarding(auth.currentUser.uid);
    }
  };

  const loginWithEmail = async (email, password) => {
    setAuthError(null);
    await signInWithEmailAndPassword(auth, email, password);
    if (auth.currentUser) {
      await checkRobloxOnboarding(auth.currentUser.uid);
    }
  };

  const register = async (email, password) => {
    setAuthError(null);
    await createUserWithEmailAndPassword(auth, email, password);
    if (auth.currentUser) {
      await checkRobloxOnboarding(auth.currentUser.uid);
    }
  };

  const logout = async () => {
    await signOut(auth);
    await signInAnonymously(auth);
  };

  const upgradeAnonymousWithGoogle = async () => {
    if (!auth.currentUser?.isAnonymous) return;
    await linkWithPopup(auth.currentUser, googleProvider);
  };

  const checkRobloxOnboarding = async (uid) => {
    try {
      const userRef = doc(firestore, 'users', uid);
      const snap = await getDoc(userRef);
      const data = snap.data() || {};
      const needs = !data.roblox_imported && !data.skipped_roblox_import;
      setRobloxOnboardingNeeded(needs);
    } catch (err) {
      console.error('Error checking Roblox onboarding flag', err);
      setRobloxOnboardingNeeded(false);
    }
  };

  const markRobloxOnboardingComplete = () => setRobloxOnboardingNeeded(false);

  const value = {
    user,
    loading,
    authError,
    loginWithGoogle,
    loginWithEmail,
    register,
    logout,
    upgradeAnonymousWithGoogle,
    robloxOnboardingNeeded,
    markRobloxOnboardingComplete,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);
