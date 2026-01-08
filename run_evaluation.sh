#!/bin/bash
# Usage: ./run_evaluation.sh [INSTANCE_IDS] [OPTIONS]
#
# Examples:
#   ./run_evaluation.sh                      # Run all instances
#   ./run_evaluation.sh 4 5 6                # Run specific instances
#   ./run_evaluation.sh 1-10                 # Run range of instances (1 through 10)
#   ./run_evaluation.sh 1-10 --force_reeval  # Force re-evaluation
#   ./run_evaluation.sh --force_reeval       # Force re-eval all instances

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration - update these paths as needed
BENCHMARK_PATH="/homes/gws/tuxm/Project/Paper2Bench-dev/data/ScienceAgentBench/benchmark/benchmark"
PRED_PROGRAM_PATH="${SCRIPT_DIR}/claude_code_outputs/pred_programs"
LOG_DIR="${SCRIPT_DIR}/logs/run_evaluation/claude_v1"
LOG_FNAME="${LOG_DIR}/eval_summary.jsonl"
RUN_ID="claude_v1"
MAX_WORKERS=8
TIMEOUT=3600

# Activate conda environment
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
    conda activate claude-sab
    echo "Activated conda environment: claude-sab"
elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
    conda activate claude-sab
    echo "Activated conda environment: claude-sab"
else
    echo "Warning: Could not find conda. Make sure claude-sab environment is active."
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Parse arguments
INSTANCE_IDS=()
EXTRA_ARGS=()

for arg in "$@"; do
    if [[ "$arg" == --* ]]; then
        # It's a flag like --force_reeval
        EXTRA_ARGS+=("$arg")
    elif [[ "$arg" =~ ^[0-9]+-[0-9]+$ ]]; then
        # It's a range like 1-102
        START=$(echo "$arg" | cut -d'-' -f1)
        END=$(echo "$arg" | cut -d'-' -f2)
        for i in $(seq "$START" "$END"); do
            INSTANCE_IDS+=("$i")
        done
    elif [[ "$arg" =~ ^[0-9]+$ ]]; then
        # It's a single number
        INSTANCE_IDS+=("$arg")
    else
        EXTRA_ARGS+=("$arg")
    fi
done

# Build the command
CMD="python -m evaluation.harness.run_evaluation \
--benchmark_path ${BENCHMARK_PATH} \
--pred_program_path ${PRED_PROGRAM_PATH} \
--log_fname ${LOG_FNAME} \
--run_id ${RUN_ID} \
--cache_level base \
--max_workers ${MAX_WORKERS} \
--timeout ${TIMEOUT}"

# Add instance IDs if specified
if [ ${#INSTANCE_IDS[@]} -gt 0 ]; then
    CMD="$CMD --instance_ids ${INSTANCE_IDS[*]}"
    echo "Running evaluation for instances: ${INSTANCE_IDS[*]}"
else
    echo "Running evaluation for all instances"
fi

# Add extra args (like --force_reeval)
if [ ${#EXTRA_ARGS[@]} -gt 0 ]; then
    CMD="$CMD ${EXTRA_ARGS[*]}"
fi

echo ""
echo "Configuration:"
echo "  Benchmark path:   ${BENCHMARK_PATH}"
echo "  Pred programs:    ${PRED_PROGRAM_PATH}"
echo "  Log file:         ${LOG_FNAME}"
echo "  Run ID:           ${RUN_ID}"
echo "  Max workers:      ${MAX_WORKERS}"
echo ""
echo "Running: $CMD"
echo ""

eval "$CMD"

echo ""
echo "Evaluation complete!"
echo "Results saved to: ${LOG_FNAME}"