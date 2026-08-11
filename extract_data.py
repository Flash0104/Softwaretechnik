import os
import re
import json
import fitz
import requests

# Directories
study_dir = "/Users/canbekiroglu/Downloads/SE_StudyMaterials/Can_s contribution for SWT"
app_dir = "/Users/canbekiroglu/Softwaretechnik"
output_dir = os.path.join(app_dir, "static/data")
images_dir = os.path.join(app_dir, "static/images")

os.makedirs(output_dir, exist_ok=True)
os.makedirs(images_dir, exist_ok=True)

# Read .env file manually to avoid dependency
api_key = None
env_path = os.path.join(app_dir, ".env")
if os.path.exists(env_path):
    print("Found .env file. Reading API key...")
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()
                if key in ["GEMINI_API", "GEMINI_API_KEY"]:
                    api_key = val
                    # Clean up quotes if any
                    if (api_key.startswith('"') and api_key.endswith('"')) or (api_key.startswith("'") and api_key.endswith("'")):
                        api_key = api_key[1:-1]
                    break

if api_key:
    print("Gemini API key loaded successfully.")
else:
    print("WARNING: No GEMINI_API or GEMINI_API_KEY found in .env. Falling back to local heuristics / manual parsing.")

def extract_text_from_pdf(filepath):
    try:
        doc = fitz.open(filepath)
        text = ""
        for i, page in enumerate(doc):
            text += f"\n--- PAGE {i+1} ---\n"
            text += page.get_text()
        return text
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""

