#!/usr/bin/env python3
"""
Create head-to-head comparison directories for failed tasks.
Copies pred_program, gold_program, pred_results, gold_results, and input.json
for each failed task into a structured comparison folder.
"""

import json
import os
import shutil
from pathlib import Path

# Configuration
BASE_DIR = Path("/homes/gws/tuxm/Project/ScienceAgentBench")
EVAL_DIR = BASE_DIR / "logs/run_evaluation/claude_v1"
PRED_PROGRAMS_DIR = BASE_DIR / "claude_code_outputs/pred_programs"
BENCHMARK_DIR = Path("/homes/gws/tuxm/Project/Paper2Bench-dev/data/ScienceAgentBench/benchmark/benchmark")
GOLD_PROGRAMS_DIR = BENCHMARK_DIR / "gold_programs"
GOLD_RESULTS_DIR = BENCHMARK_DIR / "eval_programs/gold_results"
OUTPUT_DIR = BASE_DIR / "claude_code_outputs/head-head-compare"

# All 52 failed tasks from BENCHMARK_BUGS.md
FAILED_TASKS = [
    # Benchmark Bugs (7)
    21, 34, 58, 77, 78, 89, 92,
    # Ambiguous Instructions (28)
    5, 7, 8, 22, 26, 29, 31, 32, 35, 36, 37, 42, 43, 44, 47, 52, 55, 59, 60, 61, 62, 67, 68, 70, 71, 72, 87, 95, 97, 102,
    # Docker/Infrastructure (7)
    9, 10, 11, 12, 13, 15, 16,
    # Environment Issues (4)
    30, 49, 56, 75,
    # Path Errors (3)
    51, 65, 66,
    # Agent Errors (2)
    2, 45,
    # Evaluation Strict (2)
    69, 85,
]


def get_gold_result_filename(output_fname: str) -> str:
    """
    Map output_fname to gold_results filename.
    E.g., 'pred_results/deforestation_rate.csv' -> 'deforestation_rate_gold.csv'
    """
    # Get just the filename without 'pred_results/' prefix
    basename = os.path.basename(output_fname)
    # Split into name and extension
    name, ext = os.path.splitext(basename)
    # Remove '_pred' suffix if present
    if name.endswith('_pred'):
        name = name[:-5]
    # Add '_gold' suffix
    return f"{name}_gold{ext}"


def find_gold_result_files(gold_result_name: str) -> list:
    """
    Find gold result files matching the expected name.
    Returns list of matching files (there may be multiple for some tasks).
    """
    matches = []
    if GOLD_RESULTS_DIR.exists():
        # Try exact match first
        exact_path = GOLD_RESULTS_DIR / gold_result_name
        if exact_path.exists():
            matches.append(exact_path)
        else:
            # Try pattern matching for variants
            base_name = os.path.splitext(gold_result_name)[0]
            for f in GOLD_RESULTS_DIR.iterdir():
                if f.is_file() and base_name.replace('_gold', '') in f.stem:
                    if '_gold' in f.stem or f.stem == base_name.replace('_gold', ''):
                        matches.append(f)
    return matches


