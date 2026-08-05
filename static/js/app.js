// SWT Study Hub - Client Logic

// Application State
let state = {
    allDecks: {}, // exam, exercises, testates, slides
    questions: [], // current deck questions
    currentQuestionIndex: 0,
    starMode: 3, // 1: Lookup, 2: Hint, 3: Solve
    selectedMcOptions: [],
    progress: {
        score: 0,
        solved: {}, // question_id -> score
        streak: 0,
        lastStudyDate: null
    },
    hasAiKey: false
};

// DOM Elements
const views = {
    dashboard: document.getElementById('dashboard-view'),
    study: document.getElementById('study-view')
};

// Init application on load
window.addEventListener('DOMContentLoaded', async () => {
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
});

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
    if (!btn) return;
    if (theme === 'light') {
        btn.innerHTML = '<i class="fa-solid fa-sun"></i>';
    } else {
        btn.innerHTML = '<i class="fa-solid fa-moon"></i>';
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

// Load Progress from Server or localStorage
async function loadProgress() {
    try {
        const res = await fetch('/api/progress');
        if (res.ok) {
            const data = await res.json();
            if (data.solved) {
                state.progress = data;
                return;
            }
        }
    } catch (e) {
        console.warn("Failed to load progress from server, loading from localStorage.");
    }
    
    // LocalStorage Fallback
    const local = localStorage.getItem('swt_study_progress');
    if (local) {
        state.progress = JSON.parse(local);
    }
}

// Save Progress to Server & localStorage
async function saveProgress() {
    // Check Streak
    const today = new Date().toDateString();
    if (state.progress.lastStudyDate !== today) {
        if (state.progress.lastStudyDate) {
            const lastDate = new Date(state.progress.lastStudyDate);
            const diffTime = Math.abs(new Date(today) - lastDate);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            if (diffDays === 1) {
                state.progress.streak += 1;
            } else if (diffDays > 1) {
                state.progress.streak = 1;
            }
        } else {
            state.progress.streak = 1;
        }
        state.progress.lastStudyDate = today;
    }

    localStorage.setItem('swt_study_progress', JSON.stringify(state.progress));
    
    try {
        await fetch('/api/progress', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(state.progress)
        });
    } catch (e) {
        console.error("Failed to sync progress with server", e);
    }
    updateStats();
}

