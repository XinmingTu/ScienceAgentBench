"""
Main entry point for Claude Code CLI evaluation on ScienceAgentBench.

This script runs Claude Code autonomously on scientific tasks:
1. Loads tasks from HuggingFace dataset
2. Runs Claude Code in Docker containers sequentially
3. Extracts predicted programs
4. Optionally runs evaluation using existing harness

Usage:
    python -m claude_code.run_claude_code_eval \
        --benchmark_path /path/to/benchmark \
        --pred_program_path pred_programs \
        --log_fname claude_run.jsonl \
        --eval_log_fname claude_eval.jsonl \
        --run_id claude_v1 \
        [--instance_ids 0 1 2] \
        [--skip_inference] \
        [--skip_evaluation]
"""

import os
import sys
from argparse import ArgumentParser
from pathlib import Path

from datasets import load_dataset
from tqdm import tqdm

from .claude_code_runner import ClaudeCodeRunner
from .utils import (
    setup_logging,
    check_resume_condition,
    load_existing_logs,
    append_log,
    str2bool,
)


def parse_args():
    """Parse command line arguments."""
    parser = ArgumentParser(
        description="Run Claude Code CLI on ScienceAgentBench tasks"
    )

    # Paths
    parser.add_argument(
        "--benchmark_path",
        type=str,
        required=True,
        help="Path to benchmark directory containing datasets/, eval_programs/, gold_programs/",
    )
    parser.add_argument(
        "--pred_program_path",
        type=str,
        default="pred_programs",
        help="Output directory for predicted programs",
    )
    parser.add_argument(
        "--log_fname",
        type=str,
        default="claude_code_run.jsonl",
        help="Log file for inference runs (JSONL)",
    )
    parser.add_argument(
        "--eval_log_fname",
        type=str,
        default="claude_code_eval.jsonl",
        help="Log file for evaluation results (JSONL)",
    )

    # Execution control
    parser.add_argument(
        "--run_id",
        type=str,
        required=True,
        help="Unique identifier for this run",
    )
    parser.add_argument(
        "--instance_ids",
        nargs="+",
        type=str,
        default=None,
        help="Specific instance IDs to run (space separated)",
    )
    parser.add_argument(
        "--skip_inference",
        action="store_true",
        help="Skip inference, only run evaluation",
    )
    parser.add_argument(
        "--skip_evaluation",
        action="store_true",
        help="Skip evaluation, only run inference",
    )

    # Claude Code settings
    parser.add_argument(
        "--max_turns",
        type=int,
        default=10,
        help="Maximum turns for Claude Code execution (default: 10)",
    )
    parser.add_argument(
        "--docker_timeout",
        type=int,
        default=1800,
        help="Timeout for Docker container execution in seconds (default: 1800)",
    )
    parser.add_argument(
        "--claude_home",
        type=str,
        default=os.path.expanduser("~/.claude"),
        help="Path to Claude authentication directory",
    )

    # Evaluation settings
    parser.add_argument(
        "--max_eval_workers",
        type=int,
        default=4,
        help="Maximum parallel workers for evaluation (default: 4)",
    )

    return parser.parse_args()


def run_evaluation(
    benchmark_path: str,
    pred_program_path: str,
    eval_log_fname: str,
    run_id: str,
    instance_ids: list,
    max_workers: int,
):
    """
    Run evaluation using the existing ScienceAgentBench harness.

    Args:
        benchmark_path: Path to benchmark directory
        pred_program_path: Path to predicted programs
        eval_log_fname: Path to evaluation log file
        run_id: Run identifier
        instance_ids: List of instance IDs to evaluate (or None for all)
        max_workers: Number of parallel workers
    """
    # Import here to avoid circular imports and make evaluation optional
    try:
        from evaluation.harness.run_evaluation import main as eval_main
    except ImportError:
        print("Warning: Could not import evaluation harness. Skipping evaluation.")
        return

    print(f"\n{'='*60}")
    print("Starting evaluation phase...")
    print(f"{'='*60}\n")

    eval_main(
        benchmark_path=benchmark_path,
        pred_program_path=pred_program_path,
        log_fname=eval_log_fname,
        dataset_name="osunlp/ScienceAgentBench",
        split="validation",
        instance_ids=instance_ids,
        max_workers=max_workers,
        force_rebuild=False,
        cache_level="base",
        clean=False,
        open_file_limit=4096,
        run_id=run_id,
        timeout=1800,
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        azure_openai_key=os.environ.get("AZURE_OPENAI_KEY", ""),
        azure_openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", ""),
        azure_openai_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        azure_openai_deployment_name=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", ""),
    )


