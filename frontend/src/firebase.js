// Firebase Authentication in the browser. Firebase checks the password / Google account and hands us an ID token;
// the backend verifies that token and trades it for the app's own session token (see api.firebaseLogin).
import { initializeApp } from "firebase/app";
import {
  GoogleAuthProvider, createUserWithEmailAndPassword, getAuth, onAuthStateChanged,
  sendPasswordResetEmail, signInWithEmailAndPassword, signInWithPopup, signOut,
} from "firebase/auth";

const cfg = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};
export const firebaseEnabled = Boolean(cfg.apiKey && cfg.authDomain && cfg.projectId);
const auth = firebaseEnabled ? getAuth(initializeApp(cfg)) : null;

export const fb = {
  signUp: async (email, password) => (await createUserWithEmailAndPassword(auth, email, password)).user.getIdToken(),
  signIn: async (email, password) => (await signInWithEmailAndPassword(auth, email, password)).user.getIdToken(),
  google: async () => (await signInWithPopup(auth, new GoogleAuthProvider())).user.getIdToken(),
  /** A fresh ID token for the user who is signed in with Firebase right now. */
  idToken: async () => {
    if (!auth.currentUser) throw new Error("Your sign-in expired. Please sign in again.");
    return auth.currentUser.getIdToken();
  },
  reset: (email) => sendPasswordResetEmail(auth, email),
  /** Firebase remembers the user in this browser: resolves to an ID token, or null if nobody is signed in. */
  restore: () => new Promise((resolve) => {
    const off = onAuthStateChanged(auth, async (u) => { off(); resolve(u ? await u.getIdToken().catch(() => null) : null); });
  }),
};

export const fbSignOut = () => (auth ? signOut(auth).catch(() => {}) : Promise.resolve());

const MESSAGES = {
  "auth/invalid-credential": "Incorrect email or password.",
  "auth/wrong-password": "Incorrect email or password.",
  "auth/user-not-found": "Incorrect email or password.",
  "auth/email-already-in-use": "An account with this email already exists. Sign in instead.",
  "auth/weak-password": "Choose a stronger password.",
  "auth/invalid-email": "Enter a valid email address.",
  "auth/user-disabled": "This account has been disabled.",
  "auth/too-many-requests": "Too many attempts. Wait a few minutes and try again.",
  "auth/popup-closed-by-user": "Google sign-in was cancelled.",
  "auth/cancelled-popup-request": "Google sign-in was cancelled.",
  "auth/popup-blocked": "Your browser blocked the Google pop-up. Allow pop-ups and try again.",
  "auth/network-request-failed": "Network error. Check your connection.",
  "auth/operation-not-allowed": "This sign-in method isn't turned on in the Firebase console yet.",
};
export const fbMessage = (e) => MESSAGES[e?.code] ?? e?.message ?? "Something went wrong.";