def create_task_comparison(task_id: int) -> dict:
    """
    Create comparison folder for a single task.
    Returns dict with status info.
    """
    status = {
        'task_id': task_id,
        'success': True,
        'errors': [],
        'files_copied': []
    }

    task_eval_dir = EVAL_DIR / str(task_id)
    task_output_dir = OUTPUT_DIR / f"task_{task_id}"

    # Create output directory
    task_output_dir.mkdir(parents=True, exist_ok=True)

    # Read input.json to get metadata
    input_json_path = task_eval_dir / "input" / "input.json"
    if not input_json_path.exists():
        status['errors'].append(f"input.json not found: {input_json_path}")
        status['success'] = False
        return status

    with open(input_json_path, 'r') as f:
        task_info = json.load(f)

    gold_program_name = task_info.get('gold_program_name', '')
    output_fname = task_info.get('output_fname', '')

    # 1. Copy input.json
    try:
        shutil.copy2(input_json_path, task_output_dir / "input.json")
        status['files_copied'].append('input.json')
    except Exception as e:
        status['errors'].append(f"Failed to copy input.json: {e}")

    # 2. Copy pred_program.py
    pred_program_src = PRED_PROGRAMS_DIR / f"pred_{gold_program_name}"
    if pred_program_src.exists():
        try:
            shutil.copy2(pred_program_src, task_output_dir / "pred_program.py")
            status['files_copied'].append('pred_program.py')
        except Exception as e:
            status['errors'].append(f"Failed to copy pred_program: {e}")
    else:
        status['errors'].append(f"pred_program not found: {pred_program_src}")

    # 3. Copy gold_program.py
    gold_program_src = GOLD_PROGRAMS_DIR / gold_program_name
    if gold_program_src.exists():
        try:
            shutil.copy2(gold_program_src, task_output_dir / "gold_program.py")
            status['files_copied'].append('gold_program.py')
        except Exception as e:
            status['errors'].append(f"Failed to copy gold_program: {e}")
    else:
        status['errors'].append(f"gold_program not found: {gold_program_src}")

    # 4. Copy pred_results/
    pred_results_src = task_eval_dir / "pred_results"
    pred_results_dst = task_output_dir / "pred_results"
    if pred_results_src.exists() and any(pred_results_src.iterdir()):
        try:
            if pred_results_dst.exists():
                shutil.rmtree(pred_results_dst)
            shutil.copytree(pred_results_src, pred_results_dst)
            files = list(pred_results_dst.iterdir())
            status['files_copied'].append(f'pred_results/ ({len(files)} files)')
        except Exception as e:
            status['errors'].append(f"Failed to copy pred_results: {e}")
    else:
        # Create empty dir with note
        pred_results_dst.mkdir(exist_ok=True)
        status['errors'].append("pred_results is empty or missing")

    # 5. Copy gold_results/
    gold_results_dst = task_output_dir / "gold_results"
    gold_results_dst.mkdir(exist_ok=True)

    if output_fname:
        gold_result_name = get_gold_result_filename(output_fname)
        gold_files = find_gold_result_files(gold_result_name)

        if gold_files:
            for gold_file in gold_files:
                try:
                    shutil.copy2(gold_file, gold_results_dst / gold_file.name)
                    status['files_copied'].append(f'gold_results/{gold_file.name}')
                except Exception as e:
                    status['errors'].append(f"Failed to copy gold result {gold_file.name}: {e}")
        else:
            status['errors'].append(f"No gold results found for: {gold_result_name}")
    else:
        status['errors'].append("No output_fname in task info")

    return status


def main():
    print("Creating head-to-head comparison directories...")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Processing {len(FAILED_TASKS)} failed tasks\n")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for task_id in sorted(set(FAILED_TASKS)):  # Remove duplicates and sort
        print(f"Processing task {task_id}...", end=" ")
        status = create_task_comparison(task_id)
        results.append(status)

        if status['errors']:
            print(f"WARNINGS: {len(status['errors'])}")
            for err in status['errors']:
                print(f"  - {err}")
        else:
            print("OK")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    successful = [r for r in results if not r['errors']]
    partial = [r for r in results if r['errors'] and r['files_copied']]
    failed = [r for r in results if r['errors'] and not r['files_copied']]

    print(f"Total tasks processed: {len(results)}")
    print(f"Fully successful: {len(successful)}")
    print(f"Partial (some files missing): {len(partial)}")
    print(f"Failed (no files copied): {len(failed)}")

    if failed:
        print("\nFailed tasks:")
        for r in failed:
            print(f"  Task {r['task_id']}: {r['errors']}")

    # Verify output
    created_dirs = list(OUTPUT_DIR.glob("task_*"))
    print(f"\nCreated {len(created_dirs)} task directories")


if __name__ == "__main__":
    main()