def call_gemini_json_http(prompt, system_instruction=None):
    if not api_key:
        return None
    try:
        model_name = "gemini-3.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        parts = [{"text": prompt}]
        contents = [{"parts": parts}]
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
            
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        if response.status_code == 200:
            res_json = response.json()
            # Extract content from response structure
            text_response = res_json['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text_response)
        else:
            print(f"Gemini API request failed with status code {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Error during Gemini HTTP request: {e}")
        return None

# ==================== PARSING SECTION 1: EXAM ====================
def parse_exam():
    pdf_path = os.path.join(study_dir, "Exam WS25-26/Klausurkopie (1)_unlocked.pdf")
    print(f"\nParsing Exam: {pdf_path}...")
    raw_text = extract_text_from_pdf(pdf_path)
    
    prompt = f"""
    You are an expert Software Engineering tutor. Analyze the following raw text from an actual Software Engineering exam sheet.
    
    The text contains:
    - Questions (e.g. 1.1, 1.2, 1.3, etc.).
    - Student answers enclosed between "## Antwort X Beginn ##" and "## Antwort X Ende ##".
    - Points awarded for the student's answer, e.g. "PUNKTE: 2" and "** Erreichte Punkte: 1.0".
    
    Task:
    Extract all questions and structure them into a JSON list.
    CRITICAL: Translate all German text (questions, options, correct answers, hints) into clear, professional English. The final output must be 100% in English.
    
    For each question, provide:
    1. "id": e.g. "exam_1.1"
    2. "category": "Exam WS25-26"
    3. "question": The clean question text translated into English.
    4. "type": "multiple_choice" or "open"
    5. "options": If multiple choice, list the options translated into English (e.g. ["(a) ...", "(b) ..."]). Otherwise, null.
    6. "correct_answer": The actual correct answer (reference solution) in English. For multiple choice, list the correct options (e.g. ["(b)", "(d)"]). For open questions, write a concise, correct model answer in English based on standard Software Engineering lectures.
    7. "student_answer": The student's answer as extracted from the answer block (translated into English if in German, and cleaned up).
    8. "points_earned": The points the student received (float).
    9. "points_max": The maximum points for this task (from the answer block header).
    10. "hint": A small helpful tip/hint to guide a student on how to write the correct answer (in English).
    11. "page_num": The page number where this question appears (from the "--- PAGE X ---" markers).
    
    Here is the exam text:
    {raw_text}
    
    Return a JSON array of objects.
    """
    
    system_instruction = "You are a precise PDF extractor that structures exam papers into clean, high-quality English JSON schemas. All output text fields must be translated to English."
    data = call_gemini_json_http(prompt, system_instruction)
    
    if data:
        print(f"Exam parsing completed. Extracted {len(data)} questions.")
        return data
    else:
        print("Fallback Exam parsing (using heuristic local rules)...")
        # Local heuristic fallback if API key is not available
        return get_exam_fallback()

# ==================== PARSING SECTION 2: EXERCISES ====================
def parse_exercises():
    exercise_files = [
        ("ex_1_3", os.path.join(study_dir, "Exercises/SWT_TESTATE1_EX123.pdf")),
        ("ex_4_7", os.path.join(study_dir, "Exercises/SWT_TESTATE2_PREP_ENG_EX4567 (1).pdf")),
        ("ex_8_9", os.path.join(study_dir, "Exercises/SWT_TESTATE3_EX_8_9.pdf")),
        ("ex_10", os.path.join(study_dir, "Exercises/SWT_Ü10_ENG_CORRECT (1).pdf"))
    ]
    
    all_exercises = []
    
    for key, path in exercise_files:
        if not os.path.exists(path):
            print(f"File not found: {path}")
            continue
            
        print(f"\nParsing Exercises from {os.path.basename(path)}...")
        raw_text = extract_text_from_pdf(path)
        
        prompt = f"""
        Analyze the following raw text from Software Engineering exercise sheets with solutions.
        
        Extract all exercise questions (referred to as "Task X.Y") and structure them into a JSON list.
        CRITICAL: Translate any German text (questions, solutions, hints) to English. Output must be 100% in English.
        
        For each task/question, provide:
        1. "id": e.g. "exercise_1.1_a"
        2. "category": "Exercises"
        3. "sheet": e.g. "Exercise Sheet 1"
        4. "task_title": e.g. "Task 1.1: Fundamentals of Software Engineering" (in English)
        5. "question": The clean question text translated into English.
        6. "correct_answer": The official model answer / solution text translated into English.
        7. "student_answer": If there is a student solution listed, extract and translate to English. Otherwise, null.
        8. "hint": A short hint (1-2 sentences in English) on how to answer this question.
        9. "page_num": The page number (from "--- PAGE X ---" markers) where the question starts.
        
        Exercise Text:
        {raw_text}
        
        Return a JSON array of objects.
        """
        
        data = call_gemini_json_http(prompt, "You are a precise data parser extracting structured exercise tasks and solutions from course text. Translate all output text fields to English.")
        if data:
            all_exercises.extend(data)
            print(f"  Extracted {len(data)} tasks.")
        else:
            print(f"  Failed to extract tasks for {key} via Gemini. Falling back to local data.")
            # We'll merge local fallback for exercises later if empty
            
    if not all_exercises:
        return get_exercises_fallback()
        
    return all_exercises

# ==================== PARSING SECTION 3: TESTATES ====================
def parse_testates():
    t1_path = os.path.join(study_dir, "Testate Answers/SE Testat 1 Fragen English.pdf")
    pingo_path = os.path.join(study_dir, "From Arabic People/pingo-softeng (1).pdf")
    
    all_testates = []
    
    # Process Testat 1
    if os.path.exists(t1_path):
        print(f"\nParsing Testat 1: {t1_path}...")
        t1_text = extract_text_from_pdf(t1_path)
        prompt = f"""
        Extract all Testat questions and answers from the following text.
        CRITICAL: Translate any German text to English. Output must be 100% in English.
        CRITICAL: All questions MUST be formatted as Multiple Choice Questions (type: "multiple_choice").
        If a question in the source text does not have multiple-choice options, you MUST generate 3 plausible but incorrect distractor options, creating a list of 4 options total (labeled "(a) ...", "(b) ...", "(c) ...", "(d) ...") in English. 
        The correct_answer must be a list containing the correct option label(s) (e.g. ["(b)"] or ["(b)", "(d)"]).
        
        {t1_text}
        
        For each question, output:
        1. "id": e.g. "testat_1_q1"
        2. "category": "Testates / Quizzes"
        3. "quiz_name": "Testat 1"
        4. "question": The question text in English.
        5. "type": "multiple_choice"
        6. "options": A list of 4 options containing the correct answer(s) and generated distractors (e.g. ["(a) ...", "(b) ...", "(c) ...", "(d) ..."]).
        7. "correct_answer": A list of the correct option label(s) (e.g. ["(b)"] or ["(a)", "(c)"]).
        8. "hint": A helpful hint in English.
        9. "image_page": null
        
        Return a JSON array of objects.
        """
        data = call_gemini_json_http(prompt, "Extract Testat Q&A to JSON in English.")
        if data:
            all_testates.extend(data)
            print(f"  Extracted {len(data)} Testat 1 questions.")
        else:
            # Fallback for Testat 1
            all_testates.extend(get_testat1_fallback())
            
    # Process Pingo Quiz
    if os.path.exists(pingo_path):
        print(f"\nParsing Pingo Quiz: {pingo_path}...")
        pingo_text = extract_text_from_pdf(pingo_path)
        prompt = f"""
        Extract all Pingo Quiz questions and answers from the following text.
        Note: Correct answers are in bold or indicated clearly.
        CRITICAL: Translate any German text to English. Output must be 100% in English.
        CRITICAL: All questions MUST be formatted as Multiple Choice Questions (type: "multiple_choice").
        If a question in the source text does not have multiple-choice options, you MUST generate 3 plausible but incorrect distractor options, creating a list of 4 options total (labeled "(a) ...", "(b) ...", "(c) ...", "(d) ...") in English.
        The correct_answer must be a list containing the correct option label(s) (e.g. ["(b)"] or ["(b)", "(d)"]).
        
        {pingo_text}
        
        For each question, output:
        1. "id": e.g. "pingo_vl1_q1"
        2. "category": "Testates / Quizzes"
        3. "quiz_name": "Pingo Quiz"
        4. "question": The question text in English.
        5. "type": "multiple_choice"
        6. "options": A list of 4 options containing the correct answer(s) and the generated distractors (e.g. ["(a) ...", "(b) ...", "(c) ...", "(d) ..."]).
        7. "correct_answer": A list of the correct option label(s) (e.g. ["(b)"] or ["(a)", "(c)"]).
        8. "hint": A helpful hint in English.
        9. "image_page": null
        
        Return a JSON array of objects.
        """
        data = call_gemini_json_http(prompt, "Extract Pingo Q&A to JSON in English.")
        if data:
            all_testates.extend(data)
            print(f"  Extracted {len(data)} Pingo questions.")
            
    # Add Testat 2 scanned pages translated into 100% English multiple choice items
    testat2_items = [
        {
            "id": "testat_2_page_1",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 2 (Scanned Sheet)",
            "question": "Testat 2 — Page 1 (Tasks 1 & 2):\n\nTask 1: Which of the following requirements is typically classified as quality requirements (non-functional requirements)?\nTask 2: What tasks or responsibilities does the Product Owner have in Scrum?",
            "type": "multiple_choice",
            "options": [
                "(a) Task 1: The delay between key press and display must be less than 0.1 seconds.",
                "(b) Task 1: When two devices are in range, they need to exchange IDs.",
                "(c) Task 1: The app should be available 99.999% of the time.",
                "(d) Task 2: Definition of User Stories and Epics (together with the team)",
                "(e) Task 2: Representation of Stakeholder Interests",
                "(f) Task 2: Decision on items for the next release & Product Backlog Management"
            ],
            "correct_answer": ["(a)", "(c)", "(d)", "(e)", "(f)"],
            "hint": "Task 1: Performance (<0.1s) & availability (99.999%) are non-functional. Task 2: Product Owner defines user stories, represents stakeholders, decides release items, and manages the Product Backlog.",
            "image_page": "testate_2_page_1.png"
        },
        {
            "id": "testat_2_page_2",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 2 (Scanned Sheet)",
            "question": "Testat 2 — Page 2 (Tasks 3 & 4):\n\nTask 3: What distinguishes software architecture from software design?\nTask 4: What are the characteristic features of a Service-Oriented Architecture (SOA)?",
            "type": "multiple_choice",
            "options": [
                "(a) Task 3: Architecture deals with the fundamental organization and structure of the system (\"Big Picture\").",
                "(b) Task 3: Design deals with internal details such as algorithms and data structures.",
                "(c) Task 4: Communication often occurs through standard protocols such as HTTP, SOAP, or REST.",
                "(d) Task 4: The coupling is loosely done through service contracts.",
                "(e) Task 4: Applications often arise through the orchestration (linking) of existing services.",
                "(f) Task 4: Services must necessarily all be written in the same programming language."
            ],
            "correct_answer": ["(a)", "(b)", "(c)", "(d)", "(e)"],
            "hint": "Task 3: Architecture is the high-level structure ('Big Picture'), Design is internal details (algorithms/data structures). Task 4: SOA features standard protocols (HTTP/REST), loose coupling via service contracts, and service orchestration.",
            "image_page": "testate_2_page_2.png"
        },
        {
            "id": "testat_2_page_3",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 2 (Scanned Sheet)",
            "question": "Testat 2 — Page 3 (Tasks 5 & 6):\n\nTask 5: Which statements about the \"error\" hierarchy (Error, Fault, Failure) are correct?\nTask 6: What rules typically apply to equivalence class testing?",
            "type": "multiple_choice",
            "options": [
                "(a) Task 5: A failure is what the user or tester observes (e.g., incorrect output, crash).",
                "(b) Task 5: An error by the programmer can lead to a fault in the code.",
                "(c) Task 5: Debugging is the process of identifying error effects to locate the error state.",
                "(d) Task 6: For each equivalence class, a single representative is theoretically sufficient, but boundary values are often used.",
                "(e) Task 6: A test case for invalid equivalence classes should cover only one invalid class to avoid masking effects.",
                "(f) Task 6: Inputs are divided into groups of similar values assumed to be treated equally by the program."
            ],
            "correct_answer": ["(a)", "(b)", "(c)", "(d)", "(e)", "(f)"],
            "hint": "Task 5: Error (programmer mistake) -> Fault (defect in code) -> Failure (observable malfunction). Debugging locates the fault from the failure. Task 6: Equivalence classes group inputs treated equally; single representative per valid class, single invalid class per test to avoid masking.",
            "image_page": "testate_2_page_3.png"
        },
        {
            "id": "testat_2_page_4",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 2 (Scanned Sheet)",
            "question": "Testat 2 — Page 4 (Tasks 7 & 8):\n\nTask 7: Which statements about white-box testing criteria are correct?\nTask 8: Which testing levels are correctly described here?",
            "type": "multiple_choice",
            "options": [
                "(a) Task 7: Branch coverage requires that each branch in the control flow graph is traversed at least once.",
                "(b) Task 7: Loop tests are useful because branch coverage typically does not adequately test loops (e.g., 0 or m iterations).",
                "(c) Task 8: Integration test: Verifies the interaction between components and interfaces.",
                "(d) Task 8: Unit Test: Tests the smallest independent code unit (e.g., class/method) in isolation."
            ],
            "correct_answer": ["(a)", "(b)", "(c)", "(d)"],
            "hint": "Task 7: Branch coverage traverses all control flow edges; loop tests check 0/1/m iterations. Task 8: Unit test = isolated smallest code unit; Integration test = interaction between components/interfaces.",
            "image_page": "testate_2_page_4.png"
        },
        {
            "id": "testat_2_page_5",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 2 (Scanned Sheet)",
            "question": "Testat 2 — Page 5 (Tasks 9 & 10):\n\nTask 9: Which statements about software measurement are correct?\nTask 10: How do reviews and formal inspections differ?",
            "type": "multiple_choice",
            "options": [
                "(a) Task 9: Metrics are used to manage, understand, and improve projects.",
                "(b) Task 9: Lines of Code (LOC) is a measure that also counts blank lines and comments.",
                "(c) Task 9: The measure NCSS (Non-commenting Source Statements) counts only actual code statements and ignores comments.",
                "(d) Task 10: During a walkthrough, the authors guide the participants through the artifact.",
                "(e) Task 10: Formal inspections follow a strictly defined process with designated roles (e.g., moderator, recorder).",
                "(f) Task 10: Formal inspections typically have a higher effectiveness in finding errors compared to informal reviews."
            ],
            "correct_answer": ["(a)", "(b)", "(c)", "(d)", "(e)", "(f)"],
            "hint": "Task 9: LOC counts blank lines/comments, while NCSS counts only actual code statements. Task 10: Walkthrough is author-guided; formal inspections have strict process roles (moderator, recorder) and higher defect detection effectiveness without in-meeting solutioning.",
            "image_page": "testate_2_page_5.png"
        }
    ]
    all_testates.extend(testat2_items)
        
    testat3_items = [
        {
            "id": "testat_3_page_1",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "How can the terms software process, process model, and lifecycle model be distinguished from each other?",
            "type": "multiple_choice",
            "options": [
                "(a) A software process model abstracts from concrete processes and defines roles and types of activities.",
                "(b) A lifecycle model is an instantiation of a software process.",
                "(c) A software process corresponds to the actual execution of software development.",
                "(d) The boundary between lifecycle model and process model is always clearly defined."
            ],
            "correct_answer": ["(a)", "(c)"],
            "hint": "Software process = actual execution; process model = abstraction and definition of roles/activities.",
            "image_page": "testate_3_page_1.png"
        },
        {
            "id": "testat_3_page_2",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "Which statements about the waterfall model are correct?",
            "type": "multiple_choice",
            "options": [
                "(a) A key assumption is that feedback is possible to any preceding phase.",
                "(b) It explicitly takes into account the need for feedback.",
                "(c) The coupling between phases occurs primarily through the exchange of documents/artifacts.",
                "(d) It supports the parallel development of different phases."
            ],
            "correct_answer": ["(b)", "(c)"],
            "hint": "The waterfall model explicitly considers feedback (typically to the adjacent preceding phase) and couples phases through document exchange.",
            "image_page": "testate_3_page_2.png"
        },
        {
            "id": "testat_3_page_3",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "What do the axes in the classic V-model represent?",
            "type": "multiple_choice",
            "options": [
                "(a) The horizontal axis represents the level of abstraction.",
                "(b) The vertical axis shows the costs of the project.",
                "(c) The vertical axis represents abstraction or refinement.",
                "(d) The horizontal axis represents time or project progress."
            ],
            "correct_answer": ["(c)", "(d)"],
            "hint": "Vertical axis = abstraction/refinement level; horizontal axis = time/project progress.",
            "image_page": "testate_3_page_3.png"
        },
        {
            "id": "testat_3_page_4",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "What is the significance of the V-Modell XT in practice today?",
            "type": "multiple_choice",
            "options": [
                "(a) In the startup scene, it is preferred due to its speed.",
                "(b) In regulated industries such as medical technology, the principle of the V-Model XT remains essential.",
                "(c) It is fundamentally required for IT projects of the German federal administration.",
                "(d) \"XT\" stands for \"eXtreme Tailoring\" and allows for customization to specific needs."
            ],
            "correct_answer": ["(b)", "(c)", "(d)"],
            "hint": "V-Modell XT is mandatory for German federal administration IT projects, essential in regulated industries like medtech, and XT stands for eXtreme Tailoring.",
            "image_page": "testate_3_page_4.png"
        },
        {
            "id": "testat_3_page_5",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "What is the purpose of the \"Staging Area\" (Index) in systems like Git?",
            "type": "multiple_choice",
            "options": [
                "(a) It allows you to thoroughly review changes before committing (e.g., via Diff).",
                "(b) It allows precise control over which changes are included in the next commit.",
                "(c) It serves as a permanent archive for deleted files.",
                "(d) It is essential to perform a rebase."
            ],
            "correct_answer": ["(a)", "(b)"],
            "hint": "The staging area allows reviewing changes prior to committing and selecting specific modifications for the commit.",
            "image_page": "testate_3_page_5.png"
        },
        {
            "id": "testat_3_page_6",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "What are the essential differences between \"Merge\" and \"Rebase\" in version control?",
            "type": "multiple_choice",
            "options": [
                "(a) Rebasing is safer than merging because conflicts can never occur.",
                "(b) A rebase places your own commits at the end of another branch.",
                "(c) A merge results in a new \"merge commit\" that combines two branches.",
                "(d) A rebase creates a clean, linear history of commits without additional merge commits."
            ],
            "correct_answer": ["(b)", "(c)", "(d)"],
            "hint": "Merge creates a merge commit, whereas Rebase replays commits on top of another branch creating a clean linear history.",
            "image_page": "testate_3_page_6.png"
        },
        {
            "id": "testat_3_page_7",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "Which values are prioritized in the Agile Manifesto?",
            "type": "multiple_choice",
            "options": [
                "(a) Contract negotiations carry more weight than collaboration with the customer.",
                "(b) Working software is valued more than comprehensive documentation.",
                "(c) Processes and tools are valued more than individuals and interactions.",
                "(d) Responding to change is prioritized over following a plan."
            ],
            "correct_answer": ["(b)", "(d)"],
            "hint": "Agile Manifesto prioritizes working software over comprehensive documentation and responding to change over following a plan.",
            "image_page": "testate_3_page_7.png"
        },
        {
            "id": "testat_3_page_8",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "What is the difference between a Sprint Review and a Sprint Retrospective?",
            "type": "multiple_choice",
            "options": [
                "(a) In the Sprint Review, the Sprint results are evaluated.",
                "(b) The sprint retrospective is used to reflect on the process and identify improvements for the team.",
                "(c) In the sprint retrospective, a live demo of the software is primarily shown.",
                "(d) The Sprint Review takes place at the beginning of a sprint, the Sprint Retrospective at the end."
            ],
            "correct_answer": ["(a)", "(b)"],
            "hint": "Sprint Review evaluates sprint results/increment, while Sprint Retrospective reflects on team process and continuous improvements.",
            "image_page": "testate_3_page_8.png"
        },
        {
            "id": "testat_3_page_9",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "Which principles are part of the \"Engineering Practices\" of Extreme Programming (XP)?",
            "type": "multiple_choice",
            "options": [
                "(a) Big Up-front Design",
                "(b) Pair Programming",
                "(c) Continuous refactoring",
                "(d) Test Driven Development (TDD)"
            ],
            "correct_answer": ["(b)", "(c)", "(d)"],
            "hint": "XP Engineering Practices include Pair Programming, Continuous Refactoring, and Test Driven Development (TDD).",
            "image_page": "testate_3_page_9.png"
        },
        {
            "id": "testat_3_page_10",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "Which statements about the CI/CD pipeline and its components are correct?",
            "type": "multiple_choice",
            "options": [
                "(a) Continuous Integration (CI) alone can already guarantee the complete functional correctness of software.",
                "(b) Continuous Integration (CI) facilitates parallel development and helps to identify errors more quickly by merging code at an early stage.",
                "(c) Continuous Deployment (CD) involves the automated installation (deployment) of the runnable software version in the production environment.",
                "(d) Automated tests are an essential part of the pipeline to ensure the functionality and quality of a release."
            ],
            "correct_answer": ["(b)", "(c)", "(d)"],
            "hint": "CI enables parallel development and early defect detection, CD automates production deployments, and automated testing ensures release quality.",
            "image_page": "testate_3_page_10.png"
        },
        {
            "id": "testat_3_page_11",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "Exercise Sheet No. 10 - Task 10.1: Fundamentals and Definitions\na) Explain the term \"Adaptation\" in the context of software systems and explain the fundamental idea behind it. (3 points)",
            "type": "open",
            "options": None,
            "correct_answer": "• Adaptation is an approach for handling uncertainty in software systems.\n• The system collects new knowledge at runtime to:\n  - Resolve uncertainties\n  - Reflect upon itself, its context, and its goals\n  - Modify itself in order to achieve those goals\n  - Learn from past modifications\n• Adaptation enables systems to react autonomously to unforeseen situations without requiring human intervention or a complete re-implementation.",
            "hint": "Think about runtime knowledge, self-reflection, self-modification, and handling uncertainty without manual intervention.",
            "image_page": "testate_3_page_11.png"
        },
        {
            "id": "testat_3_page_12",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "Exercise Sheet No. 10 - Task 10.1: Fundamentals and Definitions\nb) Explain the essential difference between adaptation and evolution. Name at least two characteristic features for each. (2 points)",
            "type": "open",
            "options": None,
            "correct_answer": "Adaptation:\n• Short-term, instance-specific modification of the system\n• Addresses immediate, unforeseen problems\n• Does not affect future instances of the software and does not permanently change the system\n• Example: Temporarily adding cloud servers under high load\n\nEvolution:\n• Long-term modification of the software\n• Based on aggregated insights and adaptation patterns collected over time\n• Affects all future instances of the software\n• Example: Permanent code adaptation and redeployment via CI/CD pipeline",
            "hint": "Adaptation is short-term/instance-specific (e.g. autoscaling under load), whereas evolution is long-term/permanent for all future instances (e.g. code updates via CI/CD).",
            "image_page": "testate_3_page_12.png"
        },
        {
            "id": "testat_3_page_13",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "Exercise Sheet No. 10 - Task 10.1: Fundamentals and Definitions\nc) Explain the two perspectives on adaptation (external and internal perspective) and how they differ. (3 points)",
            "type": "open",
            "options": None,
            "correct_answer": "• External Perspective: An adaptive system is a system that can handle uncertainty in its environment, in itself, and in its goals autonomously (or with minimal human intervention). This perspective focuses on the observable behavior of the system from the outside.\n• Internal Perspective: An adaptive system consists of two distinct parts:\n  - System Logic: Interacts with the environment and handles the primary domain task of the system.\n  - Adaptation Logic: Interacts with System Logic, monitors execution quality, and adjusts system behavior.\n• Difference: The external perspective describes system behavior from a user's point of view, whereas the internal perspective describes architectural structure and separation of concerns within the system.",
            "hint": "External perspective = observable behavior from the outside; Internal perspective = architectural separation between System Logic and Adaptation Logic.",
            "image_page": "testate_3_page_13.png"
        },
        {
            "id": "testat_3_page_14",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "Exercise Sheet No. 10 - Task 10.1: Fundamentals and Definitions\nd) Name the four fundamental types of adaptation and briefly explain the purpose of each. (4 points)",
            "type": "open",
            "options": None,
            "correct_answer": "1. Self-optimization: The capability of a system to seek opportunities to optimize resource utilization while meeting required quality goals.\n2. Self-healing: The capability of a system to discover defects and recover from them to meet required quality goals, or gracefully degrade if full recovery is impossible.\n3. Self-protection: The capability of a system to defend against malicious attacks and anticipate potential disruptions to achieve required quality goals.\n4. Self-configuration: The capability of a system to automatically integrate new components or reconfigure itself without interrupting normal operations.",
            "hint": "The 4 Self-* properties: Self-optimization (resources), Self-healing (defects), Self-protection (attacks), and Self-configuration (seamless integration).",
            "image_page": "testate_3_page_14.png"
        },
        {
            "id": "testat_3_page_15",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "Exercise Sheet No. 10 - Task 10.2: MAPE-K Reference Model\na) Explain the MAPE-K reference model for adaptive systems. Describe the role of each of the five components. (5 points)",
            "type": "open",
            "options": None,
            "correct_answer": "The MAPE-K reference model is an architectural model for adaptive systems consisting of five components:\n• Monitor: Collects data from the managed element and execution context. Continuously monitors relevant system states and environmental parameters.\n• Analyze: Determines whether adaptation is necessary and evaluates available options. Assesses collected data and identifies deviations from target goals.\n• Plan: Plans mitigation actions to adapt the managed element when required. Formulates strategies to resolve identified issues.\n• Execute: Executes the plan and adjusts the managed element. Implements planned changes in the system.\n• Knowledge: Abstracts relevant aspects of the managed element, environment, and administrator goals. Provides a shared knowledge base for all other components.\n\nThe model achieves a clear separation of concerns within the adaptation logic.",
            "hint": "MAPE-K stands for Monitor (data collection), Analyze (evaluating need), Plan (action strategies), Execute (enacting changes), and Knowledge (shared repository).",
            "image_page": "testate_3_page_15.png"
        },
        {
            "id": "testat_3_page_16",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "Exercise Sheet No. 10 - Task 10.2: MAPE-K Reference Model\nb) Explain why a separation between \"System Logic\" (Managed System) and \"Adaptation Logic\" (Managing System) is sensible in adaptive systems. (4 points)",
            "type": "open",
            "options": None,
            "correct_answer": "• Separation of Concerns: Domain functionality is separated from adaptation concerns (quality and self-management), reducing overall system complexity and increasing maintainability.\n• Modularity: Each part can be developed, tested, and evolved independently.\n• Reusability: The adaptation logic can potentially be reused across different domain systems, while the system logic remains domain-specific.\n• Clear Allocation of Responsibilities: System Logic focuses on delivering core business functionality, while Adaptation Logic focuses on satisfying quality goals under changing conditions.",
            "hint": "Key reasons: Separation of concerns, modularity, reusability of adaptation mechanisms, and distinct responsibilities.",
            "image_page": "testate_3_page_16.png"
        },
        {
            "id": "testat_3_page_17",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "Exercise Sheet No. 10 - Task 10.3: Engineering Adaptive Systems\na) Name the four principles for developing adaptive systems presented in the lecture and briefly explain each (1–2 sentences). (4 points)",
            "type": "open",
            "options": None,
            "correct_answer": "1. Architecture-based Adaptation: The system is described using explicit architectural models that are used at runtime for adaptation decisions. This allows adaptations to be made in a structured and traceable manner.\n2. Adaptation with Runtime Models: The system maintains runtime models of itself and its quality aspects to support automated decision-making. These models form the knowledge base for adaptation logic.\n3. Control-based Adaptation: Adaptation is modeled as a feedback control loop where controllers (e.g. PID) continuously measure system states and adjust control variables toward target values. This brings established control-engineering techniques into software development.\n4. AI-based Adaptation: The system utilizes Machine Learning (specifically Reinforcement Learning) to autonomously learn optimal adaptation policies at runtime. This enables adaptation in highly dynamic environments that cannot be fully modeled in advance.",
            "hint": "The 4 principles: 1. Architecture-based Adaptation, 2. Adaptation mit Runtime Models, 3. Control-based Adaptation (feedback loops), 4. AI-based Adaptation (machine learning).",
            "image_page": "testate_3_page_17.png"
        },
        {
            "id": "testat_3_page_18",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": "Exercise Sheet No. 10 - Task 10.3: Engineering Adaptive Systems\nb) Explain the relationship between the lifecycle model of an adaptive system and a traditional DevOps model. (2 points)",
            "type": "open",
            "options": None,
            "correct_answer": "• Traditional DevOps Model:\n  - Clear separation between DEV (development) and OPS (operations)\n  - Changes require going through the full development cycle (code modification, CI/CD pipeline, deployment)\n  - System evolution occurs via permanent modification and redeployment\n• Adaptive System Lifecycle Model:\n  - Extends DevOps with an additional ADAPT phase\n  - The system can self-observe and self-modify at runtime\n  - Enables rapid, temporary adaptations without triggering a full development and deployment cycle\n  - Combines long-term evolution (via DevOps) with short-term runtime adaptation\n• An adaptive system integrates autonomous runtime self-adaptation capability into the classical development and operations lifecycle.",
            "hint": "DevOps uses the traditional DEV/OPS cycle for evolution. An adaptive system extends this by integrating an ADAPT loop for autonomous runtime self-observation and self-modification.",
            "image_page": "testate_3_page_18.png"
        }
    ]
    all_testates.extend(testat3_items)
        
    return all_testates

