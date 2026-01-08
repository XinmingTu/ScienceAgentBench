"""
Utility functions for Claude Code CLI evaluation runner.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Any


def setup_logging(run_id: str, log_dir: Optional[Path] = None) -> logging.Logger:
    """
    Configure logging for the evaluation run.

    Args:
        run_id: Unique identifier for this run
        log_dir: Directory for log files (default: logs/claude_code/{run_id})

    Returns:
        Configured logger instance
    """
    if log_dir is None:
        log_dir = Path("logs") / "claude_code" / run_id
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    logger = logging.getLogger("claude_code")
    logger.setLevel(logging.INFO)

    # File handler
    file_handler = logging.FileHandler(log_dir / "run.log")
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)

    # Add handlers if not already added
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def check_resume_condition(
    pred_fname: Path, instance_id: str, eval_logs: Dict[str, dict],
    skip_eval_check: bool = False
) -> bool:
    """
    Check if a task should be skipped (resume condition).

    Returns True if:
    1. Predicted program file exists and is not ERROR, AND
    2. Either skip_eval_check is True OR evaluation result exists

    Args:
        pred_fname: Path to the predicted program file
        instance_id: Task instance ID
        eval_logs: Dictionary of evaluation results keyed by instance_id
        skip_eval_check: If True, only check pred file (for --skip_evaluation mode)

    Returns:
        True if task should be skipped, False otherwise
    """
    # Check if pred file exists and is valid
    if not pred_fname.exists():
        return False

    try:
        pred_content = pred_fname.read_text().strip()
        if pred_content == "ERROR" or not pred_content:
            return False
    except Exception:
        return False

    # If skip_eval_check, we only need successful inference
    if skip_eval_check:
        return True

    # Check if evaluation result exists
    if instance_id not in eval_logs:
        return False

    return True


def extract_python_code(output: str) -> str:
    """
    Extract Python code from Claude output.

    Handles various code block formats:
    1. ```python ... ```
    2. ``` ... ```
    3. Raw code detection

    Args:
        output: Raw output from Claude Code

    Returns:
        Extracted Python code, or "ERROR" if no valid code found
    """
    # Try Python-specific code block
    match = re.search(r"```python\s*(.*?)```", output, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Try generic code block
    match = re.search(r"```\s*(.*?)```", output, re.DOTALL)
    if match:
        code = match.group(1).strip()
        # Check if it looks like Python
        if any(kw in code for kw in ["import ", "def ", "class ", "print(", "from "]):
            return code

    # Last resort: try to find code-like content (lines starting with import/from)
    lines = output.split("\n")
    code_lines = []
    in_code = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            in_code = True
        if in_code:
            code_lines.append(line)

    if code_lines:
        return "\n".join(code_lines)

    return "ERROR"


def load_existing_logs(log_fname: str) -> Dict[str, dict]:
    """
    Load existing log file for resume capability.

    Args:
        log_fname: Path to the JSONL log file

    Returns:
        Dictionary of log entries keyed by instance_id
    """
    logs = {}
    log_path = Path(log_fname)

    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        if "instance_id" in entry:
                            logs[entry["instance_id"]] = entry
                    except json.JSONDecodeError:
                        continue

    return logs


def append_log(log_fname: str, instance_id: str, result: dict):
    """
    Append a single result to log file.

    Args:
        log_fname: Path to the JSONL log file
        instance_id: Task instance ID
        result: Result dictionary to log
    """
    result = dict(result)  # Copy to avoid modifying original
    result["instance_id"] = instance_id

    # Ensure parent directory exists
    log_path = Path(log_fname)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result) + "\n")


def find_python_files(workspace: Path) -> list:
    """
    Find all Python files in the workspace directory.

    Args:
        workspace: Path to the workspace directory

    Returns:
        List of Path objects for Python files, sorted by modification time (newest first)
    """
    py_files = list(workspace.glob("*.py"))
    # Sort by modification time, newest first
    py_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return py_files


def extract_program_from_workspace(workspace: Path, json_output: Optional[str] = None) -> str:
    """
    Extract the Python program from workspace or JSON output.

    Priority:
    1. Look for written .py files in workspace
    2. Extract from code blocks in JSON output

    Args:
        workspace: Path to the workspace directory
        json_output: Optional JSON output from Claude Code

    Returns:
        Extracted Python code, or "ERROR" if not found
    """
    # Priority 1: Look for written .py file in workspace
    py_files = find_python_files(workspace)
    if py_files:
        # Return the most recently modified Python file
        return py_files[0].read_text()

    # Priority 2: Extract from JSON output
    if json_output:
        try:
            # Try to parse as JSON and extract from conversation
            data = json.loads(json_output)
            # Look for assistant messages with code
            if isinstance(data, list):
                for item in reversed(data):
                    if isinstance(item, dict):
                        content = item.get("content", "")
                        code = extract_python_code(content)
                        if code != "ERROR":
                            return code
            elif isinstance(data, dict):
                # Single response format
                content = data.get("content", "") or data.get("output", "")
                code = extract_python_code(content)
                if code != "ERROR":
                    return code
        except json.JSONDecodeError:
            # If not valid JSON, try to extract code directly
            code = extract_python_code(json_output)
            if code != "ERROR":
                return code

    return "ERROR"


def str2bool(v: str) -> bool:
    """Convert string to boolean for argument parsing."""
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise ValueError(f"Boolean value expected, got {v}")


# ============================================================================
# Per-task logging functions
# ============================================================================

def get_task_log_dir(log_dir: Path, instance_id: str) -> Path:
    """Get the per-task log directory path."""
    return log_dir / "tasks" / str(instance_id)


def save_task_info(log_dir: Path, instance_id: str, example: dict):
    """
    Save task metadata to per-task directory.

    Args:
        log_dir: Base log directory
        instance_id: Task instance ID
        example: Task instance from dataset
    """
    task_dir = get_task_log_dir(log_dir, instance_id)
    task_dir.mkdir(parents=True, exist_ok=True)

    task_info = {
        "instance_id": str(instance_id),
        "domain": example.get("domain", "unknown"),
        "task_inst": example.get("task_inst", ""),
        "gold_program_name": example.get("gold_program_name", ""),
        "output_fname": example.get("output_fname", ""),
    }

    with open(task_dir / "task_info.json", "w", encoding="utf-8") as f:
        json.dump(task_info, f, indent=2)


def save_inference_result(log_dir: Path, instance_id: str, result: dict):
    """
    Save inference result to per-task directory.

    Args:
        log_dir: Base log directory
        instance_id: Task instance ID
        result: Inference result dictionary
    """
    task_dir = get_task_log_dir(log_dir, instance_id)
    task_dir.mkdir(parents=True, exist_ok=True)

    with open(task_dir / "inference.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


def save_evaluation_result(log_dir: Path, instance_id: str, eval_result: dict):
    """
    Save evaluation result to per-task directory and create status marker.

    Args:
        log_dir: Base log directory
        instance_id: Task instance ID
        eval_result: Evaluation result dictionary
    """
    task_dir = get_task_log_dir(log_dir, instance_id)
    task_dir.mkdir(parents=True, exist_ok=True)

    with open(task_dir / "evaluation.json", "w", encoding="utf-8") as f:
        json.dump(eval_result, f, indent=2)

    # Create status marker file
    success = eval_result.get("success_rate", 0) == 1
    marker_file = task_dir / ("PASSED" if success else "FAILED")
    marker_file.touch()

    # Remove the other marker if it exists
    other_marker = task_dir / ("FAILED" if success else "PASSED")
    if other_marker.exists():
        other_marker.unlink()


def save_conversation_log(log_dir: Path, instance_id: str, conversation: str):
    """
    Save conversation log to per-task directory.

    Args:
        log_dir: Base log directory
        instance_id: Task instance ID
        conversation: Full conversation log
    """
    task_dir = get_task_log_dir(log_dir, instance_id)
    task_dir.mkdir(parents=True, exist_ok=True)

    with open(task_dir / "conversation.log", "w", encoding="utf-8") as f:
        f.write(conversation)


def check_task_completed(log_dir: Path, instance_id: str, require_eval: bool = False) -> bool:
    """
    Check if a task has already been completed.

    Args:
        log_dir: Base log directory
        instance_id: Task instance ID
        require_eval: If True, require evaluation to be complete

    Returns:
        True if task is complete, False otherwise
    """
    task_dir = get_task_log_dir(log_dir, instance_id)

    # Check inference result
    inference_file = task_dir / "inference.json"
    if not inference_file.exists():
        return False

    try:
        with open(inference_file, "r", encoding="utf-8") as f:
            inference = json.load(f)
        if not inference.get("success", False):
            return False
    except (json.JSONDecodeError, IOError):
        return False

    # If evaluation not required, inference success is enough
    if not require_eval:
        return True

    # Check evaluation result
    eval_file = task_dir / "evaluation.json"
    return eval_file.exists()


def get_task_status_summary(log_dir: Path) -> dict:
    """
    Get summary of task statuses.

    Args:
        log_dir: Base log directory

    Returns:
        Dictionary with counts of passed, failed, pending tasks
    """
    tasks_dir = log_dir / "tasks"
    if not tasks_dir.exists():
        return {"passed": 0, "failed": 0, "pending": 102, "total": 0}

    passed = 0
    failed = 0

    for task_dir in tasks_dir.iterdir():
        if task_dir.is_dir():
            if (task_dir / "PASSED").exists():
                passed += 1
            elif (task_dir / "FAILED").exists():
                failed += 1

    return {
        "passed": passed,
        "failed": failed,
        "pending": 102 - passed - failed,
        "total": passed + failed,
    }
