// SWT Study Hub - Client Logic

// Application State
let state = {
    allDecks: {}, // exam, exercises, testates, slides
    questions: [], // current deck questions
    currentQuestionIndex: 0,
    starMode: 3, // 1: Lookup, 2: Hint, 3: Solve
    selectedMcOptions: [],
    sessionAnswers: {}, // q_id -> score
    sessionUserAnswers: {}, // q_id -> user answer text/options
    sessionFeedback: {}, // q_id -> feedback object
    isReviewMode: false,
    currentReviewAttempt: null,
    progress: {
        score: 0,
        solved: {}, // question_id -> score
        userAnswers: {}, // question_id -> user answer text/options
        feedback: {}, // question_id -> { score, feedbackText, timestamp }
        streak: 0,
        lastStudyDate: null,
        history: []
    },
    hasAiKey: false
};

// DOM Elements (evaluated lazily after auth shows the container)
const views = {
    get dashboard() { return document.getElementById('dashboard-view'); },
    get study()     { return document.getElementById('study-view'); }
};

// ----- Entry point called by auth.js after Google sign-in -----
async function onUserSignedIn(user) {
    initTheme();
    await loadProgress();
    await fetchQuestions();
    updateStats();
    checkAiStatus();
    renderHistory();

    // Initialize Mermaid input listener
    const umlEditor = document.getElementById('uml-editor');
    if (umlEditor) {
        umlEditor.addEventListener('input', renderMermaid);
    }
}

// Theme still initializes on DOMContentLoaded so the overlay looks right
window.addEventListener('DOMContentLoaded', () => { initTheme(); });

// Init Theme on load
function initTheme() {
    const savedTheme = localStorage.getItem('swt_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
    
    // Initialize Mermaid configuration
    if (window.mermaid) {
        window.mermaid.initialize({
            startOnLoad: false,
            theme: savedTheme === 'light' ? 'default' : 'dark',
            securityLevel: 'loose'
        });
    }
}

// Toggle Theme
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('swt_theme', newTheme);
    updateThemeIcon(newTheme);
    
    // Update Mermaid configuration for theme
    if (window.mermaid) {
        window.mermaid.initialize({
            startOnLoad: false,
            theme: newTheme === 'light' ? 'default' : 'dark',
            securityLevel: 'loose'
        });
        
        // Re-render if UML workbench is open
        const sandbox = document.getElementById('uml-sandbox-pane');
        if (sandbox && sandbox.style.display === 'flex') {
            renderMermaid();
        }
    }
}

// Update Theme Switcher Icon
function updateThemeIcon(theme) {
    const btn = document.getElementById('theme-toggle-btn');
    if (btn) {
        btn.innerHTML = theme === 'light' ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
    }
    // Also update Moodle breadcrumb theme icon
    const moodleIcon = document.getElementById('moodle-theme-icon');
    if (moodleIcon) {
        moodleIcon.className = theme === 'light' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
    }
}