# ==================== PARSING SECTION 4: SLIDES ====================
def parse_slides():
    slides_summary_pdf = os.path.join(study_dir, "Slides/SE Kapiteln 1-10 (sehr kurz) en-US.pdf")
    print(f"\nParsing Slides Summary: {slides_summary_pdf}...")
    
    if not os.path.exists(slides_summary_pdf):
        print("Slides summary PDF not found.")
        return get_slides_fallback()
        
    try:
        doc = fitz.open(slides_summary_pdf)
    except Exception as e:
        print(f"Error opening slides PDF: {e}")
        return get_slides_fallback()
        
    all_definitions = []
    batch_size = 4
    total_pages = len(doc)
    
    for start_idx in range(1, total_pages, batch_size): # Start from page 1 to skip translation watermarks
        end_idx = min(start_idx + batch_size, total_pages)
        print(f"Processing slides batch: Pages {start_idx} to {end_idx-1}...")
        
        batch_text = ""
        for page_num in range(start_idx, end_idx):
            batch_text += f"\n--- PAGE {page_num} ---\n"
            batch_text += doc[page_num].get_text()
            
        prompt = f"""
        Analyze the following English summary text of Software Engineering lectures.
        
        Extract all key terms, concepts, and definitions and structure them into a JSON list.
        For each entry, provide:
        1. "id": e.g. "slide_definition_{start_idx}_{page_num}" (make sure they are unique!)
        2. "category": "Lecture Slides / Definitions"
        3. "chapter": The chapter name/number (e.g. "Chapter 1: Introduction to Software Engineering" or "Chapter 2: PTMW").
        4. "term": The keyword or term (e.g. "Verification", "Abstraction", "Waterfall model").
        5. "definition": The definition or explanation.
        6. "example": If an example is given in the text, extract it. Otherwise, null.
        7. "hint": A short question to ask the user, e.g. "How would you define Verification?" or "What are the goals of SE?".
        
        Text:
        {batch_text}
        
        Return a JSON array of objects. Make sure all strings are properly escaped and valid JSON.
        """
        
        data = call_gemini_json_http(prompt, "Extract key terms and definitions to JSON. Be robust and return clean JSON format.")
        if data and isinstance(data, list):
            all_definitions.extend(data)
            print(f"  Extracted {len(data)} definitions from page batch {start_idx}-{end_idx-1}.")
        else:
            print(f"  Failed or got no data for page batch {start_idx}-{end_idx-1}.")
            
    if all_definitions:
        print(f"Slides parsing completed. Extracted a total of {len(all_definitions)} definitions.")
        return all_definitions
    else:
        print("Failed to extract slide definitions via Gemini. Using fallback...")
        return get_slides_fallback()