// Fetch all questions compiled by PDF extractor
async function fetchQuestions() {
    try {
        const res = await fetch('/api/questions');
        if (res.ok) {
            state.allDecks = await res.json();
            console.log("Loaded Decks:", state.allDecks);
        }
    } catch (e) {
        console.error("Error fetching study database", e);
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

// Start Studying a Deck
function startDeck(category) {
    state.activeCategory = category;
    state.questions = state.allDecks[category] || [];
    
    if (state.questions.length === 0) {
        alert("Deck is empty or still being parsed. Please wait or try again.");
        return;
    }
    
    // Initialize session answers and metrics
    state.sessionAnswers = {};
    state.currentSession = {
        category: category,
        startTime: new Date().toISOString(),
        mode: state.starMode
    };
    
    // Set deck badge
    let displayCategory = category.toUpperCase();
    if (category === 'mock_exam') displayCategory = 'MOCK EXAM';
    document.getElementById('deck-badge').innerText = displayCategory;
    
    // Render Question List sidebar
    renderQuestionList();
    
    // Toggle View
    views.dashboard.style.display = 'none';
    views.study.style.display = 'grid';
    
    // Study mode tabs visibility (only for slides/definitions deck)
    const modeTabs = document.getElementById('study-mode-tabs');
    if (modeTabs) {
        if (category === 'slides') {
            modeTabs.style.display = 'flex';
        } else {
            modeTabs.style.display = 'none';
        }
    }
    switchStudyTab('solve');
    
    // Load first question
    state.currentQuestionIndex = 0;
    loadQuestion(0);
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
    endDeckSession();
    views.study.style.display = 'none';
    views.dashboard.style.display = 'block';
    updateStats();
}

// Render questions sidebar
function renderQuestionList() {
    const list = document.getElementById('deck-question-list');
    list.innerHTML = '';
    
    state.questions.forEach((q, idx) => {
        const item = document.createElement('li');
        item.classList.add('question-item');
        if (idx === state.currentQuestionIndex) {
            item.classList.add('active');
        }
        if (state.progress.solved[q.id] !== undefined) {
            item.classList.add('completed');
        }
        
        // Create title
        let title = q.task_title || q.term || q.question;
        // Clean HTML tags
        title = title.replace(/<[^>]*>/g, '');
        item.innerText = `${idx + 1}. ${title}`;
        item.onclick = () => {
            state.currentQuestionIndex = idx;
            loadQuestion(idx);
            // Highlight active side list item
            document.querySelectorAll('.question-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');
        };
        list.appendChild(item);
    });
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
    
    // Update active star buttons
    document.querySelectorAll('.mode-star-btn').forEach((btn, idx) => {
        if (idx + 1 === mode) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    applyStarMode();
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

// Next Question
function nextQuestion() {
    if (state.currentQuestionIndex + 1 < state.questions.length) {
        state.currentQuestionIndex += 1;
        loadQuestion(state.currentQuestionIndex);
        renderQuestionList(); // Refresh sidebar to show completed badges
    } else {
        alert("Deck complete! Excellent job studying software systems engineering.");
        exitDeck();
    }
}

// End the current study session and save performance to history
function endDeckSession() {
    if (!state.currentSession || !state.sessionAnswers) return;
    
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
            pointsMax: Math.round(maxPossibleScore * 10) / 10
        };
        
        if (!state.progress.history) {
            state.progress.history = [];
        }
        state.progress.history.unshift(attempt); // Add to the beginning of history list
    }
    
    saveProgress();
    renderHistory();
    
    state.currentSession = null;
    state.sessionAnswers = null;
}

// Render dynamic attempt history list in dashboard table
function renderHistory() {
    const tbody = document.getElementById('history-table-body');
    if (!tbody) return;
    
    const history = state.progress.history || [];
    if (history.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-history">No attempts recorded yet. Start studying a deck above!</td>
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
    const visualPane = document.getElementById('visual-pane');
    const workspace = document.getElementById('workspace-panel');
    const btn = document.getElementById('toggle-uml-btn');
    if (!sandbox || !workspace || !btn) return;
    
    const isVisible = sandbox.style.display === 'flex';
    
    if (isVisible) {
        // Hide Sandbox
        sandbox.style.display = 'none';
        btn.classList.remove('active');
        
        // Re-evaluate if split screen is needed for visual pane
        const q = state.questions[state.currentQuestionIndex];
        let hasImage = q && (q.image_page || (state.activeCategory === 'exam' && q.page_num));
        if (hasImage) {
            visualPane.style.display = 'flex';
            workspace.classList.add('split-screen');
        } else {
            visualPane.style.display = 'none';
            workspace.classList.remove('split-screen');
        }
    } else {
        // Show Sandbox
        sandbox.style.display = 'flex';
        btn.classList.add('active');
        workspace.classList.add('split-screen');
        
        // Hide visual pane if open, to avoid 3-column clutter
        visualPane.style.display = 'none';
        
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
    state.currentSession = {
        category: 'weak_topics',
        startTime: new Date().toISOString(),
        mode: state.starMode
    };
    
    document.getElementById('deck-badge').innerText = 'WEAK TOPICS';
    renderQuestionList();
    
    views.dashboard.style.display = 'none';
    views.study.style.display = 'grid';
    
    const modeTabs = document.getElementById('study-mode-tabs');
    if (modeTabs) modeTabs.style.display = 'none';
    
    switchStudyTab('solve');
    
    state.currentQuestionIndex = 0;
    loadQuestion(0);
}