// Fetch API Key presence and update badge
async function checkAiStatus() {
    try {
        const response = await fetch('/api/questions');
        const data = await response.json();
        // Just checking connectivity and testing endpoints
        const badge = document.getElementById('ai-status-badge');
        if (data.exam && data.exam.length > 0) {
            badge.innerHTML = `<i class="fa-solid fa-brain"></i> AI Grading Active`;
            badge.style.background = 'rgba(16, 185, 129, 0.1)';
            badge.style.color = '#10b981';
            badge.style.borderColor = '#10b981';
            state.hasAiKey = true;
        } else {
            badge.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Self-Assess Mode`;
            badge.style.background = 'rgba(245, 158, 11, 0.1)';
            badge.style.color = '#f59e0b';
            badge.style.borderColor = '#f59e0b';
            state.hasAiKey = false;
        }
    } catch (e) {
        console.error("Error checking AI status", e);
    }
}

// ============================================================
//  PROGRESS — Firestore (with localStorage fallback)
// ============================================================

// Load progress from Firestore, fall back to localStorage
// Also migrates old localStorage data to Firestore on first sign-in.
async function loadProgress() {
    const uid = getCurrentUid();

    function normalizeProgress(data) {
        if (!data) return state.progress;
        return {
            score: typeof data.score === 'number' ? data.score : 0,
            solved: data.solved || {},
            userAnswers: data.userAnswers || {},
            feedback: data.feedback || {},
            streak: data.streak || 0,
            lastStudyDate: data.lastStudyDate || null,
            history: data.history || []
        };
    }

    // 1. Try Firestore first
    if (uid && typeof db !== 'undefined') {
        try {
            const snap = await db.collection('users').doc(uid).collection('data').doc('progress').get();
            if (snap.exists) {
                const data = snap.data();
                if (data && data.solved) {
                    state.progress = normalizeProgress(data);
                    // Keep localStorage in sync for offline resilience
                    localStorage.setItem('swt_study_progress', JSON.stringify(state.progress));
                    console.log('Progress loaded from Firestore.');
                    return;
                }
            }

            // Firestore has no data yet — check if localStorage has pre-existing data to migrate
            const local = localStorage.getItem('swt_study_progress');
            if (local) {
                try {
                    const localData = JSON.parse(local);
                    if (localData && localData.solved && Object.keys(localData.solved).length > 0) {
                        state.progress = normalizeProgress(localData);
                        // Upload to Firestore so it's persisted to this account
                        await db.collection('users').doc(uid).collection('data').doc('progress')
                            .set(state.progress);
                        console.log('Migrated localStorage progress to Firestore ✅');
                        return;
                    }
                } catch(e) {
                    console.warn('localStorage migration failed:', e);
                }
            }
        } catch (e) {
            console.warn('Firestore progress load failed, falling back to localStorage:', e);
        }
    }

    // 2. localStorage fallback (offline or Firestore error)
    const local = localStorage.getItem('swt_study_progress');
    if (local) {
        try {
            const parsed = JSON.parse(local);
            if (parsed) state.progress = normalizeProgress(parsed);
        } catch(e) {}
    }
}

// Save progress to Firestore + localStorage
async function saveProgress() {
    if (!state.progress.solved) state.progress.solved = {};
    if (!state.progress.userAnswers) state.progress.userAnswers = {};
    if (!state.progress.feedback) state.progress.feedback = {};

    // Update streak
    const today = new Date().toDateString();
    if (state.progress.lastStudyDate !== today) {
        if (state.progress.lastStudyDate) {
            const lastDate = new Date(state.progress.lastStudyDate);
            const diffDays = Math.ceil(Math.abs(new Date(today) - lastDate) / (1000 * 60 * 60 * 24));
            state.progress.streak = diffDays === 1 ? (state.progress.streak || 0) + 1 : 1;
        } else {
            state.progress.streak = 1;
        }
        state.progress.lastStudyDate = today;
    }

    // Always write to localStorage immediately
    localStorage.setItem('swt_study_progress', JSON.stringify(state.progress));

    // Write to Firestore in background (non-blocking)
    const uid = getCurrentUid();
    if (uid && typeof db !== 'undefined') {
        db.collection('users').doc(uid).collection('data').doc('progress')
            .set(state.progress)
            .catch(e => console.warn('Firestore progress save failed:', e));
    }

    updateStats();
}

// ============================================================
//  QUESTIONS — try Firestore, fall back to /api/questions
// ============================================================
async function fetchQuestions() {
    // 1. Try local Flask API first to get updated question data from study_data.json
    try {
        const res = await fetch('/api/questions?t=' + Date.now(), { cache: 'no-store' });
        if (res.ok) {
            state.allDecks = await res.json();
            console.log('Questions loaded from API:', state.allDecks);
            return;
        }
    } catch (e) {
        console.warn('API questions fetch failed, falling back to Firestore:', e);
    }

    // 2. Fallback: Firestore (populated by migration script)
    if (typeof db !== 'undefined') {
        try {
            const categories = ['exam', 'exercises', 'testates', 'slides', 'mock_exam'];
            const results = await Promise.all(
                categories.map(cat =>
                    db.collection('questions').doc(cat).collection('items').get()
                      .then(snap => ({ cat, docs: snap.docs.map(d => d.data()) }))
                      .catch(() => ({ cat, docs: [] }))
                )
            );
            const decks = {};
            results.forEach(({ cat, docs }) => { if (docs.length > 0) decks[cat] = docs; });

            if (Object.values(decks).some(d => d.length > 0)) {
                state.allDecks = decks;
                console.log('Questions loaded from Firestore fallback:', Object.keys(decks).map(k => `${k}:${decks[k].length}`));
                return;
            }
        } catch (e) {
            console.error('Error fetching questions from Firestore:', e);
        }
    }
}

// Update Stats Dashboard
function updateStats() {
    document.getElementById('total-score').innerText = state.progress.score;
    document.getElementById('study-streak').innerText = `${state.progress.streak} day${state.progress.streak === 1 ? '' : 's'}`;
    
    // Count total solved
    const solvedKeys = Object.keys(state.progress.solved);
    const solvedCount = solvedKeys.length;
    
    // Count total questions in database
    let totalQuestions = 0;
    Object.keys(state.allDecks).forEach(deckName => {
        totalQuestions += state.allDecks[deckName].length;
        
        // Update individual card progress bars
        const deckSolved = state.allDecks[deckName].filter(q => solvedKeys.includes(q.id)).length;
        const deckTotal = state.allDecks[deckName].length;
        const pct = deckTotal > 0 ? Math.round((deckSolved / deckTotal) * 100) : 0;
        
        const pctLabel = document.getElementById(`${deckName}-progress-pct`);
        const barFill = document.getElementById(`${deckName}-progress-bar`);
        if (pctLabel && barFill) {
            pctLabel.innerText = `${pct}%`;
            barFill.style.width = `${pct}%`;
        }
    });
    
    document.getElementById('solved-count').innerText = `${solvedCount}/${totalQuestions}`;
    const overallPct = totalQuestions > 0 ? Math.round((solvedCount / totalQuestions) * 100) : 0;
    document.getElementById('overall-progress').innerText = `${overallPct}%`;
    
    // Render topic mastery stats on dashboard
    renderTopicMastery();
}

// Start Studying a Deck (New Attempt)
function startDeck(category) {
    state.activeCategory = category;
    state.questions = state.allDecks[category] || [];
    state.isReviewMode = false;
    state.currentReviewAttempt = null;
    
    if (state.questions.length === 0) {
        alert("Deck is empty or still being parsed. Please wait or try again.");
        return;
    }
    
    // Initialize fresh session answers and metrics for NEW attempt
    state.sessionAnswers = {};
    state.sessionUserAnswers = {};
    state.sessionFeedback = {};
    state.moodleSelectedOptions = {};
    state.moodleFlags = {};
    state.currentMoodleIndex = 0;
    state.moodleShowAll = false;
    state.currentSession = {
        category: category,
        startTime: new Date().toISOString(),
        mode: state.starMode
    };
    
    // Friendly display names
    const catNames = {
        exam: 'Exam WS25-26',
        exercises: 'Exercises 1-10',
        testates: 'Testates & Pingo',
        slides: 'Lecture Slides / Terms',
        mock_exam: 'Mock Exam (Variant 2)',
        weak_topics: 'Weak Topics Review'
    };
    const displayName = catNames[category] || category.toUpperCase();
    
    // Update Moodle header
    const titleEl = document.getElementById('moodle-quiz-title');
    if (titleEl) titleEl.innerText = displayName;
    const crumbEl = document.getElementById('moodle-deck-crumb');
    if (crumbEl) crumbEl.innerText = displayName;
    const startedEl = document.getElementById('moodle-started-time');
    if (startedEl) startedEl.innerText = new Date().toLocaleString();
    const qCountEl = document.getElementById('moodle-questions-count');
    if (qCountEl) qCountEl.innerText = state.questions.length + ' questions';
    
    const statusBadge = document.querySelector('.moodle-status-badge');
    if (statusBadge) {
        statusBadge.className = 'moodle-status-badge in-progress';
        statusBadge.innerText = 'In Progress';
        statusBadge.style.background = '';
        statusBadge.style.color = '';
        statusBadge.style.borderColor = '';
    }
    
    const finishBtn = document.getElementById('moodle-finish-attempt-btn');
    if (finishBtn) {
        finishBtn.innerHTML = '<i class="fa-solid fa-flag-checkered"></i> Finish attempt';
        finishBtn.onclick = exitDeck;
    }

    updateMoodleScore();
    
    // Set legacy badge (hidden, for JS compat)
    document.getElementById('deck-badge').innerText = displayName;
    
    // Toggle View — show Moodle layout
    views.dashboard.style.display = 'none';
    views.study.style.display = 'flex';
    
    // Set initial star mode UI
    syncMoodleStarButtons();
    
    // Render the full question feed
    renderMoodleFeed();
    renderMoodleNavButtons();
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Switch Study Mode Tab (Solve vs Flashcard)
function switchStudyTab(tab) {
    state.activeStudyTab = tab;
    
    const solveBtn = document.getElementById('tab-solve-btn');
    const flashBtn = document.getElementById('tab-flashcard-btn');
    const solveArea = document.getElementById('playground-solving-area');
    const flashArea = document.getElementById('flashcard-playground-area');
    
    if (!solveBtn || !flashBtn || !solveArea || !flashArea) return;
    
    if (tab === 'solve') {
        solveBtn.classList.add('active');
        flashBtn.classList.remove('active');
        solveArea.style.display = 'block';
        flashArea.style.display = 'none';
    } else {
        solveBtn.classList.remove('active');
        flashBtn.classList.add('active');
        solveArea.style.display = 'none';
        flashArea.style.display = 'block';
        
        // Load the card data
        loadQuestion(state.currentQuestionIndex);
    }
}

// Flip Flashcard
function flipFlashcard() {
    const card = document.getElementById('flashcard-card');
    if (!card) return;
    card.classList.toggle('flipped');
    
    const gradingBlock = document.getElementById('flashcard-grading-block');
    if (gradingBlock) {
        if (card.classList.contains('flipped')) {
            gradingBlock.style.display = 'block';
        } else {
            gradingBlock.style.display = 'none';
        }
    }
}

// Rate Spaced Repetition Flashcard
function rateFlashcard(score) {
    saveScore(score);
    
    if (score >= 50) {
        confetti({
            particleCount: 40,
            spread: 40,
            origin: { y: 0.8 }
        });
    }
    
    const card = document.getElementById('flashcard-card');
    if (card) card.classList.remove('flipped');
    
    const gradingBlock = document.getElementById('flashcard-grading-block');
    if (gradingBlock) gradingBlock.style.display = 'none';
    
    setTimeout(() => {
        nextQuestion();
    }, 300);
}

// Exit studying deck
function exitDeck() {
    if (!state.isReviewMode) {
        endDeckSession();
    }
    state.isReviewMode = false;
    state.currentReviewAttempt = null;
    views.study.style.display = 'none';
    views.dashboard.style.display = 'block';
    updateStats();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Render questions sidebar (legacy — kept for JS compat, Moodle uses renderMoodleFeed)
function renderQuestionList() {
    // No-op in Moodle mode
}

// ============================================================
//  MOODLE LAYOUT RENDERING
// ============================================================

// Render all questions as Moodle-style cards in the feed
function renderMoodleFeed() {
    const feed = document.getElementById('moodle-questions-feed');
    if (!feed) return;
    feed.innerHTML = '';
    if (state.currentMoodleIndex === undefined) state.currentMoodleIndex = 0;
    if (state.moodleShowAll === undefined) state.moodleShowAll = false;

    state.questions.forEach((q, idx) => {
        try {
        const pts    = q.points_max || (q.points_earned ? q.points_earned * 2 : 2.0);
        const isMC   = Array.isArray(q.options) && q.options.length > 0;
        const solved = state.sessionAnswers && state.sessionAnswers.hasOwnProperty(q.id);
        const savedUserAns = (state.sessionUserAnswers && state.sessionUserAnswers[q.id]) || '';
        const savedFeedback = (state.sessionFeedback && state.sessionFeedback[q.id]) || null;

        // Reference image path
        let image_page = q.image_page || '';
        if (!image_page && state.activeCategory === 'exam' && q.page_num) {
            image_page = 'exam_page_' + q.page_num + '.png';
        }

        // Safe text (strip HTML)
        const questionText = String(q.question || (q.term ? 'Define: ' + q.term : 'Question ' + (idx + 1)))
            .replace(/<[^>]*>/g, '');
        const hintText     = String(q.hint || 'Try breaking the answer into core principles.')
            .replace(/<[^>]*>/g, '');
        const solVal       = Array.isArray(q.correct_answer) ? q.correct_answer.join(', ') : (q.correct_answer || '');
        const solutionText = String(solVal).replace(/<[^>]*>/g, '');

        // ── Outer block ──
        const block = document.createElement('div');
        block.className = 'moodle-question-block' + (solved ? ' completed-block' : '');
        block.id = 'moodle-qblock-' + idx;

        // ── Left strip ──
        const strip = document.createElement('div');
        strip.className = 'moodle-q-strip';

        const label = document.createElement('span');
        label.className = 'moodle-q-label';
        label.textContent = 'Question';

        const num = document.createElement('span');
        num.className = 'moodle-q-number';
        num.textContent = idx + 1;

        const status = document.createElement('span');
        status.id = 'moodle-qstatus-' + idx;
        status.className = 'moodle-q-status ' + (solved ? 'answered' : 'not-answered');
        status.textContent = solved ? 'Complete' : 'Not yet answered';

        const marks = document.createElement('div');
        marks.className = 'moodle-q-marks';
        const marksStrong = document.createElement('strong');
        marksStrong.id = 'moodle-qscore-' + idx;
        const earnedPct = (state.sessionAnswers && state.sessionAnswers[q.id]) || 0;
        const earnedPts = Math.round(pts * (earnedPct / 100) * 10) / 10;
        marksStrong.textContent = solved
            ? (earnedPts + ' / ' + pts)
            : ('Mark ' + pts + ' out of ' + pts);
        marks.appendChild(marksStrong);

        const flagBtn = document.createElement('button');
        flagBtn.id = 'moodle-qflag-' + idx;
        const flagged = state.moodleFlags && state.moodleFlags[idx];
        flagBtn.className = 'moodle-q-flag' + (flagged ? ' flagged' : '');
        flagBtn.innerHTML = '<i class="fa-' + (flagged ? 'solid' : 'regular') + ' fa-flag"></i> Flag';
        flagBtn.onclick = function() { toggleMoodleFlag(idx); };

        strip.appendChild(label);
        strip.appendChild(num);
        strip.appendChild(status);
        strip.appendChild(marks);
        strip.appendChild(flagBtn);

        // ── Right card ──
        const card = document.createElement('div');
        card.className = 'moodle-q-card';

        // Reference image
        if (image_page) {
            const img = document.createElement('img');
            img.className = 'moodle-q-refimage';
            img.src = '/static/images/' + image_page;
            img.alt = 'Reference diagram';
            img.loading = 'lazy';
            card.appendChild(img);
        }

        // Question prompt label
        const promptEl = document.createElement('p');
        promptEl.className = 'moodle-q-prompt';
        promptEl.textContent = isMC ? 'Select one or more:' : 'Write your answer:';
        card.appendChild(promptEl);

        // Question text
        const qTextEl = document.createElement('div');
        qTextEl.className = 'moodle-q-text';
        qTextEl.innerHTML = formatContentHTML(questionText);
        card.appendChild(qTextEl);

        // ── Input area ──
        if (isMC) {
            const ul = document.createElement('ul');
            ul.className = 'moodle-mc-list';

            if (savedUserAns && (!state.moodleSelectedOptions[idx] || state.moodleSelectedOptions[idx].length === 0)) {
                if (!state.moodleSelectedOptions) state.moodleSelectedOptions = {};
                if (Array.isArray(savedUserAns)) {
                    state.moodleSelectedOptions[idx] = [...savedUserAns];
                } else {
                    const matches = String(savedUserAns).match(/\([a-zA-Z0-9]\)/g);
                    if (matches) {
                        state.moodleSelectedOptions[idx] = matches;
                    } else {
                        state.moodleSelectedOptions[idx] = String(savedUserAns).split(',').map(s => s.trim()).filter(Boolean);
                    }
                }
            }
            const currentSelected = (state.moodleSelectedOptions && state.moodleSelectedOptions[idx]) || [];

            q.options.forEach((opt, oi) => {
                const li = document.createElement('li');
                const optKey = opt.substring(0, 3).trim();
                const isSelected = currentSelected.some(sel => 
                    sel.toLowerCase() === optKey.toLowerCase() || 
                    opt.toLowerCase().startsWith(sel.toLowerCase()) ||
                    sel.toLowerCase() === opt.toLowerCase()
                );

                li.className = 'moodle-mc-item' + (isSelected ? ' selected' : '');
                li.id = 'moodle-opt-' + idx + '-' + oi;
                li.onclick = function() { toggleMoodleMCOption(idx, oi, this); };

                const cb = document.createElement('div');
                cb.className = 'moodle-mc-checkbox';
                cb.innerHTML = '<i class="fa-solid fa-check"></i>';

                const optSpan = document.createElement('span');
                optSpan.innerHTML = formatContentHTML(opt);

                li.appendChild(cb);
                li.appendChild(optSpan);
                ul.appendChild(li);
            });
            card.appendChild(ul);
        } else {
            const ta = document.createElement('textarea');
            ta.className = 'moodle-textarea';
            ta.id = 'moodle-textarea-' + idx;
            ta.rows = 8;
            ta.placeholder = 'Type your detailed answer here...';
            if (savedUserAns) {
                ta.value = savedUserAns;
            }
            card.appendChild(ta);
        }

        // ── Hint panel ──
        const showHint   = state.starMode === 2;
        const showSolve  = state.starMode === 1;
        const showSubmit = state.starMode !== 1;

        const hintPanel = document.createElement('div');
        hintPanel.className = 'moodle-hint-panel';
        hintPanel.id = 'moodle-hint-' + idx;
        hintPanel.style.display = showHint ? 'block' : 'none';
        hintPanel.innerHTML = '<h4><i class="fa-solid fa-lightbulb"></i> Study Hint:</h4>';
        const hintP = document.createElement('div');
        hintP.innerHTML = formatContentHTML(hintText);
        hintPanel.appendChild(hintP);
        card.appendChild(hintPanel);

        // ── Solution panel ──
        const solPanel = document.createElement('div');
        solPanel.className = 'moodle-solution-panel';
        solPanel.id = 'moodle-solution-' + idx;
        const hasFeedback = savedFeedback && savedFeedback.feedbackText;
        solPanel.style.display = (showSolve || solved || hasFeedback) ? 'block' : 'none';
        solPanel.innerHTML = '<h4><i class="fa-solid fa-circle-check"></i> Reference Solution:</h4>';
        const solP = document.createElement('div');
        solP.innerHTML = formatContentHTML(solutionText);
        solPanel.appendChild(solP);
        card.appendChild(solPanel);

        // ── Feedback panel ──
        const fbPanel = document.createElement('div');
        fbPanel.className = 'moodle-feedback-panel';
        fbPanel.id = 'moodle-feedback-' + idx;
        fbPanel.style.display = hasFeedback ? 'block' : 'none';
        const fbScore = hasFeedback ? savedFeedback.score : 0;
        const fbScoreClass = fbScore >= 75 ? 'high' : fbScore >= 50 ? 'med' : 'low';
        fbPanel.innerHTML =
            '<div class="moodle-feedback-header">' +
            '<h4><i class="fa-solid fa-graduation-cap"></i> AI Grading Feedback:</h4>' +
            '<span id="moodle-score-badge-' + idx + '" class="score-badge ' + fbScoreClass + '">' + (hasFeedback ? fbScore + '% Correct' : '') + '</span>' +
            '</div>' +
            '<p class="moodle-feedback-text" id="moodle-feedback-text-' + idx + '">' + (hasFeedback ? String(savedFeedback.feedbackText).replace(/<[^>]*>/g, '') : '') + '</p>';
        card.appendChild(fbPanel);

        // ── Self-assess panel ──
        const selfPanel = document.createElement('div');
        selfPanel.className = 'moodle-self-assess';
        selfPanel.id = 'moodle-self-' + idx;
        selfPanel.style.display = 'none';
        selfPanel.innerHTML =
            '<h4><i class="fa-solid fa-balance-scale"></i> Grade yourself:</h4>' +
            '<p>Compare to the Reference Solution above.</p>' +
            '<div class="moodle-self-btns">' +
            '<button class="self-btn yes" onclick="moodleGradeSelf(' + idx + ', 100)"><i class="fa-solid fa-circle-check"></i> Got it! (100%)</button>' +
            '<button class="self-btn maybe" onclick="moodleGradeSelf(' + idx + ', 50)"><i class="fa-solid fa-adjust"></i> Partially (50%)</button>' +
            '<button class="self-btn no" onclick="moodleGradeSelf(' + idx + ', 0)"><i class="fa-solid fa-circle-xmark"></i> Missed it (0%)</button>' +
            '</div>';
        card.appendChild(selfPanel);

        // ── Actions row ──
        const actions = document.createElement('div');
        actions.className = 'moodle-q-actions';

        // Previous button
        if (idx > 0) {
            const prevBtn = document.createElement('button');
            prevBtn.className = 'moodle-btn moodle-btn-secondary';
            prevBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i> Previous';
            prevBtn.onclick = function() { showMoodleQuestion(idx - 1); };
            actions.appendChild(prevBtn);
        }

        // Hint button (star mode 2)
        if (showHint) {
            const hintBtn = document.createElement('button');
            hintBtn.className = 'moodle-btn moodle-btn-secondary';
            hintBtn.id = 'moodle-hint-btn-' + idx;
            hintBtn.innerHTML = '<i class="fa-solid fa-lightbulb"></i> Reveal Hint';
            hintBtn.onclick = function() { moodleRevealHint(idx); };
            actions.appendChild(hintBtn);
        }

        // Check button (star mode 2 and 3)
        const submitBtn = document.createElement('button');
        submitBtn.className = 'moodle-btn moodle-btn-primary';
        submitBtn.id = 'moodle-submit-btn-' + idx;
        submitBtn.style.display = showSubmit ? '' : 'none';
        submitBtn.innerHTML = '<span id="moodle-submit-text-' + idx + '">' + (solved ? 'Re-check' : 'Check') + '</span>' +
            '<div class="moodle-spinner" id="moodle-spinner-' + idx + '"></div>';
        submitBtn.onclick = function() { moodleSubmit(idx); };
        actions.appendChild(submitBtn);

        // Next button
        const nextBtn = document.createElement('button');
        nextBtn.className = 'moodle-btn moodle-btn-success';
        nextBtn.id = 'moodle-next-btn-' + idx;
        nextBtn.style.display = (showSolve || solved || hasFeedback) ? 'inline-flex' : 'none';
        const isLast = idx === state.questions.length - 1;
        nextBtn.innerHTML = isLast
            ? '<i class="fa-solid fa-flag-checkered"></i> Finish'
            : 'Next <i class="fa-solid fa-chevron-right"></i>';
        nextBtn.onclick = function() { moodleNextFrom(idx); };
        actions.appendChild(nextBtn);

        card.appendChild(actions);

        block.appendChild(strip);
        block.appendChild(card);
        feed.appendChild(block);
        } catch (err) {
            console.error('Error rendering question card index ' + idx, err);
        }
    });

    // Default: show only the first question (one-at-a-time mode)
    if (!state.moodleShowAll) {
        showMoodleQuestion(state.currentMoodleIndex);
    }
}

// Show a single question (one-at-a-time mode)
function showMoodleQuestion(idx) {
    const total = state.questions.length;
    if (idx < 0) idx = 0;
    if (idx >= total) idx = total - 1;
    state.currentMoodleIndex = idx;

    const feed = document.getElementById('moodle-questions-feed');
    if (!feed) return;

    // Show only this block, hide all others
    feed.querySelectorAll('.moodle-question-block').forEach((block, i) => {
        block.style.display = (i === idx) ? '' : 'none';
    });

    // Update nav sidebar: active on current, keep answered states
    document.querySelectorAll('.moodle-nav-btn').forEach((btn, i) => {
        btn.classList.toggle('nav-active', i === idx);
    });

    // Update quiz navigation counter in header
    const qCountEl = document.getElementById('moodle-questions-count');
    if (qCountEl) qCountEl.textContent = 'Question ' + (idx + 1) + ' of ' + total;

    // Scroll feed into view
    const block = document.getElementById('moodle-qblock-' + idx);
    if (block) block.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Render nav sidebar buttons
function renderMoodleNavButtons() {
    const nav = document.getElementById('moodle-nav-buttons');
    if (!nav) return;
    nav.innerHTML = '';
    state.questions.forEach((q, idx) => {
        const isSolved = state.sessionAnswers && state.sessionAnswers.hasOwnProperty(q.id);
        const isFlagged = state.moodleFlags && state.moodleFlags[idx];
        const btn = document.createElement('button');
        btn.className = 'moodle-nav-btn' + (isSolved ? ' nav-answered' : '') + (isFlagged ? ' nav-flagged' : '');
        btn.id = 'moodle-navbtn-' + idx;
        btn.textContent = idx + 1;
        btn.onclick = function() { showMoodleQuestion(idx); };
        nav.appendChild(btn);
    });

    // Legend (only add once)
    if (!document.querySelector('.moodle-nav-legend')) {
        const legend = document.createElement('div');
        legend.className = 'moodle-nav-legend';
        legend.innerHTML =
            '<div class="moodle-legend-item"><div class="moodle-legend-dot dot-unanswered"></div> Not answered</div>' +
            '<div class="moodle-legend-item"><div class="moodle-legend-dot dot-answered"></div> Answered</div>' +
            '<div class="moodle-legend-item"><div class="moodle-legend-dot dot-active"></div> Current</div>';
        const sidebar = document.querySelector('.moodle-nav-sidebar');
        if (sidebar) sidebar.appendChild(legend);
    }
}

// Scroll to a question (used in show-all mode)
function scrollToQuestion(idx) {
    if (!state.moodleShowAll) {
        showMoodleQuestion(idx);
        return;
    }
    const block = document.getElementById('moodle-qblock-' + idx);
    if (block) {
        block.scrollIntoView({ behavior: 'smooth', block: 'start' });
        block.classList.add('active-block');
        setTimeout(() => block.classList.remove('active-block'), 1800);
    }
}

// Toggle flag on a question
function toggleMoodleFlag(idx) {
    if (!state.moodleFlags) state.moodleFlags = {};
    state.moodleFlags[idx] = !state.moodleFlags[idx];
    const btn = document.getElementById(`moodle-qflag-${idx}`);
    const navBtn = document.getElementById(`moodle-navbtn-${idx}`);
    if (btn) {
        const flagged = state.moodleFlags[idx];
        btn.className = `moodle-q-flag${flagged ? ' flagged' : ''}`;
        btn.innerHTML = `<i class="fa-${flagged ? 'solid' : 'regular'} fa-flag"></i> Flag question`;
    }
    if (navBtn) {
        navBtn.classList.toggle('nav-flagged', !!state.moodleFlags[idx]);
    }
}

// Toggle MC option selection for a specific question
function toggleMoodleMCOption(qIdx, optIdx, el) {
    if (!state.moodleSelectedOptions) state.moodleSelectedOptions = {};
    if (!state.moodleSelectedOptions[qIdx]) state.moodleSelectedOptions[qIdx] = [];
    const q = state.questions[qIdx];
    if (!q || !q.options) return;
    const opt = q.options[optIdx];
    const optKey = opt.substring(0, 3).trim();
    el.classList.toggle('selected');
    if (el.classList.contains('selected')) {
        if (!state.moodleSelectedOptions[qIdx].includes(optKey)) {
            state.moodleSelectedOptions[qIdx].push(optKey);
        }
    } else {
        state.moodleSelectedOptions[qIdx] = state.moodleSelectedOptions[qIdx].filter(o => o !== optKey);
    }
}

// Reveal hint for a specific question
function moodleRevealHint(idx) {
    const panel = document.getElementById(`moodle-hint-${idx}`);
    if (panel) panel.style.display = 'block';
}

// Submit a specific question in Moodle mode
async function moodleSubmit(idx) {
    const q = state.questions[idx];
    if (!q) return;

    const isMC = q.type === 'multiple_choice' || (q.options && q.options.length > 0);
    let userAns;
    if (isMC) {
        const sel = state.moodleSelectedOptions && state.moodleSelectedOptions[idx] || [];
        if (sel.length === 0) {
            alert('Please select at least one option.');
            return;
        }
        userAns = sel.join(', ');
    } else {
        const ta = document.getElementById(`moodle-textarea-${idx}`);
        userAns = ta ? ta.value.trim() : '';
        if (!userAns) {
            alert('Please type an answer before submitting.');
            return;
        }
    }

    const submitBtn = document.getElementById(`moodle-submit-btn-${idx}`);
    const submitText = document.getElementById(`moodle-submit-text-${idx}`);
    const spinner = document.getElementById(`moodle-spinner-${idx}`);
    if (submitBtn) { submitBtn.disabled = true; }
    if (submitText) { submitText.innerText = 'Checking...'; }
    if (spinner) { spinner.style.display = 'block'; }

    try {
        const response = await fetch('/api/check-answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: q.id,
                category: q.category || state.activeCategory,
                user_answer: userAns
            })
        });
        const result = await response.json();

        if (spinner) spinner.style.display = 'none';
        if (submitText) submitText.innerText = 'Check';
        if (submitBtn) submitBtn.disabled = false;

        if (result.fallback) {
            moodleSaveScore(idx, 0, userAns, "Self-assessment mode active.");
            // Show solution + self-assessment
            const solPanel = document.getElementById(`moodle-solution-${idx}`);
            const selfPanel = document.getElementById(`moodle-self-${idx}`);
            if (solPanel) solPanel.style.display = 'block';
            if (selfPanel) selfPanel.style.display = 'block';
            if (submitBtn) submitBtn.style.display = 'none';
        } else {
            moodleShowGradingResult(idx, result.score, result.feedback, result.correct_answer, userAns);
        }
    } catch (e) {
        console.error('Error submitting moodle answer', e);
        if (spinner) spinner.style.display = 'none';
        if (submitText) submitText.innerText = 'Check';
        if (submitBtn) submitBtn.disabled = false;
        moodleSaveScore(idx, 0, userAns, "Error during grading fallback.");
        // Fallback
        const solPanel = document.getElementById(`moodle-solution-${idx}`);
        const selfPanel = document.getElementById(`moodle-self-${idx}`);
        if (solPanel) solPanel.style.display = 'block';
        if (selfPanel) selfPanel.style.display = 'block';
        if (submitBtn) submitBtn.style.display = 'none';
    }
}

// Show grading result on a specific card
function moodleShowGradingResult(idx, score, feedback, correctAnswer, userAns) {
    const feedbackPanel = document.getElementById(`moodle-feedback-${idx}`);
    const scoreBadge = document.getElementById(`moodle-score-badge-${idx}`);
    const feedbackText = document.getElementById(`moodle-feedback-text-${idx}`);
    const solPanel = document.getElementById(`moodle-solution-${idx}`);
    const submitBtn = document.getElementById(`moodle-submit-btn-${idx}`);
    const nextBtn = document.getElementById(`moodle-next-btn-${idx}`);

    if (feedbackPanel) feedbackPanel.style.display = 'block';
    if (scoreBadge) {
        scoreBadge.textContent = `${score}% Correct`;
        scoreBadge.className = 'score-badge ' + (score >= 75 ? 'high' : score >= 50 ? 'med' : 'low');
    }
    if (feedbackText) feedbackText.textContent = feedback;
    if (solPanel) {
        solPanel.style.display = 'block';
        const solContent = solPanel.querySelector('div') || solPanel.querySelector('p');
        if (solContent && correctAnswer) solContent.innerHTML = formatContentHTML(correctAnswer);
    }
    if (submitBtn) {
        submitBtn.style.display = 'inline-flex';
        const submitText = document.getElementById(`moodle-submit-text-${idx}`);
        if (submitText) submitText.innerText = 'Re-check';
    }
    if (nextBtn) nextBtn.style.display = 'inline-flex';

    // Save score, answer, and feedback
    moodleSaveScore(idx, score, userAns, feedback);

    // Confetti for high scores
    if (score >= 75) {
        confetti({ particleCount: 60, spread: 50, origin: { y: 0.8 } });
    }

    // Update UI
    moodleMarkAnswered(idx);
    updateMoodleScore();
}

// Self-assess grading for moodle per-question
function moodleGradeSelf(idx, score) {
    const q = state.questions[idx];
    let userAns = '';
    if (q) {
        const isMC = q.type === 'multiple_choice' || (q.options && q.options.length > 0);
        if (isMC) {
            const sel = state.moodleSelectedOptions && state.moodleSelectedOptions[idx] || [];
            userAns = sel.join(', ');
        } else {
            const ta = document.getElementById(`moodle-textarea-${idx}`);
            userAns = ta ? ta.value.trim() : '';
        }
    }
    moodleSaveScore(idx, score, userAns, `Self-assessed grade: ${score}%`);
    if (score >= 50) {
        confetti({ particleCount: 40, spread: 40, origin: { y: 0.8 } });
    }
    const selfPanel = document.getElementById(`moodle-self-${idx}`);
    const nextBtn = document.getElementById(`moodle-next-btn-${idx}`);
    if (selfPanel) selfPanel.style.display = 'none';
    if (nextBtn) nextBtn.style.display = 'inline-flex';
    moodleMarkAnswered(idx);
    updateMoodleScore();
}

// Save score for a specific question in Moodle mode
function moodleSaveScore(idx, score, userAns, feedbackText) {
    if (state.isReviewMode) return;
    const q = state.questions[idx];
    if (!q) return;
    if (!state.sessionAnswers) state.sessionAnswers = {};
    state.sessionAnswers[q.id] = score;

    if (!state.sessionUserAnswers) state.sessionUserAnswers = {};
    if (userAns !== undefined) state.sessionUserAnswers[q.id] = userAns;

    if (!state.sessionFeedback) state.sessionFeedback = {};
    if (feedbackText !== undefined) {
        state.sessionFeedback[q.id] = {
            score: score,
            feedbackText: feedbackText,
            timestamp: new Date().toISOString()
        };
    }

    if (!state.progress.userAnswers) state.progress.userAnswers = {};
    if (userAns !== undefined) state.progress.userAnswers[q.id] = userAns;

    if (!state.progress.feedback) state.progress.feedback = {};
    if (feedbackText !== undefined) {
        state.progress.feedback[q.id] = {
            score: score,
            feedbackText: feedbackText,
            timestamp: new Date().toISOString()
        };
    }

    const ptsMax = q.points_max || (q.points_earned ? q.points_earned * 2 : 2.0);
    const earnedPoints = Math.round(ptsMax * (score / 100) * 10) / 10;
    const prevPoints = (state.progress.solved && state.progress.solved[q.id]) || 0;
    
    if (earnedPoints >= prevPoints || state.progress.solved[q.id] === undefined) {
        state.progress.score += (earnedPoints - prevPoints);
        state.progress.solved[q.id] = earnedPoints;
    }
    saveProgress();
}

// Mark a question as answered in the left strip and nav sidebar
function moodleMarkAnswered(idx) {
    const q = state.questions[idx];
    const statusEl = document.getElementById(`moodle-qstatus-${idx}`);
    const scoreEl = document.getElementById(`moodle-qscore-${idx}`);
    const navBtn = document.getElementById(`moodle-navbtn-${idx}`);
    const block = document.getElementById(`moodle-qblock-${idx}`);
    const pts = q ? (q.points_max || (q.points_earned ? q.points_earned * 2 : 2.0)) : 2.0;
    const earned = q ? ((state.progress.solved && state.progress.solved[q.id]) || 0) : 0;

    if (statusEl) { statusEl.textContent = 'Complete'; statusEl.className = 'moodle-q-status answered'; }
    if (scoreEl) { scoreEl.innerHTML = `<strong>${earned} / ${pts}</strong>`; }
    if (navBtn) { navBtn.classList.remove('nav-active'); navBtn.classList.add('nav-answered'); }
    if (block) { block.classList.add('completed-block'); }
}

// Update score in quiz info header
function updateMoodleScore() {
    const scoreEl = document.getElementById('moodle-score-so-far');
    if (!scoreEl) return;
    
    if (!state.questions || state.questions.length === 0) {
        scoreEl.textContent = '—';
        return;
    }
    
    const totalInDeck = state.questions.length;
    
    if (state.isReviewMode && state.currentReviewAttempt) {
        const att = state.currentReviewAttempt;
        scoreEl.textContent = `${att.solvedCount} / ${att.totalCount} answered (${att.pointsEarned}/${att.pointsMax} pts)`;
        return;
    }
    
    // Count answered in current session
    const sessionSolvedCount = state.questions.filter(q => state.sessionAnswers && state.sessionAnswers.hasOwnProperty(q.id)).length;
    
    let sessionEarned = 0;
    let deckMax = 0;
    state.questions.forEach(q => {
        const pts = q.points_max || (q.points_earned ? q.points_earned * 2 : 2.0);
        deckMax += pts;
        if (state.sessionAnswers && state.sessionAnswers.hasOwnProperty(q.id)) {
            const pct = state.sessionAnswers[q.id] || 0;
            sessionEarned += (pts * (pct / 100));
        }
    });
    sessionEarned = Math.round(sessionEarned * 10) / 10;
    deckMax = Math.round(deckMax * 10) / 10;
    
    scoreEl.textContent = `${sessionSolvedCount} / ${totalInDeck} answered (${sessionEarned}/${deckMax} pts)`;
}

// Scroll to next unanswered question or show completion
function moodleNextFrom(idx) {
    // Simply advance to next question (one-at-a-time mode)
    const next = idx + 1;
    if (next < state.questions.length) {
        showMoodleQuestion(next);
    } else {
        // Last question — offer to finish
        const btn = document.getElementById('moodle-next-btn-' + idx);
        if (btn) {
            btn.innerHTML = '<i class="fa-solid fa-flag-checkered"></i> Finish';
            btn.onclick = function() {
                if (confirm('Finished! Return to dashboard?')) exitDeck();
            };
        } else {
            if (confirm('You answered all questions! Return to dashboard?')) exitDeck();
        }
    }
}

// Toggle between show-all and one-at-a-time mode
function toggleMoodleShowAll() {
    const feed = document.getElementById('moodle-questions-feed');
    if (!feed) return;
    const btn = document.querySelector('.moodle-show-all-btn');

    state.moodleShowAll = !state.moodleShowAll;

    if (state.moodleShowAll) {
        // Show all questions at once
        feed.querySelectorAll('.moodle-question-block').forEach(b => b.style.display = '');
        document.querySelectorAll('.moodle-nav-btn').forEach(b => b.classList.remove('nav-active'));
        if (btn) btn.innerHTML = '<i class="fa-solid fa-chevron-down"></i> One at a time';
        // Reset header count to total
        const qCountEl = document.getElementById('moodle-questions-count');
        if (qCountEl) qCountEl.textContent = state.questions.length + ' questions';
    } else {
        // Back to one-at-a-time — show current
        showMoodleQuestion(state.currentMoodleIndex || 0);
        if (btn) btn.innerHTML = '<i class="fa-solid fa-list"></i> Show all questions';
    }
}

// Load Question Details
function loadQuestion(index) {
    const q = state.questions[index];
    if (!q) return;
    
    // Load Flashcard details if in flashcard mode
    if (state.activeStudyTab === 'flashcard') {
        const card = document.getElementById('flashcard-card');
        if (card) card.classList.remove('flipped');
        
        const gradingBlock = document.getElementById('flashcard-grading-block');
        if (gradingBlock) gradingBlock.style.display = 'none';
        
        document.getElementById('flashcard-chapter').innerText = q.chapter || "Slide Definition";
        document.getElementById('flashcard-term').innerText = q.term || "Concept";
        document.getElementById('flashcard-back-term').innerText = q.term || "Concept";
        document.getElementById('flashcard-definition').innerText = q.definition || q.correct_answer || "";
        
        const exBox = document.getElementById('flashcard-example-box');
        const exVal = document.getElementById('flashcard-example');
        if (exBox && exVal) {
            if (q.example) {
                exVal.innerText = q.example;
                exBox.style.display = 'block';
            } else {
                exBox.style.display = 'none';
            }
        }
        return;
    }
    
    // Update Question Meta
    document.getElementById('question-index-label').innerText = `Question ${index + 1} of ${state.questions.length}`;
    
    const pts = q.points_max || (q.points_earned ? q.points_earned * 2 : 2.0);
    document.getElementById('question-points-label').innerText = `Points: ${pts}`;
    
    // Update Question Text
    document.getElementById('question-text-content').innerText = q.question || `Define the term: ${q.term}`;
    
    // Clear Workspace Input & Panels
    const mcContainer = document.getElementById('mc-options-container');
    const textContainer = document.getElementById('text-input-container');
    const textarea = document.getElementById('user-answer-input');
    
    mcContainer.style.display = 'none';
    textContainer.style.display = 'none';
    textarea.value = '';
    state.selectedMcOptions = [];
    
    // Visual / Diagram Split screen setup
    const workspace = document.getElementById('workspace-panel');
    const visualPane = document.getElementById('visual-pane');
    const refImage = document.getElementById('question-reference-image');
    const imageLabel = document.getElementById('image-page-label');
    
    // Determine diagram file
    let image_page = q.image_page;
    if (!image_page && state.activeCategory === 'exam' && q.page_num) {
        // Map exam questions to rendered exam page PNGs
        image_page = `exam_page_${q.page_num}.png`;
    }
    
    if (image_page) {
        refImage.src = `/static/images/${image_page}`;
        imageLabel.innerText = image_page;
        workspace.classList.add('split-screen');
        visualPane.style.display = 'flex';
    } else {
        workspace.classList.remove('split-screen');
        visualPane.style.display = 'none';
    }
    
    // Render Answer input depending on question type
    const isMC = q.type === 'multiple_choice' || (q.options && q.options.length > 0);
    if (isMC) {
        mcContainer.style.display = 'flex';
        mcContainer.innerHTML = '';
        q.options.forEach(opt => {
            const li = document.createElement('li');
            li.classList.add('option-item');
            
            const checkbox = document.createElement('div');
            checkbox.classList.add('option-checkbox');
            checkbox.innerHTML = '<i class="fa-solid fa-check"></i>';
            
            const textSpan = document.createElement('span');
            textSpan.innerText = opt;
            
            li.appendChild(checkbox);
            li.appendChild(textSpan);
            
            li.onclick = () => {
                li.classList.toggle('selected');
                const optText = opt.substring(0, 3).trim(); // Extract "(a)" or "(b)"
                if (li.classList.contains('selected')) {
                    state.selectedMcOptions.push(optText);
                } else {
                    state.selectedMcOptions = state.selectedMcOptions.filter(o => o !== optText);
                }
            };
            mcContainer.appendChild(li);
        });
    } else {
        textContainer.style.display = 'block';
    }
    
    // Reset buttons and panels
    document.getElementById('feedback-display').style.display = 'none';
    document.getElementById('self-assessment-display').style.display = 'none';
    document.getElementById('next-question-btn').style.display = 'none';
    document.getElementById('submit-answer-btn').style.display = 'block';
    
    // Apply star mode interface
    applyStarMode();
}

// Set Star Rating Mode (1, 2, 3 stars)
function setStarMode(mode) {
    state.starMode = mode;
    
    // Update legacy star buttons (in hidden area)
    document.querySelectorAll('.mode-star-btn').forEach((btn, idx) => {
        btn.classList.toggle('active', idx + 1 === mode);
    });
    
    // Update Moodle breadcrumb star buttons
    syncMoodleStarButtons();
    
    // If Moodle feed is rendered, re-render to apply mode
    const feed = document.getElementById('moodle-questions-feed');
    if (feed && feed.children.length > 0) {
        renderMoodleFeed();
        renderMoodleNavButtons();
    }
    
    applyStarMode();
}

// Sync Moodle breadcrumb star button active state
function syncMoodleStarButtons() {
    const modeLabels = { 1: 'Lookup Mode', 2: 'Hint Mode', 3: 'Solve Mode' };
    [1, 2, 3].forEach(n => {
        const btn = document.getElementById(`moodle-star-${n}`);
        if (btn) btn.classList.toggle('active', n === state.starMode);
    });
    const label = document.getElementById('moodle-star-label');
    if (label) label.textContent = modeLabels[state.starMode] || 'Solve Mode';
}

// Update UI elements depending on Star Mode
function applyStarMode() {
    const q = state.questions[state.currentQuestionIndex];
    if (!q) return;
    
    const hintPanel = document.getElementById('hint-display');
    const solutionPanel = document.getElementById('solution-display');
    const showHintBtn = document.getElementById('show-hint-btn');
    const submitBtn = document.getElementById('submit-answer-btn');
    const nextBtn = document.getElementById('next-question-btn');
    
    hintPanel.style.display = 'none';
    solutionPanel.style.display = 'none';
    showHintBtn.style.display = 'none';
    
    if (state.starMode === 1) {
        // Mode 1: Lookup reference solutions immediately
        solutionPanel.style.display = 'block';
        document.getElementById('solution-text-content').innerText = q.correct_answer;
        submitBtn.style.display = 'none';
        nextBtn.style.display = 'block';
    } else if (state.starMode === 2) {
        // Mode 2: Get Hints while solving
        showHintBtn.style.display = 'block';
        document.getElementById('hint-text-content').innerText = q.hint || "Try breaking the answer into core principles.";
    } else if (state.starMode === 3) {
        // Mode 3: Solve completely on your own
        // Hidden hint & solution
    }
}

// Reveal Hint in Mode 2
function revealHint() {
    const hintPanel = document.getElementById('hint-display');
    hintPanel.style.display = 'block';
}

// Submit Answer
async function submitAnswer() {
    const q = state.questions[state.currentQuestionIndex];
    if (!q) return;
    
    const userAns = q.type === 'multiple_choice' || (q.options && q.options.length > 0)
        ? state.selectedMcOptions.join(", ")
        : document.getElementById('user-answer-input').value.trim();
        
    if (!userAns) {
        alert("Please select options or type an answer before submitting.");
        return;
    }
    
    // Show spinner & disable button
    const spinner = document.getElementById('submit-btn-spinner');
    const submitText = document.getElementById('submit-btn-text');
    const submitBtn = document.getElementById('submit-answer-btn');
    
    spinner.style.display = 'block';
    submitText.innerText = 'Checking...';
    submitBtn.disabled = true;
    
    try {
        const response = await fetch('/api/check-answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: q.id,
                category: q.category || state.activeCategory,
                user_answer: userAns
            })
        });
        
        const result = await response.json();
        spinner.style.display = 'none';
        submitText.innerText = 'Submit Answer';
        submitBtn.disabled = false;
        
        if (result.fallback) {
            // Activate Self-Assessment Mode
            document.getElementById('solution-display').style.display = 'block';
            document.getElementById('solution-text-content').innerText = result.correct_answer;
            document.getElementById('self-assessment-display').style.display = 'block';
            submitBtn.style.display = 'none';
        } else {
            // Graded by Backend (MC direct match or Gemini Grading)
            showGradingResult(result.score, result.feedback, result.correct_answer);
        }
    } catch (e) {
        console.error("Error submitting answer", e);
        spinner.style.display = 'none';
        submitText.innerText = 'Submit Answer';
        submitBtn.disabled = false;
        alert("Server communication error. Falling back to self-assessment.");
        
        // Local Fallback
        document.getElementById('solution-display').style.display = 'block';
        document.getElementById('solution-text-content').innerText = q.correct_answer;
        document.getElementById('self-assessment-display').style.display = 'block';
        submitBtn.style.display = 'none';
    }
}

// Show Graded Result (AI or MC)
function showGradingResult(score, feedback, correctAnswer) {
    const feedbackPanel = document.getElementById('feedback-display');
    const scoreBadge = document.getElementById('grading-score-badge');
    const feedbackText = document.getElementById('feedback-text-content');
    const solutionPanel = document.getElementById('solution-display');
    const submitBtn = document.getElementById('submit-answer-btn');
    const nextBtn = document.getElementById('next-question-btn');
    
    feedbackPanel.style.display = 'block';
    scoreBadge.innerText = `${score}% Correct`;
    
    // Set score class colors
    scoreBadge.className = 'score-badge';
    if (score >= 75) {
        scoreBadge.classList.add('high');
        // Confetti celebration!
        confetti({
            particleCount: 80,
            spread: 60,
            origin: { y: 0.8 }
        });
        
        // Save progress score
        saveScore(score);
    } else if (score >= 50) {
        scoreBadge.classList.add('med');
        saveScore(score);
    } else {
        scoreBadge.classList.add('low');
    }
    
    feedbackText.innerText = feedback;
    
    // Show Solution panel as review
    solutionPanel.style.display = 'block';
    document.getElementById('solution-text-content').innerText = correctAnswer;
    
    submitBtn.style.display = 'none';
    nextBtn.style.display = 'block';
}

// Self-assessment grading handler
function gradeSelf(score) {
    saveScore(score);
    
    if (score >= 50) {
        confetti({
            particleCount: 50,
            spread: 50,
            origin: { y: 0.8 }
        });
    }
    
    document.getElementById('self-assessment-display').style.display = 'none';
    document.getElementById('next-question-btn').style.display = 'block';
}

// Save Score to state and sync
function saveScore(score) {
    const q = state.questions[state.currentQuestionIndex];
    if (!q) return;
    
    // Record in current session answers
    if (!state.sessionAnswers) state.sessionAnswers = {};
    state.sessionAnswers[q.id] = score;
    
    const ptsMax = q.points_max || (q.points_earned ? q.points_earned * 2 : 2.0);
    const scoreFraction = score / 100;
    const earnedPoints = Math.round(ptsMax * scoreFraction * 10) / 10;
    
    // Only update if earned points is greater than previous best
    const prevPoints = state.progress.solved[q.id] || 0;
    if (earnedPoints > prevPoints) {
        state.progress.score += (earnedPoints - prevPoints);
        state.progress.solved[q.id] = earnedPoints;
        saveProgress();
    }
}

// Next Question — fully resets UI state before loading
function nextQuestion() {
    // Explicitly reset all panels and buttons to clean state
    // (prevents stale feedback/grading panels carrying over)
    const ids = ['feedback-display','self-assessment-display','hint-display','solution-display'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
    const submitBtn = document.getElementById('submit-answer-btn');
    const nextBtn   = document.getElementById('next-question-btn');
    if (submitBtn) { submitBtn.style.display = 'block'; submitBtn.disabled = false; }
    if (nextBtn)     nextBtn.style.display = 'none';

    if (state.currentQuestionIndex + 1 < state.questions.length) {
        state.currentQuestionIndex += 1;
        loadQuestion(state.currentQuestionIndex);
        renderQuestionList();
    } else {
        alert("Deck complete! Excellent job studying software systems engineering.");
        exitDeck();
    }
}

// End the current study session and save performance to history
function endDeckSession() {
    if (!state.currentSession || !state.sessionAnswers || state.isReviewMode) return;
    
    // Auto-check any unsubmitted answers where the user selected MC options or typed text
    state.questions.forEach((q, idx) => {
        if (!state.sessionAnswers.hasOwnProperty(q.id)) {
            const isMC = Array.isArray(q.options) && q.options.length > 0;
            let userAns = '';
            
            if (isMC) {
                const sel = state.moodleSelectedOptions && state.moodleSelectedOptions[idx] || [];
                if (sel.length > 0) {
                    userAns = sel.join(', ');
                    // Auto-grade MC choices
                    const solVal = Array.isArray(q.correct_answer) ? q.correct_answer.join(', ') : (q.correct_answer || '');
                    const matchesUser = userAns.match(/\([a-zA-Z0-9]\)/g) || userAns.split(',').map(s => s.trim());
                    const matchesCorr = solVal.match(/\([a-zA-Z0-9]\)/g) || solVal.split(',').map(s => s.trim());
                    
                    const setU = new Set(matchesUser.map(s => s.toLowerCase()));
                    const setC = new Set(matchesCorr.map(s => s.toLowerCase()));
                    
                    let isEq = setU.size === setC.size;
                    if (isEq) {
                        for (let item of setU) {
                            if (!setC.has(item)) { isEq = false; break; }
                        }
                    }
                    const score = isEq ? 100 : 0;
                    const feedback = isEq ? "Correct! Well done." : ("Incorrect. Correct choice: " + solVal);
                    moodleSaveScore(idx, score, userAns, feedback);
                }
            } else {
                const ta = document.getElementById(`moodle-textarea-${idx}`);
                if (ta && ta.value.trim()) {
                    userAns = ta.value.trim();
                    moodleSaveScore(idx, 100, userAns, "Submitted with attempt.");
                }
            }
        }
    });

    const session = state.currentSession;
    let solvedInSession = 0;
    let totalScoreInSession = 0;
    let maxPossibleScore = 0;
    
    state.questions.forEach(q => {
        const pts = q.points_max || (q.points_earned ? q.points_earned * 2 : 2.0);
        
        // Did we answer this question in the current session?
        if (state.sessionAnswers && state.sessionAnswers.hasOwnProperty(q.id)) {
            solvedInSession++;
            const scorePercent = state.sessionAnswers[q.id]; // 0 to 100
            totalScoreInSession += (pts * (scorePercent / 100));
            maxPossibleScore += pts;
        }
    });
    
    if (solvedInSession > 0) {
        const pctScore = maxPossibleScore > 0 ? Math.round((totalScoreInSession / maxPossibleScore) * 100) : 0;
        
        const attempt = {
            id: 'attempt_' + Date.now(),
            category: session.category,
            timestamp: new Date().toISOString(),
            mode: session.mode,
            solvedCount: solvedInSession,
            totalCount: state.questions.length,
            score: pctScore,
            pointsEarned: Math.round(totalScoreInSession * 10) / 10,
            pointsMax: Math.round(maxPossibleScore * 10) / 10,
            sessionAnswers: { ...state.sessionAnswers },
            sessionUserAnswers: { ...state.sessionUserAnswers },
            sessionFeedback: { ...state.sessionFeedback }
        };
        
        if (!state.progress.history) {
            state.progress.history = [];
        }
        state.progress.history.unshift(attempt); // Add to the beginning of history list
    }
    
    saveProgress();
    renderHistory();
    
    state.currentSession = null;
    state.sessionAnswers = {};
    state.sessionUserAnswers = {};
    state.sessionFeedback = {};
}

// Review a past attempt from history
function reviewAttempt(attemptId) {
    const history = state.progress.history || [];
    const attempt = history.find(a => a.id === attemptId);
    if (!attempt) return;
    
    state.activeCategory = attempt.category;
    state.questions = state.allDecks[attempt.category] || [];
    state.isReviewMode = true;
    state.currentReviewAttempt = attempt;
    
    state.sessionAnswers = attempt.sessionAnswers || {};
    state.sessionUserAnswers = attempt.sessionUserAnswers || {};
    state.sessionFeedback = attempt.sessionFeedback || {};
    state.moodleSelectedOptions = {};
    state.moodleFlags = {};
    state.currentMoodleIndex = 0;
    state.moodleShowAll = false;
    
    const catNames = {
        exam: 'Exam WS25-26',
        exercises: 'Exercises 1-10',
        testates: 'Testates & Pingo',
        slides: 'Lecture Slides / Terms',
        mock_exam: 'Mock Exam (Variant 2)',
        weak_topics: 'Weak Topics Review'
    };
    const displayName = (catNames[attempt.category] || attempt.category.toUpperCase()) + ' (Review)';
    
    const titleEl = document.getElementById('moodle-quiz-title');
    if (titleEl) titleEl.innerText = displayName;
    const crumbEl = document.getElementById('moodle-deck-crumb');
    if (crumbEl) crumbEl.innerText = displayName;
    const startedEl = document.getElementById('moodle-started-time');
    if (startedEl) startedEl.innerText = new Date(attempt.timestamp).toLocaleString();
    const qCountEl = document.getElementById('moodle-questions-count');
    if (qCountEl) qCountEl.innerText = state.questions.length + ' questions';
    
    const statusBadge = document.querySelector('.moodle-status-badge');
    if (statusBadge) {
        statusBadge.className = 'moodle-status-badge finished';
        statusBadge.innerText = 'Attempt Review';
        statusBadge.style.background = 'rgba(16, 185, 129, 0.15)';
        statusBadge.style.color = '#10b981';
        statusBadge.style.borderColor = '#10b981';
    }
    
    const finishBtn = document.getElementById('moodle-finish-attempt-btn');
    if (finishBtn) {
        finishBtn.innerHTML = '<i class="fa-solid fa-arrow-left"></i> Exit Review';
        finishBtn.onclick = exitDeck;
    }
    
    updateMoodleScore();
    
    views.dashboard.style.display = 'none';
    views.study.style.display = 'flex';
    
    syncMoodleStarButtons();
    renderMoodleFeed();
    renderMoodleNavButtons();
    
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Render dynamic attempt history list in dashboard table
function renderHistory() {
    const tbody = document.getElementById('history-table-body');
    if (!tbody) return;
    
    const history = state.progress.history || [];
    if (history.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-history">No attempts recorded yet. Start studying a deck above!</td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = '';
    history.forEach(attempt => {
        const tr = document.createElement('tr');
        
        // Date formatting
        const dateObj = new Date(attempt.timestamp);
        const formattedDate = dateObj.toLocaleDateString() + ' ' + dateObj.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        // Category badge name
        let catClass = attempt.category.toLowerCase();
        let catName = attempt.category.toUpperCase();
        if (catClass === 'exercises') catName = 'EXERCISES';
        else if (catClass === 'exam') catName = 'EXAM';
        else if (catClass === 'mock_exam') catName = 'MOCK EXAM';
        
        // Stars HTML icons string
        let starsStr = '';
        for (let i = 0; i < attempt.mode; i++) {
            starsStr += '<i class="fa-solid fa-star"></i>';
        }
        
        // Score class logic
        let scoreClass = 'low';
        if (attempt.score >= 75) scoreClass = 'high';
        else if (attempt.score >= 50) scoreClass = 'med';
        
        tr.innerHTML = `
            <td><span class="history-badge ${catClass}">${catName}</span></td>
            <td>${formattedDate}</td>
            <td>
                <span class="mode-badge">
                    ${starsStr}
                    <span>(${attempt.mode}★)</span>
                </span>
            </td>
            <td>${attempt.solvedCount} / ${attempt.totalCount}</td>
            <td>
                <span class="attempt-score ${scoreClass}">${attempt.score}%</span> 
                <span style="color: var(--text-secondary); font-size: 0.8rem;">(${attempt.pointsEarned}/${attempt.pointsMax} pts)</span>
            </td>
            <td>
                <button class="moodle-btn moodle-btn-secondary" onclick="reviewAttempt('${attempt.id}')" style="padding: 0.3rem 0.65rem; font-size: 0.8rem; border-radius: 6px;">
                    <i class="fa-solid fa-magnifying-glass"></i> Review
                </button>
            </td>
        `;
        
        tbody.appendChild(tr);
    });
}

// Clear History
function clearHistory() {
    if (confirm("Are you sure you want to clear your study attempt history? This will not clear your overall question progress.")) {
        state.progress.history = [];
        saveProgress();
        renderHistory();
    }
}

// Toggle UML Sandbox Pane
function toggleUmlSandbox() {
    const sandbox = document.getElementById('uml-sandbox-pane');
    const btn = document.getElementById('toggle-uml-btn');
    if (!sandbox) return;

    const isVisible = sandbox.style.display !== 'none' && sandbox.style.display !== '';

    if (isVisible) {
        sandbox.style.display = 'none';
        if (btn) btn.classList.remove('active');
    } else {
        sandbox.style.display = 'flex';
        if (btn) btn.classList.add('active');

        // Render current content or insert initial class template if empty
        const editor = document.getElementById('uml-editor');
        if (editor && !editor.value.trim()) {
            insertUmlTemplate('class');
        } else {
            renderMermaid();
        }
    }
}

// Render Mermaid code to SVG
let mermaidTimeout = null;
function renderMermaid() {
    if (!window.mermaid) return;
    
    const editor = document.getElementById('uml-editor');
    const preview = document.getElementById('uml-preview');
    if (!editor || !preview) return;
    
    const code = editor.value.trim();
    if (!code) {
        preview.innerHTML = '<span style="color: var(--text-muted);">Empty workbench. Choose a template above.</span>';
        return;
    }
    
    // Debounce compilation to avoid stuttering as user types
    clearTimeout(mermaidTimeout);
    mermaidTimeout = setTimeout(async () => {
        try {
            preview.innerHTML = '<span class="spinner" style="display: block;"></span>';
            const uniqueId = 'mermaid-svg-' + Date.now();
            const { svg } = await window.mermaid.render(uniqueId, code);
            preview.innerHTML = svg;
        } catch (err) {
            console.warn("Mermaid parsing error", err);
            preview.innerHTML = `<div style="color: var(--color-danger); font-size: 0.85rem; text-align: left;">
                <p><strong>Syntax Error:</strong></p>
                <p style="font-family: monospace; white-space: pre-wrap; margin-top: 0.5rem;">${err.message || err.toString()}</p>
            </div>`;
            const tempEl = document.getElementById(uniqueId);
            if (tempEl) tempEl.remove();
        }
    }, 400);
}

// Insert predefined templates into editor
function insertUmlTemplate(type) {
    const editor = document.getElementById('uml-editor');
    if (!editor) return;
    
    let template = '';
    if (type === 'class') {
        template = `classDiagram
    class Customer {
        +String name
        +String email
        +placeOrder()
    }
    class Order {
        +int orderId
        +Date date
        +calculateTotal()
    }
    Customer --> Order : places`;
    } else if (type === 'sequence') {
        template = `sequenceDiagram
    actor Student
    participant System
    participant Database

    Student->>System: submitAnswer(answer)
    System->>Database: getCorrectAnswer(qId)
    Database-->>System: correctAnswer
    System-->>Student: gradingFeedback(score)`;
    } else if (type === 'state') {
        template = `stateDiagram-v2
    [*] --> Idle
    Idle --> Solving : Start Deck
    Solving --> Graded : Submit Answer
    Graded --> Solving : Next Question
    Graded --> [*] : Exit Deck`;
    } else if (type === 'er') {
        template = `erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE-ITEM : contains
    CUSTOMER {
        string name
        string email
    }
    ORDER {
        int orderId
        float totalAmount
    }`;
    }
    
    editor.value = template;
    renderMermaid();
}

// Render Topic Mastery blocks in Dashboard
function renderTopicMastery() {
    const container = document.getElementById('topic-mastery-container');
    if (!container) return;
    
    // Categorization helper
    const getTopic = (q) => {
        const text = ((q.question || '') + ' ' + (q.term || '') + ' ' + (q.chapter || '') + ' ' + (q.category || '')).toLowerCase();
        if (text.includes('test') || text.includes('qa') || text.includes('coverage') || text.includes('path') || text.includes('wert') || text.includes('äquivalenz') || text.includes('blackbox') || text.includes('whitebox') || text.includes('zwei-zweig') || text.includes('branch')) {
            return 'Testing & QA';
        }
        if (text.includes('requirement') || text.includes('anforderung') || text.includes('use-case') || text.includes('use case') || text.includes('scenario') || text.includes('context') || text.includes('kontext')) {
            return 'Requirements Eng.';
        }
        if (text.includes('architect') || text.includes('architektur') || text.includes('design') || text.includes('coupling') || text.includes('cohesion') || text.includes('hiding') || text.includes('kapselung') || text.includes('pattern') || text.includes('muster') || text.includes('kopplung') || text.includes('kohäsion')) {
            return 'Architecture & Design';
        }
        if (text.includes('process') || text.includes('prozess') || text.includes('agile') || text.includes('scrum') || text.includes('waterfall') || text.includes('sprint') || text.includes('v-modell') || text.includes('incremental')) {
            return 'Processes & Agility';
        }
        if (text.includes('adaptive') || text.includes('mape') || text.includes('control loop') || text.includes('selbst-')) {
            return 'Adaptive Systems';
        }
        return 'SE Fundamentals';
    };
    
    // Group questions by topic
    const topics = {
        'Testing & QA': { total: 0, solved: 0 },
        'Requirements Eng.': { total: 0, solved: 0 },
        'Architecture & Design': { total: 0, solved: 0 },
        'Processes & Agility': { total: 0, solved: 0 },
        'Adaptive Systems': { total: 0, solved: 0 },
        'SE Fundamentals': { total: 0, solved: 0 }
    };
    
    // Count solved
    const solvedKeys = Object.keys(state.progress.solved);
    
    Object.keys(state.allDecks).forEach(deckName => {
        state.allDecks[deckName].forEach(q => {
            const topic = getTopic(q);
            if (topics[topic] !== undefined) {
                topics[topic].total += 1;
                if (solvedKeys.includes(q.id)) {
                    topics[topic].solved += 1;
                }
            }
        });
    });
    
    // Render
    container.innerHTML = '';
    
    Object.keys(topics).forEach(topicName => {
        const stats = topics[topicName];
        const pct = stats.total > 0 ? Math.round((stats.solved / stats.total) * 100) : 0;
        
        let topicClass = 'fundamentals';
        if (topicName.includes('Testing')) topicClass = 'testing';
        else if (topicName.includes('Requirements')) topicClass = 'requirements';
        else if (topicName.includes('Architecture')) topicClass = 'architecture';
        else if (topicName.includes('Processes')) topicClass = 'processes';
        else if (topicName.includes('Adaptive')) topicClass = 'adaptive';
        
        const card = document.createElement('div');
        card.className = `topic-mastery-card ${topicClass}`;
        card.innerHTML = `
            <div class="topic-header">
                <span class="topic-name">${topicName}</span>
                <span class="topic-pct" style="font-weight:700;">${pct}%</span>
            </div>
            <div class="progress-bar-bg" style="height: 6px; margin-top: 0.5rem; background:rgba(255,255,255,0.06);">
                <div class="progress-bar-fill" style="width: ${pct}%; height: 100%; border-radius: 3px;"></div>
            </div>
            <div class="topic-meta" style="margin-top: 0.4rem; font-size: 0.8rem; color: var(--text-secondary); display: flex; justify-content: space-between;">
                <span>Solved: ${stats.solved}/${stats.total}</span>
            </div>
        `;
        container.appendChild(card);
    });
    
    // Identify weak questions (answered but score is < 50%)
    let weakQuestions = [];
    Object.keys(state.allDecks).forEach(deckName => {
        state.allDecks[deckName].forEach(q => {
            const score = state.progress.solved[q.id];
            const maxPts = q.points_max || (q.points_earned ? q.points_earned * 2 : 2.0);
            if (score !== undefined && score < maxPts * 0.5) {
                weakQuestions.push(q);
            }
        });
    });
    
    const reviewBtn = document.getElementById('review-weak-btn');
    if (reviewBtn) {
        if (weakQuestions.length > 0) {
            reviewBtn.style.display = 'inline-flex';
            reviewBtn.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Review ${weakQuestions.length} Weak Questions`;
            reviewBtn.onclick = () => startWeakQuestionsDeck(weakQuestions);
        } else {
            reviewBtn.style.display = 'none';
        }
    }
}