# ==================== FALLBACK GENERATORS ====================
# These guarantee that we have high quality data even if the API Key is not set or fails.
def get_exam_fallback():
    return [
        {
            "id": "exam_1.1",
            "category": "Exam WS25-26",
            "question": "1.1 Which of the following statements about Software Engineering (SE) are correct according to the lecture? Note: Multiple answers can be correct (Multiple Choice).",
            "type": "multiple_choice",
            "options": [
                "(a) Costs in SE projects are almost exclusively determined by material and infrastructure costs.",
                "(b) A key goal of software engineering is to manage complexity in the construction of large systems.",
                "(c) In contrast to other engineering disciplines, cooperation between people plays a subordinate role in SE.",
                "(d) Software is an intangible asset, which is why requirements can often only be fully clarified through use or commissioning."
            ],
            "correct_answer": ["(b)", "(d)"],
            "student_answer": "(a), (b), (c), (d)",
            "points_earned": 0.0,
            "points_max": 4.0,
            "hint": "Software is intangible and development is human-centric. Infrastructure costs are low compared to labor, and complexity is a main challenge.",
            "page_num": 1
        },
        {
            "id": "exam_1.2a",
            "category": "Exam WS25-26",
            "question": "1.2 Abstraction is an essential skill in Software Engineering. a) Explain the principle of abstraction.",
            "type": "open",
            "options": None,
            "correct_answer": "Abstraction is the process of omitting unimportant details and emphasizing essential features. It helps in building simplified models of reality to reduce complexity.",
            "student_answer": "Abstraction is a principle that defines the concrete milestones and defines the software process roles.",
            "points_earned": 0.0,
            "points_max": 2.0,
            "hint": "Think about what abstraction does to details (e.g. maps vs real landscapes) to reduce complexity.",
            "page_num": 2
        },
        {
            "id": "exam_1.2b",
            "category": "Exam WS25-26",
            "question": "1.2 b) State two specific negative consequences that can occur in the development process if the principle of abstraction is neglected.",
            "type": "open",
            "options": None,
            "correct_answer": "1. Overwhelmed by details / high complexity which slows down the process.\n2. Deterioration of software quality and difficulty in modifying or extending the system.",
            "student_answer": "It will take more time to development if abstraction is neglected. It will cost more to redeploy the whole working software if abstraction is neglected.",
            "points_earned": 2.0,
            "points_max": 2.0,
            "hint": "Focus on complexity, speed, quality, and understanding.",
            "page_num": 2
        },
        {
            "id": "exam_1.3a",
            "category": "Exam WS25-26",
            "question": "1.3 a) State the applicable type of maintenance for the following scenario: The software must be adapted to a new statutory value-added tax regulation.",
            "type": "open",
            "options": None,
            "correct_answer": "Adaptive Maintenance",
            "student_answer": "Process Maintenance",
            "points_earned": 0.0,
            "points_max": 1.0,
            "hint": "This involves adapting to external changes (like legal or environment changes).",
            "page_num": 2
        },
        {
            "id": "exam_1.3b",
            "category": "Exam WS25-26",
            "question": "1.3 b) State the applicable type of maintenance for the following scenario: A memory leak leading to system crashes is fixed.",
            "type": "open",
            "options": None,
            "correct_answer": "Corrective Maintenance",
            "student_answer": "Corrective Maintenance",
            "points_earned": 1.0,
            "points_max": 1.0,
            "hint": "Fixing bugs and crashes.",
            "page_num": 2
        },
        {
            "id": "exam_1.4a",
            "category": "Exam WS25-26",
            "question": "1.4 a) Define the principle of modularity in the context of Software Engineering.",
            "type": "open",
            "options": None,
            "correct_answer": "Modularity means dividing a software system into smaller, self-contained, and independent parts called modules, each with a clear responsibility, to make the system easier to design, implement, and maintain.",
            "student_answer": "Modularity is about how each module (class, interface, function) as itself. Each module has independent role and responsiblity in codebase and each module is important.",
            "points_earned": 1.5,
            "points_max": 2.0,
            "hint": "Focus on dividing a system into well-defined, independent, and self-contained parts.",
            "page_num": 3
        },
        {
            "id": "exam_2.3a",
            "category": "Exam WS25-26",
            "question": "2.3 Given the following Java code fragment for a discount calculation:\nif (umsatz > 1000) {\n    if (istStammkunde) {\n        rabatt = 0.15;\n    } else {\n        rabatt = 0.10;\n    }\n} else {\n    rabatt = 0.0;\n}\na) How many branches exist in this Java code fragment in total?",
            "type": "open",
            "options": None,
            "correct_answer": "4 branches",
            "student_answer": "3",
            "points_earned": 0.0,
            "points_max": 2.0,
            "hint": "Count all possible paths generated by the condition checks: (1) umsatz <= 1000, (2) umsatz > 1000 & istStammkunde, (3) umsatz > 1000 & !istStammkunde. Total branches = 4.",
            "page_num": 6
        },
        {
            "id": "exam_3.3a",
            "category": "Exam WS25-26",
            "question": "3.3 a) Name the applicable phase in the MAPE-K model for the following activity: The adaptation logic calculates that two additional web server instances must be started.",
            "type": "open",
            "options": None,
            "correct_answer": "Plan",
            "student_answer": "Monitor",
            "points_earned": 0.0,
            "points_max": 1.0,
            "hint": "Calculating or formulating steps to achieve a goal belongs to the third phase of MAPE-K.",
            "page_num": 8
        }
    ]

