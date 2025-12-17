import json
import pandas as pd
from pathlib import Path

# 1. SETUP AUTOMATIC PATHS
# This finds the 'eProcurement_AI_Pipeline' folder regardless of where you run the script
BASE_DIR = Path(__file__).resolve().parent.parent 

# Define exact locations using the BASE_DIR
GOLDEN_SET_PATH = BASE_DIR / "classification" / "data" / "formatted_golden_set.json"
RESULTS_NO_LLM = BASE_DIR / "output" / "sika_classified_no_llm.jsonl"
RESULTS_WITH_LLM = BASE_DIR / "output" / "sika_classified_with_llm.jsonl"

def load_json_data(file_path):
    data = []
    if not file_path.exists():
        print(f"❌ Error: File not found at {file_path}")
        return data
    
    with open(file_path, 'r', encoding='utf-8') as f:
        # Check if it's .jsonl (line by line) or .json (one big list)
        if file_path.suffix == '.jsonl':
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
        else:
            data = json.load(f)
    return data

def evaluate(golden_set, results, mode_name):
    # Create a lookup dictionary: { "product name": type_id }
    results_lookup = {item['product_name'].lower().strip(): item.get('type_id') for item in results}
    
    total = 0
    correct = 0
    matches_found = 0

    for gold in golden_set:
        name = gold['product_name'].lower().strip()
        true_id = gold['type_id']

        
        if name in results_lookup:
            matches_found += 1
            predicted_id = results_lookup[name]
            if str(predicted_id) == str(true_id):
                correct += 1
        total += 1

    accuracy = (correct / matches_found) * 100 if matches_found > 0 else 0
    
    # This dictionary contains "scalar" values
    return {
        "Mode": mode_name,
        "Total_Golden": total,
        "Matched": matches_found,
        "Correct": correct,
        "Accuracy_Pct": round(accuracy, 2)
    }

# --- RUN THE EVALUATION ---

# Load files
gold_data = load_json_data(GOLDEN_SET_PATH)
no_llm_data = load_json_data(RESULTS_NO_LLM)
with_llm_data = load_json_data(RESULTS_WITH_LLM)

if gold_data:
    # Perform calculations
    eval_no_llm = evaluate(gold_data, no_llm_data, "FAISS Only")
    eval_with_llm = evaluate(gold_data, with_llm_data, "FAISS + LLM")

    
    df = pd.DataFrame([eval_no_llm, eval_with_llm])

    print("\n" + "="*40)
    print("      CLASSIFICATION PERFORMANCE")
    print("="*40)
    print(df.to_string(index=False))