// Start custom study session on weak topics
function startWeakQuestionsDeck(weakQuestions) {
    state.activeCategory = 'weak_topics';
    state.questions = weakQuestions;
    state.sessionAnswers = {};
    state.moodleSelectedOptions = {};
    state.moodleFlags = {};
    state.currentMoodleIndex = 0;
    state.moodleShowAll = false;
    state.currentSession = {
        category: 'weak_topics',
        startTime: new Date().toISOString(),
        mode: state.starMode
    };
    
    const titleEl = document.getElementById('moodle-quiz-title');
    if (titleEl) titleEl.innerText = 'Weak Topics Review';
    const crumbEl = document.getElementById('moodle-deck-crumb');
    if (crumbEl) crumbEl.innerText = 'Weak Topics';
    const startedEl = document.getElementById('moodle-started-time');
    if (startedEl) startedEl.innerText = new Date().toLocaleString();
    const qCountEl = document.getElementById('moodle-questions-count');
    if (qCountEl) qCountEl.innerText = weakQuestions.length + ' questions';
    updateMoodleScore();

    document.getElementById('deck-badge').innerText = 'WEAK TOPICS';
    
    views.dashboard.style.display = 'none';
    views.study.style.display = 'flex';
    
    syncMoodleStarButtons();
    renderMoodleFeed();
    renderMoodleNavButtons();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function formatContentHTML(str) {
    if (!str) return '';
    let html = String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');

    // Fenced code blocks ```lang ... ``` or ``` ... ```
    html = html.replace(/```(?:[a-zA-Z0-9_-]+)?\n?([\s\S]*?)```/g, function(match, code) {
        return `<pre class="code-snippet"><code>${code.trim()}</code></pre>`;
    });

    // Inline code `code`
    html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    return html;
}
