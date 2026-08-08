// ============================================================
//  auth.js — Google Sign-In & Auth State Management
//  Depends on: firebase-config.js (must load first)
// ============================================================

// Current authenticated user (null if not signed in)
let currentUser = null;

// ----- Auth State Observer -----
// Fires on every page load and whenever sign-in state changes.
auth.onAuthStateChanged(async (user) => {
    if (user) {
        currentUser = user;
        showApp(user);
        // Kick off the main app logic (defined in app.js)
        if (typeof onUserSignedIn === 'function') {
            await onUserSignedIn(user);
        }
    } else {
        currentUser = null;
        showLoginOverlay();
    }
});

// ----- Google Sign-In -----
async function signInWithGoogle() {
    const btn = document.getElementById('google-signin-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Signing in…';
    }
    try {
        await auth.signInWithPopup(googleProvider);
        // onAuthStateChanged will fire and call showApp()
    } catch (err) {
        console.error('Google Sign-In failed:', err);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="Google" width="20" height="20"> Sign in with Google';
        }
        const errMsg = document.getElementById('auth-error-msg');
        if (errMsg) {
            errMsg.textContent = 'Sign-in failed. Please try again.';
            errMsg.style.display = 'block';
        }
    }
}

// ----- Sign Out -----
async function signOut() {
    try {
        await auth.signOut();
        // onAuthStateChanged will fire and call showLoginOverlay()
    } catch (err) {
        console.error('Sign-out error:', err);
    }
}

// ----- Show App (post sign-in) -----
function showApp(user) {
    const overlay = document.getElementById('auth-overlay');
    const appContainer = document.querySelector('.container');
    if (overlay)       overlay.style.display = 'none';
    if (appContainer)  appContainer.style.display = 'block'; // was 'flex' — that broke layout

    // Populate user info in header
    const avatarImg  = document.getElementById('user-avatar-img');
    const userName   = document.getElementById('user-display-name');
    const userInfo   = document.getElementById('user-info-section');

    if (avatarImg && user.photoURL) {
        avatarImg.src = user.photoURL;
        avatarImg.alt = user.displayName || 'User';
    } else if (avatarImg) {
        avatarImg.src = '';
        avatarImg.alt = '';
    }
    if (userName)  userName.textContent = user.displayName || user.email || 'Student';
    if (userInfo)  userInfo.style.display = 'flex';
}

// ----- Show Login Overlay (pre sign-in) -----
function showLoginOverlay() {
    const overlay = document.getElementById('auth-overlay');
    const appContainer = document.querySelector('.container');
    if (overlay)       overlay.style.display = 'flex';
    if (appContainer)  appContainer.style.display = 'none';

    // Reset sign-in button
    const btn = document.getElementById('google-signin-btn');
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="Google" width="20" height="20"> Sign in with Google';
    }

    const userInfo = document.getElementById('user-info-section');
    if (userInfo) userInfo.style.display = 'none';
}


// ----- Helpers for app.js -----
function getCurrentUser() {
    return currentUser;
}

function getCurrentUid() {
    return currentUser ? currentUser.uid : null;
}