def get_exercises_fallback():
    return [
        {
            "id": "exercise_1.1_a",
            "category": "Exercises",
            "sheet": "Exercise Sheet 1",
            "task_title": "Task 1.1: Fundamentals of Software Engineering",
            "question": "a) Name three important characteristics of software engineering.",
            "correct_answer": "1. Systematic development according to defined methods and processes.\n2. Use of tools to support the development process.\n3. Focus on quality, maintainability, and reusability of software.",
            "student_answer": "Systematic development according to defined methods and processes; Use of tools to support the development process; Focus on quality, maintainability, and reusability.",
            "hint": "Think about what makes engineering disciplined compared to simple coding.",
            "page_num": 1
        },
        {
            "id": "exercise_1.3_b",
            "category": "Exercises",
            "sheet": "Exercise Sheet 1",
            "task_title": "Task 1.3: Quality Characteristics",
            "question": "b) Explain the difference between verification and validation.",
            "correct_answer": "Verification checks if the product is built correctly according to specifications ('Are we building the product right?').\nValidation checks if we are building the correct product to meet user needs ('Are we building the right product?').",
            "student_answer": "Verification checks if implemented correctly. Validation checks if it meets customer requirements.",
            "hint": "Use the famous key questions: 'right product' vs 'product right'.",
            "page_num": 3
        }
    ]

