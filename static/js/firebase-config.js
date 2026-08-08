// ============================================================
//  Firebase Configuration — softwaretechnik-hub
//  NOTE: These keys are safe to commit. Security is enforced
//  by Firestore Security Rules, not by hiding these values.
// ============================================================

const FIREBASE_CONFIG = {
    apiKey:            "AIzaSyDnFSepVtBHHzbTOnyoqtsSid-yZznGj0g",
    authDomain:        "softwaretechnik-hub.firebaseapp.com",
    projectId:         "softwaretechnik-hub",
    storageBucket:     "softwaretechnik-hub.firebasestorage.app",
    messagingSenderId: "306502605337",
    appId:             "1:306502605337:web:ba36d56fe6e5c5b113e888"
    // Analytics not used — no measurementId needed
};

// Initialize Firebase app (compat API — loaded via CDN, no build step)
firebase.initializeApp(FIREBASE_CONFIG);

// Shared service references used by auth.js and app.js
const db             = firebase.firestore();
const auth           = firebase.auth();
const googleProvider = new firebase.auth.GoogleAuthProvider();
