#!/usr/bin/env python3
"""
migrate_to_firestore.py
=======================
One-time script to upload all questions from study_data.json to Firestore.

Usage:
    1. pip install firebase-admin
    2. Download your Firebase service account key:
       Firebase Console → Project Settings → Service accounts → Generate new private key
       Save it as: serviceAccountKey.json  (in this project root)
    3. Run: python migrate_to_firestore.py

This is safe to re-run — it uses set() which overwrites existing docs.
"""

import json
import os
import sys

# ------------------------------------------------------------------
# Check for firebase-admin
# ------------------------------------------------------------------
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    print("Error: firebase-admin not installed.")
    print("Run: pip install firebase-admin")
    sys.exit(1)

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")
DATA_FILE = os.path.join(os.path.dirname(__file__), "static/data/study_data.json")

# ------------------------------------------------------------------
# Validate files exist
# ------------------------------------------------------------------
if not os.path.exists(SERVICE_ACCOUNT_FILE):
    print(f"\nError: Service account key not found at: {SERVICE_ACCOUNT_FILE}")
    print("\nTo get it:")
    print("  1. Go to console.firebase.google.com")
    print("  2. Project Settings → Service accounts")
    print("  3. Click 'Generate new private key'")
    print("  4. Save the downloaded JSON as 'serviceAccountKey.json' in this folder")
    sys.exit(1)

if not os.path.exists(DATA_FILE):
    print(f"Error: study_data.json not found at: {DATA_FILE}")
    sys.exit(1)

# ------------------------------------------------------------------
# Initialize Firebase Admin SDK
# ------------------------------------------------------------------
print("Initializing Firebase Admin SDK...")
cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
firebase_admin.initialize_app(cred)
db = firestore.client()
print("Connected to Firestore.")

# ------------------------------------------------------------------
# Load local data
# ------------------------------------------------------------------
print(f"\nLoading questions from {DATA_FILE}...")
with open(DATA_FILE, "r", encoding="utf-8") as f:
    study_data = json.load(f)

# ------------------------------------------------------------------
# Upload to Firestore
# ------------------------------------------------------------------
CATEGORIES = ["exam", "exercises", "testates", "slides", "mock_exam"]
total_uploaded = 0

for category in CATEGORIES:
    questions = study_data.get(category, [])
    if not questions:
        print(f"  [{category}] — no questions found, skipping.")
        continue

    print(f"\n  Uploading [{category}] — {len(questions)} questions...")
    batch = db.batch()
    batch_count = 0

    for i, question in enumerate(questions):
        # Use the question's own ID if it has one, otherwise generate one
        q_id = str(question.get("id", f"{category}_{i+1}"))

        # Sanitize: ensure the document has an 'id' field consistent with its Firestore key
        question["id"] = q_id

        # Firestore path: questions/{category}/items/{questionId}
        doc_ref = (
            db.collection("questions")
              .document(category)
              .collection("items")
              .document(q_id)
        )
        batch.set(doc_ref, question)
        batch_count += 1
        total_uploaded += 1

        # Firestore batches are limited to 500 writes — commit and start fresh
        if batch_count >= 499:
            batch.commit()
            print(f"    Committed batch of {batch_count} docs...")
            batch = db.batch()
            batch_count = 0

    # Commit remaining docs in the last batch
    if batch_count > 0:
        batch.commit()
        print(f"    Committed final batch of {batch_count} docs.")

# ------------------------------------------------------------------
# Done
# ------------------------------------------------------------------
print(f"\n✅ Migration complete! {total_uploaded} questions uploaded to Firestore.")
print("\nNext steps:")
print("  1. Open Firebase Console → Firestore → verify the 'questions' collection exists")
print("  2. Make sure your Firestore Security Rules are published (see FIREBASE_SETUP.md)")
print("  3. Redeploy to Vercel: git add . && git commit -m 'Add Firebase auth + Firestore' && git push")
