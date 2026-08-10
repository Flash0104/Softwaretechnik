import os
import json
import requests
import re
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

if os.environ.get("VERCEL"):
    app_dir = os.getcwd()
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
api_key = None
env_path = os.path.join(app_dir, ".env")
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()
                if key in ["GEMINI_API", "GEMINI_API_KEY"]:
                    api_key = val
                    if (api_key.startswith('"') and api_key.endswith('"')) or (api_key.startswith("'") and api_key.endswith("'")):
                        api_key = api_key[1:-1]
                    break

if not api_key:
    api_key = os.environ.get("GEMINI_API") or os.environ.get("GEMINI_API_KEY")

# Unified data file path
DATA_FILE = os.path.join(app_dir, "static/data/study_data.json")


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading study data: {e}")
    return {"exam": [], "exercises": [], "testates": [], "slides": [], "mock_exam": []}

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/data')
def data_view():
    return render_template("data.html")


@app.route('/api/questions')
def get_questions():
    data = load_data()
    return jsonify(data)

@app.route('/api/check-answer', methods=['POST'])
def check_answer():
    req_data = request.json or {}
    q_id = req_data.get("id")
    category = req_data.get("category")
    user_answer = req_data.get("user_answer", "").strip()
    
    # Load questions to find match
    db = load_data()
    
    # Categorize correctly
    category_key = None
    if "mock" in category.lower():
        category_key = "mock_exam"
    elif "exam" in category.lower():
        category_key = "exam"
    elif "exercise" in category.lower():
        category_key = "exercises"
    elif "testate" in category.lower() or "quiz" in category.lower():
        category_key = "testates"
    elif "slide" in category.lower() or "definition" in category.lower():
        category_key = "slides"
        
    question_obj = None
    if category_key and category_key in db:
        for q in db[category_key]:
            if q.get("id") == q_id:
                question_obj = q
                break
                
    if not question_obj:
        # Fallback search across all database categories by question ID
        for cat in db:
            for q in db[cat]:
                if q.get("id") == q_id:
                    question_obj = q
                    category_key = cat
                    break
            if question_obj:
                break
                
    if not question_obj:
        return jsonify({"error": "Question not found"}), 404
        
    correct_ans = question_obj.get("correct_answer") or question_obj.get("definition")
    q_text = question_obj.get("question") or question_obj.get("term")
    
    # Check if Multiple Choice or Open
    is_mc = question_obj.get("type") == "multiple_choice" or isinstance(correct_ans, list)
    
    if is_mc:
        # MC matching
        # Convert user_answer (can be list or comma-separated options) to comparison list
        user_choices = []
        if isinstance(user_answer, list):
            user_choices = [c.strip().lower() for c in user_answer]
        else:
            # Parse stuff like "(a), (b)" or "a, b"
            matches = re.findall(r"\(([a-zA-Z0-9])\)|([a-zA-Z0-9])", user_answer)
            user_choices = [f"({m[0] or m[1]})".lower() for m in matches]
            
        correct_choices = []
        if isinstance(correct_ans, list):
            correct_choices = [c.strip().lower() for c in correct_ans]
        else:
            matches = re.findall(r"\(([a-zA-Z0-9])\)|([a-zA-Z0-9])", str(correct_ans))
            correct_choices = [f"({m[0] or m[1]})".lower() for m in matches]
            
        # Clean user input checks
        is_correct = set(user_choices) == set(correct_choices)
        score = 100 if is_correct else 0
        feedback = "Correct! Well done." if is_correct else f"Incorrect. The correct choice is: {', '.join(correct_ans) if isinstance(correct_ans, list) else correct_ans}"
        
        return jsonify({
            "score": score,
            "feedback": feedback,
            "correct_answer": correct_ans,
            "is_mc": True
        })
        
    # Free-text evaluation
    # If no Gemini Key, fall back to self-assessment
    if not api_key:
        return jsonify({
            "fallback": True,
            "correct_answer": correct_ans,
            "feedback": "Self-assessment mode activated. Compare your answer below."
        })
        
    # Call Gemini to check free-text answer
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        prompt = f"""
        You are grading a student's answer in a Software Engineering exam/quiz.
        
        Question: {q_text}
        Reference Solution: {correct_ans}
        Student's Answer: {user_answer}
        
        Evaluate the student's answer by comparing it to the reference solution.
        Be fair but rigorous. Software engineering concepts must be accurate.
        If the answer is partially correct, assign partial marks.
        
        Provide your grading in a JSON object with:
        1. "score": An integer from 0 to 100 representing how correct/complete the answer is.
        2. "feedback": A brief explanation of why this score was given, and how they can improve (in English).
        
        Respond with ONLY the raw JSON object.
        """
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        
        res = requests.post(url, json=payload, headers=headers, timeout=20)
        if res.status_code == 200:
            res_json = res.json()
            text_res = res_json['candidates'][0]['content']['parts'][0]['text']
            grading = json.loads(text_res)
            return jsonify({
                "score": grading.get("score", 0),
                "feedback": grading.get("feedback", "No feedback provided."),
                "correct_answer": correct_ans,
                "is_mc": False
            })
        else:
            print(f"Gemini API check-answer call failed: {res.text}")
            return jsonify({
                "fallback": True,
                "correct_answer": correct_ans,
                "feedback": "Failed to call AI grading. Falling back to self-assessment."
            })
    except Exception as e:
        print(f"Error during AI check-answer: {e}")
        return jsonify({
            "fallback": True,
            "correct_answer": correct_ans,
            "feedback": f"Error calling AI grading: {e}. Falling back to self-assessment."
        })


@app.route('/api/debug-files')
def debug_files():
    files_list = []
    for root, dirs, files in os.walk('.'):
        # Exclude node_modules or large hidden folders to prevent output bloat
        if 'venv' in root or '.git' in root or '.vercel' in root:
            continue
        for file in files:
            files_list.append(os.path.join(root, file))
    return jsonify({
        "cwd": os.getcwd(),
        "app_dir": app_dir,
        "__file__": __file__,
        "files": files_list
    })


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5001)
