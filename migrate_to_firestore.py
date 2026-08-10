#!/usr/bin/env python3
"""
migrate_to_firestore.py
=======================
One-time script to upload all questions from study_data.json to Firestore.
Uses the Firestore REST API + Firebase Auth REST API — NO service account key needed.

Usage:
    source venv/bin/activate
    python migrate_to_firestore.py

You will be prompted for your Google account email and password
(the account that owns this Firebase project).
"""

import json
import os
import sys
import getpass

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)

# ------------------------------------------------------------------
# Your Firebase project config (from firebase-config.js)
# ------------------------------------------------------------------
API_KEY    = "AIzaSyDnFSepVtBHHzbTOnyoqtsSid-yZznGj0g"
PROJECT_ID = "softwaretechnik-hub"

DATA_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "static/data/study_data.json")
CATEGORIES = ["exam", "exercises", "testates", "slides", "mock_exam"]

# Firestore REST base URL
FS_BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

# ------------------------------------------------------------------
# Step 1: Sign in with email/password to get an ID token
# ------------------------------------------------------------------
def sign_in(email: str, password: str) -> str:
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
    resp = requests.post(url, json={
        "email": email,
        "password": password,
        "returnSecureToken": True
    }, timeout=15)
    if resp.status_code != 200:
        err = resp.json().get("error", {}).get("message", resp.text)
        print(f"\n❌ Sign-in failed: {err}")
        print("\nTip: If you use Google Sign-In (no password), you need to set a password first:")
FS_BASE    = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

# ------------------------------------------------------------------
# Convert Python → Firestore REST field values
# ------------------------------------------------------------------
def to_fs(val):
    if val is None:           return {"nullValue": None}
    if isinstance(val, bool): return {"booleanValue": val}
    if isinstance(val, int):  return {"integerValue": str(val)}
    if isinstance(val, float):return {"doubleValue": val}
    if isinstance(val, str):  return {"stringValue": val}
    if isinstance(val, list): return {"arrayValue": {"values": [to_fs(v) for v in val]}}
    if isinstance(val, dict): return {"mapValue": {"fields": {k: to_fs(v) for k, v in val.items()}}}
    return {"stringValue": str(val)}

def to_doc(data): return {"fields": {k: to_fs(v) for k, v in data.items()}}

# ------------------------------------------------------------------
# Write one document (unauthenticated PATCH = upsert)
# ------------------------------------------------------------------
def write_doc(path: str, data: dict, retries=3):
    url = f"{FS_BASE}/{path}"
    for attempt in range(retries):
        try:
            r = requests.patch(url, json=to_doc(data), timeout=20)
            if r.status_code in (200, 201):
                return True
            if r.status_code == 403:
                print("\n\n❌ PERMISSION DENIED (403)")
                print("Firestore rules are blocking unauthenticated writes.")
                print("Please set the temporary open rules first (see instructions above).")
                sys.exit(1)
            if r.status_code >= 500 and attempt < retries - 1:
                time.sleep(1)
                continue
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:150]}")
        except requests.Timeout:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                raise
    return False

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
if not os.path.exists(DATA_FILE):
    print(f"❌ Data file not found: {DATA_FILE}")
    sys.exit(1)

print("=" * 60)
print("  SWT Study Hub — Firestore Migration")
print("=" * 60)
print(f"\n⚠️  Make sure Firestore rules are set to OPEN before continuing!")
print("   (Firebase Console → Firestore → Rules → allow read, write: if true)")
input("\nPress ENTER when rules are open, or Ctrl+C to cancel...\n")

with open(DATA_FILE, "r", encoding="utf-8") as f:
    study_data = json.load(f)

total = 0
errors = 0

for category in CATEGORIES:
    questions = study_data.get(category, [])
    if not questions:
        print(f"[{category}] — empty, skipping.")
        continue

    print(f"\n[{category}] — {len(questions)} questions", end="", flush=True)
    for i, q in enumerate(questions):
        q_id = str(q.get("id", f"{category}_{i+1}"))
        q["id"] = q_id
        try:
            write_doc(f"questions/{category}/items/{q_id}", q)
            total += 1
            print(".", end="", flush=True)
        except Exception as e:
            print(f"\n  ⚠️  [{q_id}] {e}")
            errors += 1

print(f"\n\n{'=' * 60}")
print(f"✅ {total} questions uploaded, {errors} errors.")
print(f"\n🔒 NOW RESTORE YOUR FIRESTORE RULES to the secure version!")
print("   (Firebase Console → Firestore → Rules → paste below → Publish)")
print("""
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /questions/{category}/items/{questionId} {
      allow read: if request.auth != null;
      allow write: if false;
    }
    match /users/{uid}/data/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
  }
}
""")
print(f"🚀 Then visit: https://softwaretechnik-hub.vercel.app")