def get_testat1_fallback():
    return [
        {
            "id": "testat_1_q1",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 1",
            "question": "According to the lecture, what are the main objectives of software engineering? (Select all that apply)",
            "type": "multiple_choice",
            "options": [
                "(a) To produce software with a focus on marketing and aesthetics.",
                "(b) To produce software at predictable costs.",
                "(c) To produce software within predictable timeframes.",
                "(d) To produce software with predictable quality."
            ],
            "correct_answer": ["(b)", "(c)", "(d)"],
            "hint": "Think about the magic triangle of project management (cost, time, quality).",
            "image_page": None
        },
        {
            "id": "testat_1_q3",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 1",
            "question": "What is meant by the software quality attribute 'robustness'?",
            "type": "multiple_choice",
            "options": [
                "(a) The ability of a program to execute complex math operations fast.",
                "(b) Tolerance towards unspecified operation or unspecified conditions.",
                "(c) The size of code modules in the architecture.",
                "(d) Reusability of classes across different microservices."
            ],
            "correct_answer": ["(b)"],
            "hint": "Remains functional even under non-standard inputs or errors.",
            "image_page": None
        }
    ]

def get_slides_fallback():
    return [
        {
            "id": "slide_definition_1",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 1: Introduction to Software Engineering",
            "term": "Software Engineering",
            "definition": "The systematic, disciplined, and quantifiable approach to developing, operating, and maintaining software.",
            "example": "Applying engineering principles (methods, tools, principles) to coding.",
            "hint": "What is the systematic and quantifiable approach to software?"
        },
        {
            "id": "slide_definition_2",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 1: Introduction to Software Engineering",
            "term": "Verification",
            "definition": "Checking whether the system has been developed correctly in accordance with the specification ('Are we building the product right?').",
            "example": "Unit tests checking if code complies with design specifications.",
            "hint": "Checking compliance with specifications."
        },
        {
            "id": "slide_definition_3",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 1: Introduction to Software Engineering",
            "term": "Validation",
            "definition": "Checking whether the system meets the customer's actual needs ('Are we building the right product?').",
            "example": "Beta testing with real users to get feedback.",
            "hint": "Checking if the software satisfies customer requirements."
        },
        {
            "id": "slide_definition_4",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 1: Introduction to Software Engineering",
            "term": "Abstraction",
            "definition": "Emphasizing essential features while omitting unimportant details to manage complexity.",
            "example": "A map showing roads but omitting individual houses.",
            "hint": "What is the process of omitting unimportant details to reduce complexity?"
        },
        {
            "id": "slide_definition_5",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 1: Introduction to Software Engineering",
            "term": "Modularization",
            "definition": "Dividing a software system into smaller, self-contained, and independent parts called modules.",
            "example": "Creating separate packages or classes for database handling and user interface.",
            "hint": "What is dividing a system into smaller, independent parts?"
        },
        {
            "id": "slide_definition_6",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 2: PTMW",
            "term": "Cohesion",
            "definition": "The measure of how strongly related and focused the responsibilities of a single module are. High cohesion is desirable.",
            "example": "A class that only handles mathematical matrix operations has high cohesion.",
            "hint": "What metric measures the focus or single responsibility of a module?"
        },
        {
            "id": "slide_definition_7",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 2: PTMW",
            "term": "Coupling",
            "definition": "The measure of the degree of interdependence between software modules. Low coupling is desirable.",
            "example": "Two classes that share many global variables have high coupling.",
            "hint": "What metric measures the degree of interdependence between modules?"
        },
        {
            "id": "slide_definition_8",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 4: Requirements Engineering",
            "term": "Functional Requirement",
            "definition": "A requirement that defines a function or service that the software system must perform.",
            "example": "The system must allow users to log in using their email and password.",
            "hint": "What kind of requirement describes what the system should do?"
        },
        {
            "id": "slide_definition_9",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 4: Requirements Engineering",
            "term": "Non-Functional Requirement",
            "definition": "A requirement that specifies criteria or constraints that can be used to judge the operation of a system, rather than specific behaviors.",
            "example": "The system must respond to user queries within 2 seconds.",
            "hint": "What kind of requirement specifies quality properties or constraints?"
        },
        {
            "id": "slide_definition_10",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 5: Software Architecture",
            "term": "Software Architecture",
            "definition": "The fundamental structure of a software system, including its components, their external properties, and the relationships between them.",
            "example": "Model-View-Controller (MVC) or Microservices architecture.",
            "hint": "How do you define the fundamental structural blueprint of a system?"
        },
        {
            "id": "slide_definition_11",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 6: Software Testing",
            "term": "Regression Testing",
            "definition": "Re-running previously passed tests after code changes to ensure that existing functionality has not been broken.",
            "example": "Running the automated test suite after refactoring a class.",
            "hint": "What tests ensure that new changes did not break existing features?"
        },
        {
            "id": "slide_definition_12",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 6: Software Testing",
            "term": "Unit Testing",
            "definition": "Testing individual components or modules of software in isolation to verify they work correctly.",
            "example": "Writing a JUnit test to check a single method in a Java class.",
            "hint": "What type of testing isolates and checks individual components?"
        },
        {
            "id": "slide_definition_13",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 7: Quality Assurance",
            "term": "Refactoring",
            "definition": "Modifying the internal structure of code to make it easier to understand and cheaper to modify, without changing its external behavior.",
            "example": "Extracting a long method into several smaller, well-named methods.",
            "hint": "What is improving code structure without changing its external behavior?"
        },
        {
            "id": "slide_definition_14",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 8: Traditional Software Processes",
            "term": "Waterfall Model",
            "definition": "A sequential development process where progress flows steadily downwards through phases like Requirements, Design, Implementation, Testing, Maintenance.",
            "example": "Standard construction-like project scheduling.",
            "hint": "What traditional process model follows strict, sequential phases?"
        },
        {
            "id": "slide_definition_15",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 9: Agile Software Processes",
            "term": "Scrum",
            "definition": "An agile framework for managing complex software projects iteratively, based on short cycles called Sprints, Daily Scrum meetings, and defined roles.",
            "example": "A team holding a daily 15-minute standup to coordinate tasks.",
            "hint": "What popular agile framework uses Sprints and Daily standups?"
        },
        {
            "id": "slide_definition_16",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 10: Adaptive Systems",
            "term": "Self-Adaptive System",
            "definition": "A system that can monitor itself and its environment and modify its own behavior or structure at runtime to adapt to changes.",
            "example": "A cloud server that automatically scales its instances based on current traffic.",
            "hint": "What systems adapt their behavior automatically at runtime?"
        },
        {
            "id": "slide_definition_17",
            "category": "Lecture Slides / Definitions",
            "chapter": "Chapter 10: Adaptive Systems",
            "term": "MAPE-K Loop",
            "definition": "A control loop model for self-adaptive systems: Monitor, Analyze, Plan, Execute, sharing a common Knowledge base.",
            "example": "An autonomic manager monitoring CPU usage, planning scale-up, and executing it.",
            "hint": "What reference loop describes the phases of a self-adaptive system?"
        }
    ]

def parse_mock_exam():
    print("\nParsing Mock Exam...")
    # Return fully translated, high-quality structured data
    return get_mock_exam_fallback()

