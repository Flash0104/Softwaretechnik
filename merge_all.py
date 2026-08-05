import os
import re
import json
import fitz

app_dir = "/Users/canbekiroglu/Softwaretechnik"
data_dir = os.path.join(app_dir, "static/data")
study_materials_dir = "/Users/canbekiroglu/Downloads/SE_StudyMaterials/Can_s contribution for SWT"



def merge():
    study_data_path = os.path.join(data_dir, "study_data.json")
    ex47_path = os.path.join(data_dir, "exercises_4_7.json")
    
    if not os.path.exists(study_data_path):
        print("study_data.json not found.")
        return
        
    with open(study_data_path, "r", encoding="utf-8") as f:
        db = json.load(f)
        
    # 1. Merge Exercises 4-7
    if os.path.exists(ex47_path):
        with open(ex47_path, "r", encoding="utf-8") as f:
            ex47_data = json.load(f)
        
        # Add to exercises
        current_ids = [q['id'] for q in db.get("exercises", [])]
        added_count = 0
        for item in ex47_data:
            if item['id'] not in current_ids:
                db["exercises"].append(item)
                added_count += 1
        print(f"Added {added_count} exercises from sheet 4-7.")
    else:
        print("exercises_4_7.json not found, skipping sheet 4-7 merge.")
        

    
    # Save back
    with open(study_data_path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
        
    print("\nMerge complete!")
    print(f"Total Exam Questions: {len(db.get('exam', []))}")
    print(f"Total Exercise Tasks: {len(db.get('exercises', []))}")
    print(f"Total Testate Questions: {len(db.get('testates', []))}")
    print(f"Total Slide Definitions: {len(db.get('slides', []))}")
    print(f"Total Mock Exam Questions: {len(db.get('mock_exam', []))}")

if __name__ == "__main__":
    merge()