def main():
    """Main entry point for Claude Code evaluation."""
    args = parse_args()

    # Setup logging
    log_dir = Path(args.log_fname).parent
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logging(args.run_id, log_dir)

    logger.info(f"Starting Claude Code evaluation run: {args.run_id}")
    logger.info(f"Benchmark path: {args.benchmark_path}")
    logger.info(f"Pred program path: {args.pred_program_path}")

    # Validate paths
    benchmark_path = Path(args.benchmark_path).resolve()
    if not (benchmark_path / "datasets").exists():
        logger.error(f"Invalid benchmark_path: {benchmark_path}/datasets not found")
        sys.exit(1)

    # Create output directories
    pred_program_path = Path(args.pred_program_path)
    pred_program_path.mkdir(parents=True, exist_ok=True)

    # Load dataset from HuggingFace
    logger.info("Loading ScienceAgentBench dataset from HuggingFace...")
    try:
        dataset = load_dataset("osunlp/ScienceAgentBench", split="validation")
        logger.info(f"Loaded {len(dataset)} tasks")
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        sys.exit(1)

    # Filter by instance IDs if specified
    instance_ids_set = set(args.instance_ids) if args.instance_ids else None
    if instance_ids_set:
        logger.info(f"Filtering to {len(instance_ids_set)} specific instances")

    # Run inference phase
    if not args.skip_inference:
        logger.info("Starting inference phase...")

        # Initialize runner
        runner = ClaudeCodeRunner(
            benchmark_path=str(benchmark_path),
            pred_program_path=str(pred_program_path),
            claude_home=args.claude_home,
            run_id=args.run_id,
            max_turns=args.max_turns,
            docker_timeout=args.docker_timeout,
        )

        # Build Claude Code Docker image if needed
        try:
            runner.ensure_docker_image()
        except RuntimeError as e:
            logger.error(str(e))
            sys.exit(1)

        # Load existing logs for resume
        run_logs = load_existing_logs(args.log_fname)
        eval_logs = load_existing_logs(args.eval_log_fname)
        logger.info(
            f"Found {len(run_logs)} existing run logs, {len(eval_logs)} eval logs"
        )

        # Process tasks sequentially
        tasks_run = 0
        tasks_skipped = 0

        print(f"\n{'='*60}")
        print(f"Running Claude Code on ScienceAgentBench tasks")
        print(f"Max turns: {args.max_turns}, Timeout: {args.docker_timeout}s")
        print(f"{'='*60}\n")

        for idx, example in enumerate(tqdm(dataset, desc="Running Claude Code")):
            instance_id = str(example["instance_id"])

            # Filter check
            if instance_ids_set and instance_id not in instance_ids_set:
                continue

            # Resume check: skip if BOTH pred file AND eval result exist
            pred_fname = runner.get_pred_filename(example)
            if check_resume_condition(pred_fname, instance_id, eval_logs):
                logger.info(f"Skipping {instance_id} - already completed")
                tasks_skipped += 1
                continue

            # Run Claude Code on this task
            try:
                result = runner.run_task(example)
                run_logs[instance_id] = result

                # Save log incrementally
                append_log(args.log_fname, instance_id, result)
                tasks_run += 1

            except Exception as e:
                logger.error(f"Error on {instance_id}: {e}")
                error_result = {"error": str(e), "success": False}
                run_logs[instance_id] = error_result
                append_log(args.log_fname, instance_id, error_result)
                tasks_run += 1

        logger.info(f"Inference complete: {tasks_run} tasks run, {tasks_skipped} skipped")

    # Run evaluation phase
    if not args.skip_evaluation:
        run_evaluation(
            benchmark_path=str(benchmark_path),
            pred_program_path=str(pred_program_path),
            eval_log_fname=args.eval_log_fname,
            run_id=args.run_id,
            instance_ids=args.instance_ids,
            max_workers=args.max_eval_workers,
        )

    logger.info("Done!")
    print(f"\n{'='*60}")
    print("Claude Code evaluation complete!")
    print(f"Run logs: {args.log_fname}")
    print(f"Eval logs: {args.eval_log_fname}")
    print(f"Predictions: {args.pred_program_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
