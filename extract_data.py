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
            
    # Add Mock / Reference placeholders for Testat 2 and Testat 3 scanned pages
    # Since these are scanned, we display their page images in the UI!
    # Let's add them to the JSON database so the user can select them, view the image page, and self-grade.
    for i in range(1, 6): # Testat 2 has 5 pages
        all_testates.append({
            "id": f"testat_2_page_{i}",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 2 (Scanned Sheet)",
            "question": f"Review and solve the questions on Page {i} of Testat 2.",
            "type": "image_only",
            "options": None,
            "correct_answer": f"Check page {i} of the sheet for correct answers / solutions.",
            "hint": "Analyze the handwritten or marked corrections on the page.",
            "image_page": f"testate_2_page_{i}.png"
        })
        
    for i in range(1, 19): # Testat 3 has 18 pages
        all_testates.append({
            "id": f"testat_3_page_{i}",
            "category": "Testates / Quizzes",
            "quiz_name": "Testat 3 & Ex 10 (Scanned Sheet)",
            "question": f"Review and solve the questions on Page {i} of Testat 3.",
            "type": "image_only",
            "options": None,
            "correct_answer": f"Check page {i} of the sheet for correct answers / solutions.",
            "hint": "Read the scanned solution sheet notes.",
            "image_page": f"testate_3_page_{i}.png"
        })
        
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