def get_mock_exam_fallback():
    return [
        {
            "id": "mock_exam_q1",
            "category": "Mock Exam (Variant 2)",
            "question": "Question 1 (2 points) – Multiple Choice: According to the lecture, what are the main goals of Software Engineering?",
            "type": "multiple_choice",
            "options": [
                "(a) To produce software at predictable costs.",
                "(b) To produce software in a predictable timeframe.",
                "(c) To produce software of predictable quality.",
                "(d) Every requirement must be complete and unchangeable at the outset."
            ],
            "correct_answer": ["(a)", "(b)", "(c)"],
            "hint": "Consider the goals of engineering: predictability in cost, timeline, and quality. Software engineering handles change rather than requiring static requirements.",
            "page_num": 1
        },
        {
            "id": "mock_exam_q2",
            "category": "Mock Exam (Variant 2)",
            "question": "Question 2 (2 points) – Multiple Choice: Which statements about verification and validation are correct?",
            "type": "multiple_choice",
            "options": [
                "(a) Verification checks whether the software was developed correctly according to the specification.",
                "(b) Validation checks whether the correct software is being developed (customer requirements/needs).",
                "(c) Validation can only be done through code review.",
                "(d) Verification is identical to validation.",
                "(e) Verification takes place exclusively after the go-live."
            ],
            "correct_answer": ["(a)", "(b)"],
            "hint": "Remember the classic definitions: Verification is 'Are we building the product right?' and Validation is 'Are we building the right product?'",
            "page_num": 1
        },
        {
            "id": "mock_exam_q3",
            "category": "Mock Exam (Variant 2)",
            "question": "Question 3 (2 points) – Multiple Choice: Which statements about the quality property robustness are correct?",
            "type": "multiple_choice",
            "options": [
                "(a) Robustness is the tolerance to unspecified operation or non-standard use.",
                "(b) Robustness means that software must never crash – no matter what happens.",
                "(c) Robustness is the same as performance.",
                "(d) Robustness is only relevant for hardware, not for software.",
                "(e) Robustness is only achieved through more features."
            ],
            "correct_answer": ["(a)"],
            "hint": "Robustness is about handling out-of-boundary conditions gracefully, but it does not mean the system can never crash under any physical catastrophe.",
            "page_num": 1
        },
        {
            "id": "mock_exam_q4",
            "category": "Mock Exam (Variant 2)",
            "question": "Question 4 (2 points) – Multiple Choice: Which statements about the principle of information hiding (encapsulation) are correct?",
            "type": "multiple_choice",
            "options": [
                "(a) One goal is to ensure that each module keeps internal implementation details ('secrets') from others.",
                "(b) Internal representations can be changed without adjusting other modules – as long as the interface remains the same.",
                "(c) Access to information is controlled, e.g. via methods or interfaces.",
                "(d) Information hiding is only relevant during implementation, not during architecture/design.",
                "(e) Information hiding typically increases modifiability/maintainability because changes are made locally."
            ],
            "correct_answer": ["(a)", "(b)", "(c)", "(e)"],
            "hint": "Encapsulation hides secrets. This makes it easier to change things internally without affecting clients, which improves maintainability.",
            "page_num": 1
        },
        {
            "id": "mock_exam_q5",
            "category": "Mock Exam (Variant 2)",
            "question": "Question 5 (2 points) – Multiple Choice: Which statements about the concept of role in Software Engineering are correct?",
            "type": "multiple_choice",
            "options": [
                "(a) One person can take on multiple roles.",
                "(b) A role can be played by several people.",
                "(c) A role describes a set of related tasks and responsibilities.",
                "(d) In Scrum, there is always exactly 1 developer per team.",
                "(e) Roles are exclusively job descriptions from the Human Resources department."
            ],
            "correct_answer": ["(a)", "(b)", "(c)"],
            "hint": "A role is distinct from a concrete person. Multiple people can have the same role, and one person can fulfill multiple roles.",
            "page_num": 2
        },
        {
            "id": "mock_exam_q6",
            "category": "Mock Exam (Variant 2)",
            "question": "Question 6 (2 points) – Multiple Choice: Which statements characterize the magic triangle in project management?",
            "type": "multiple_choice",
            "options": [
                "(a) It consists of the dimensions of deadline (time), quality, and cost.",
                "(b) The dimensions are interdependent (trade-offs).",
                "(c) The project manager must make an appropriate balance between the dimensions.",
                "(d) It describes the three Scrum roles.",
                "(e) This only applies to agile projects, not traditional ones."
            ],
            "correct_answer": ["(a)", "(b)", "(c)"],
            "hint": "The project management triangle represents constraints: time, cost, and quality. Changing one impacts the others.",
            "page_num": 2
        },
        {
            "id": "mock_exam_q7",
            "category": "Mock Exam (Variant 2)",
            "question": "Question 7 (2 points) – Multiple Choice: Which statements distinguish between constructive vs. analytical quality assurance (QA)?",
            "type": "multiple_choice",
            "options": [
                "(a) Constructive quality assurance aims to prevent errors from the outset.",
                "(b) Analytical QA aims to find existing errors (e.g., tests, reviews).",
                "(c) Analytical QA always means automated testing.",
                "(d) Constructive quality assurance only takes place at the end of the project.",
                "(e) Constructive and analytical quality assurance are identical."
            ],
            "correct_answer": ["(a)", "(b)"],
            "hint": "Constructive QA is about building quality in (preventing bugs, e.g. guidelines, patterns). Analytical QA is about checking for bugs (finding them, e.g. tests, reviews).",
            "page_num": 2
        },
        {
            "id": "mock_exam_q8",
            "category": "Mock Exam (Variant 2)",
            "question": "Question 8 (2 points) – Multiple Choice: Which statements about risk analysis / risk management in software projects are correct?",
            "type": "multiple_choice",
            "options": [
                "(a) New risks can emerge at any time.",
                "(b) Planned risk management measures might not be effective.",
                "(c) Additional information gathered during project implementation leads to new insights.",
                "(d) Risk analysis is always incremental: at the beginning, one typically only considers the high risks.",
                "(e) Once a project has started, risks may no longer be changed."
            ],
            "correct_answer": ["(a)", "(b)", "(c)", "(d)"],
            "hint": "Risk management is continuous. Risks can change, new risks emerge, and plans can fail, which is why we do incremental analysis.",
            "page_num": 2
        },
        {
            "id": "mock_exam_q9",
            "category": "Mock Exam (Variant 2)",
            "question": "Question 9 (2 points) – Multiple Choice: Which statements about architecture/design and general principles in SE are correct?",
            "type": "multiple_choice",
            "options": [
                "(a) Architecture has a higher degree of abstraction than design.",
                "(b) A fundamental concept for architecture and design is structuring (separation of concerns).",
                "(c) Architecture and design should be such that changes can be accommodated (Design for Change).",
                "(d) The architecture is strict, but the design is formal.",
                "(e) Information hiding plays no role in architecture and design."
            ],
            "correct_answer": ["(a)", "(b)", "(c)"],
            "hint": "Architecture is high-level design. Separation of concerns and designing for change are key principles.",
            "page_num": 3
        },
        {
            "id": "mock_exam_q10",
            "category": "Mock Exam (Variant 2)",
            "question": "Question 10 (2 points) – Multiple Choice: Which statements are possible disadvantages of a service-oriented architecture (SOA)?",
            "type": "multiple_choice",
            "options": [
                "(a) Communication overhead and latency due to communication via standard protocols.",
                "(b) Debugging becomes more complex because a distributed system with multiple services is created.",
                "(c) If communication with the service provider fails (or if they are offline), this can lead to errors.",
                "(d) Handling different service versions causes considerable effort (additional source of change).",
                "(e) SOA forces all services to be implemented in the same programming language."
            ],
            "correct_answer": ["(a)", "(b)", "(c)", "(d)"],
            "hint": "Distributed systems introduce latency, complex debugging, network dependency, and versioning overhead, but allow heterogeneous languages.",
            "page_num": 3
        },
        {
            "id": "mock_exam_task1",
            "category": "Mock Exam (Variant 2)",
            "question": "Task 1 (3 points): Briefly explain the difference between a life cycle model, a software process model, and a concrete software process (provide 1 sentence each + a mini-example).",
            "type": "open",
            "correct_answer": "1. Life Cycle Model: Describes the chronological phases of software from initial development to operation and decommissioning (e.g. ISO/IEC 12207).\n2. Software Process Model: An abstract representation of a development methodology showing roles, activities, and artifacts (e.g. Scrum or Waterfall).\n3. Concrete Software Process: The project-specific execution of a process model, detailing concrete tools, persons, and schedules (e.g. 'Project X Sprint 3 starting on Monday using Jira').",
            "hint": "Think from high-level abstract lifecycle phases, to development framework models, to execution on a specific project.",
            "page_num": 4
        },
        {
            "id": "mock_exam_task2",
            "category": "Mock Exam (Variant 2)",
            "question": "Task 2 (3 points): An update fixes a crash that occurs when a specific button is clicked. What type of maintenance is this? Briefly explain.",
            "type": "open",
            "correct_answer": "Corrective Maintenance. Corrective maintenance is performed to fix defects or bugs (like system crashes) discovered after the software has been deployed to restore it to correct operation.",
            "hint": "Think about the four types of maintenance (Corrective, Adaptive, Perfective, Preventive) and which one fixes errors.",
            "page_num": 4
        },
        {
            "id": "mock_exam_task3",
            "category": "Mock Exam (Variant 2)",
            "question": "Task 3 (3 points): Name three consequences of a lack of abstraction in software engineering.",
            "type": "open",
            "correct_answer": "1. High complexity and cognitive overload, making the system difficult to understand.\n2. High coupling and difficulty in modifying or extending the system (changes ripple through code).\n3. Harder to test and lower reusability of components.",
            "hint": "What happens when developers are overwhelmed by implementation details? Think about complexity, maintainability, and testing.",
            "page_num": 4
        },
        {
            "id": "mock_exam_task4",
            "category": "Mock Exam (Variant 2)",
            "question": "Task 4 (3 points): What is the purpose of the context boundary? Also, state which principle it implements.",
            "type": "open",
            "correct_answer": "The purpose of a context boundary is to separate the system under development from its environment, clearly defining what is inside the system and what is outside (irrelevant or external). It implements the principle of Separation of Concerns.",
            "hint": "What does a boundary do in requirements engineering? Which core SE principle separates different aspects of a system?",
            "page_num": 4
        },
        {
            "id": "mock_exam_task5",
            "category": "Mock Exam (Variant 2)",
            "question": "Task 5 (3 points): Name three advantages of model-based representation of use-case scenarios.",
            "type": "open",
            "correct_answer": "1. Systematic derivation of test cases.\n2. Better control of test coverage based on execution paths.\n3. Clearer representation of the main success scenario and alternative/exception flows, revealing missing requirements.",
            "hint": "How do models (like activity diagrams) help testers and designers compared to plain text use cases?",
            "page_num": 5
        },
        {
            "id": "mock_exam_task6",
            "category": "Mock Exam (Variant 2)",
            "question": "Task 6 (3 points): Explain the difference between adaptation and evolution (state 2 characteristics each).",
            "type": "open",
            "correct_answer": "1. Adaptation: Short-term, instance-specific adjustment to runtime conditions (e.g. self-scaling or self-healing) without changing the core codebase permanently.\n2. Evolution: Long-term modification of the software's codebase/architecture affecting all future instances, typically requiring recompilation and redeployment.",
            "hint": "Contrast runtime self-adjustment (adaptation) with development-time software changes (evolution).",
            "page_num": 5
        },
        {
            "id": "mock_exam_task7",
            "category": "Mock Exam (Variant 2)",
            "question": "Task 7 (2 points): What three roles does Scrum define? (list only)",
            "type": "open",
            "correct_answer": "1. Scrum Master\n2. Product Owner\n3. Developers (Development Team)",
            "hint": "Scrum has exactly three official roles. Who facilitates, who owns the requirements, and who builds the product?",
            "page_num": 5
        },
        {
            "id": "mock_exam_app1",
            "category": "Mock Exam (Variant 2)",
            "question": "Application Task 1 (4 points): Classify requirements. Classify each of the following statements as F (functional requirement), Q (quality requirement/NFR) or P (boundary condition/constraint):\n1. Users must be able to reset passwords.\n2. The response time must be less than 200 ms.\n3. The application must be implemented in Java 21.\n4. The system must be able to export invoices as PDFs.",
            "type": "open",
            "correct_answer": "1 = F (Functional Requirement)\n2 = Q (Quality Requirement/NFR)\n3 = P (Constraint/Boundary Condition)\n4 = F (Functional Requirement)",
            "hint": "Functional requirements describe what the system does. Quality requirements describe how well it does it. Constraints limit development choices (like technology).",
            "page_num": 6
        },
        {
            "id": "mock_exam_app2",
            "category": "Mock Exam (Variant 2)",
            "question": "Application Task 2 (4 points): Risk Analysis (Quantitative): For risks A–C, the probability of occurrence P and the severity of damage C are rated as follows (1 = low, 2 = medium, 3 = high):\n- Risk A: P=3, C=2\n- Risk B: P=2, C=3\n- Risk C: P=1, C=1\nCalculate R = P * C, prioritize the risks (in descending order), and identify if any risk is negligible.",
            "type": "open",
            "correct_answer": "1. Calculations: R_A = 3 * 2 = 6, R_B = 2 * 3 = 6, R_C = 1 * 1 = 1.\n2. Prioritization: Risk A and Risk B have equal priority (Score: 6), followed by Risk C (Score: 1).\n3. Negligible: Risk C (Score: 1) is typically negligible.",
            "hint": "Risk value R is probability times severity. Sort them. A very low score (like 1) is negligible.",
            "page_num": 6
        },
        {
            "id": "mock_exam_app3",
            "category": "Mock Exam (Variant 2)",
            "question": "Application Task 3 (4 points): Black-box test (equivalence classes): Given the specification: parseInt(value, mult) with:\n- value is an uppercase letter 'A'..'Z'; result = alphabet position (A=1..Z=26)\n- mult must be positive and a maximum of 50, otherwise error.\na) Define the valid and invalid equivalence classes for 'value' and 'mult'.\nb) Specify a minimum set of test cases (representatives), where each test case covers exactly one invalid class.",
            "type": "open",
            "correct_answer": "a) Equivalence Classes:\n- value: Valid: {'A'..'Z'}, Invalid: {any non-uppercase letter, e.g. 'a', '1', '@'}\n- mult: Valid: {1..50}, Invalid: {<=0} and {>50}\n\nb) Minimum Test Cases:\n1. (A, 1) -> Valid test case.\n2. (a, 1) -> Invalid value (covers invalid class for value).\n3. (A, 0) -> Invalid mult <= 0 (covers invalid class mult <= 0).\n4. (A, 51) -> Invalid mult > 50 (covers invalid class mult > 50).",
            "hint": "Partition inputs into valid/invalid ranges. Design tests that cover each invalid partition one at a time.",
            "page_num": 6
        },
        {
            "id": "mock_exam_app4",
            "category": "Mock Exam (Variant 2)",
            "question": "Application Task 4 (4 points): Limit Value Analysis: Derive suitable test values at the limits for 'mult' from the specification (mult must be positive and a maximum of 50). Provide the tested limit values with a brief explanation.",
            "type": "open",
            "correct_answer": "Suitable limit values are:\n- Lower boundary (around 1):\n  * 0: Invalid (just below limit)\n  * 1: Valid (on the limit)\n  * 2: Valid (just above limit)\n- Upper boundary (around 50):\n  * 49: Valid (just below limit)\n  * 50: Valid (on the limit)\n  * 51: Invalid (just above limit)",
            "hint": "Limit value analysis tests values directly on, just below, and just above the boundaries (1 and 50).",
            "page_num": 7
        },
        {
            "id": "mock_exam_app5",
            "category": "Mock Exam (Variant 2)",
            "question": "Application Task 5 (4 points): Whitebox – Branch Coverage: Consider the following code fragment:\n```java\nint f(int x, int y) {\n    int r = 0;\n    if (x > 0) {\n        if (y == 0 || x > 5) {\n            r = r + 10;\n        }\n        r = r + 1;\n    } else {\n        r = r - 1;\n    }\n    return r;\n}\n```\nSpecify the branches to be reached (true/false per if-statement) and provide concrete test inputs (x, y) that together achieve 100% branch coverage.",
            "type": "open",
            "correct_answer": "Branches to cover:\n1. Outer if (x > 0): True and False.\n2. Inner if (y == 0 || x > 5): True and False.\n\nMinimum test suite for 100% branch coverage:\n- Test case 1: (x=1, y=0) -> x > 0 is True, y == 0 || x > 5 is True. Covers Outer If True, Inner If True.\n- Test case 2: (x=1, y=1) -> x > 0 is True, y == 0 || x > 5 is False. Covers Outer If True, Inner If False.\n- Test case 3: (x=-1, y=0) -> x > 0 is False. Covers Outer If False.",
            "hint": "Identify all conditional branches. Find test cases that execute the outer if true, outer if false, inner if true, and inner if false.",
            "page_num": 7
        }
    ]

def main():
    print("Building unified study database JSON...")
    
    exam_data = parse_exam()
    exercise_data = parse_exercises()
    testate_data = parse_testates()
    slide_data = parse_slides()
    mock_exam_data = parse_mock_exam()
    
    db = {
        "exam": exam_data,
        "exercises": exercise_data,
        "testates": testate_data,
        "slides": slide_data,
        "mock_exam": mock_exam_data
    }
    
    output_path = os.path.join(output_dir, "study_data.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
        
    print(f"\nUnified database successfully written to {output_path}!")
    print(f"Total Exam Questions: {len(exam_data)}")
    print(f"Total Exercise Tasks: {len(exercise_data)}")
    print(f"Total Testate Questions: {len(testate_data)}")
    print(f"Total Slide Definitions: {len(slide_data)}")
    print(f"Total Mock Exam Questions: {len(mock_exam_data)}")

if __name__ == "__main__":
    main()
