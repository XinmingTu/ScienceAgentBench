#!/bin/bash
# Resume interrupted Claude Code run
# Will automatically skip completed tasks
#
# Usage:
#   ./resume.sh              # Resume all tasks
#   ./resume.sh 1-10         # Resume tasks 1 to 10 only
#   ./resume.sh 1-5,10-15    # Resume tasks 1-5 and 10-15
#   ./resume.sh 1 5 10       # Resume specific tasks 1, 5, 10

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BENCHMARK_PATH="/homes/gws/tuxm/Project/Paper2Bench-dev/data/ScienceAgentBench/benchmark/benchmark"
OUTPUT_DIR="${PROJECT_DIR}/claude_code_outputs"
PRED_PROGRAM_PATH="${OUTPUT_DIR}/pred_programs"
LOG_DIR="${OUTPUT_DIR}/logs"
RUN_SUMMARY="${LOG_DIR}/run_summary.jsonl"
EVAL_SUMMARY="${LOG_DIR}/eval_summary.jsonl"
RUN_ID="${RUN_ID:-claude_v1}"

# Claude Code settings
MAX_TURNS="${MAX_TURNS:-10}"
DOCKER_TIMEOUT="${DOCKER_TIMEOUT:-1800}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse task range argument
parse_task_range() {
    local input="$1"
    local result=""

    # Handle comma-separated ranges (e.g., "1-5,10-15")
    IFS=',' read -ra RANGES <<< "$input"
    for range in "${RANGES[@]}"; do
        if [[ "$range" == *"-"* ]]; then
            # Range format: "1-10"
            local start="${range%-*}"
            local end="${range#*-}"
            for ((i=start; i<=end; i++)); do
                result="$result $i"
            done
        else
            # Single number
            result="$result $range"
        fi
    done

    echo "$result"
}

# Build instance_ids argument
INSTANCE_IDS_ARG=""
TASK_RANGE_DISPLAY="all (1-102)"
if [ $# -gt 0 ]; then
    # Check if first arg looks like a range (contains - or ,)
    if [[ "$1" == *"-"* ]] || [[ "$1" == *","* ]]; then
        TASK_IDS=$(parse_task_range "$1")
        INSTANCE_IDS_ARG="--instance_ids $TASK_IDS"
        TASK_RANGE_DISPLAY="$1"
        shift  # Remove processed argument
    else
        # Treat all remaining args as task IDs
        INSTANCE_IDS_ARG="--instance_ids $@"
        TASK_RANGE_DISPLAY="$@"
        shift $#
    fi
fi

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Resume Claude Code Run${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check current status
if [ -f "${RUN_SUMMARY}" ]; then
    RUN_COUNT=$(wc -l < "${RUN_SUMMARY}")
    echo "Current status:"
    echo "  Completed inference: ${RUN_COUNT} tasks"
else
    RUN_COUNT=0
    echo "No previous runs found. Starting fresh."
fi

if [ -f "${EVAL_SUMMARY}" ]; then
    EVAL_COUNT=$(wc -l < "${EVAL_SUMMARY}")
    echo "  Completed evaluation: ${EVAL_COUNT} tasks"
else
    EVAL_COUNT=0
fi

# Count passed/failed from per-task logs
TASK_LOG_DIR="${LOG_DIR}/tasks"
if [ -d "${TASK_LOG_DIR}" ]; then
    PASSED=$(find "${TASK_LOG_DIR}" -name "PASSED" 2>/dev/null | wc -l)
    FAILED=$(find "${TASK_LOG_DIR}" -name "FAILED" 2>/dev/null | wc -l)
    echo "  Passed: ${PASSED}, Failed: ${FAILED}"
fi

REMAINING=$((102 - RUN_COUNT))
echo "  Remaining: ~${REMAINING} tasks"
echo -e "  Task range:       ${BLUE}${TASK_RANGE_DISPLAY}${NC}"
echo ""

if [ "${REMAINING}" -eq 0 ] && [ -z "$INSTANCE_IDS_ARG" ]; then
    echo -e "${GREEN}All tasks completed!${NC}"
    echo "Run ./calculate_sr.sh to see final metrics."
    exit 0
fi

# Ask user what to resume
echo "What would you like to resume?"
echo "  1. Inference only (skip evaluation)"
echo "  2. Evaluation only (skip inference)"
echo "  3. Both inference and evaluation"
echo ""
read -p "Enter choice (1-3): " CHOICE

case $CHOICE in
    1)
        SKIP_EVAL="--skip_evaluation"
        SKIP_INFER=""
        echo ""
        echo -e "${GREEN}Resuming inference...${NC}"
        ;;
    2)
        SKIP_EVAL=""
        SKIP_INFER="--skip_inference"
        echo ""
        echo -e "${GREEN}Resuming evaluation...${NC}"
        ;;
    3)
        SKIP_EVAL=""
        SKIP_INFER=""
        echo ""
        echo -e "${GREEN}Resuming full run...${NC}"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Change to project directory
cd "${PROJECT_DIR}"

# Ensure PYTHONPATH is set
export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH}"

# Activate conda environment
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
    conda activate claude-sab
    echo -e "${GREEN}Activated conda environment: claude-sab${NC}"
elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
    conda activate claude-sab
    echo -e "${GREEN}Activated conda environment: claude-sab${NC}"
else
    echo -e "${YELLOW}Warning: Could not find conda. Make sure claude-sab environment is active.${NC}"
fi

# Run Claude Code with resume
python -m claude_code.run_claude_code_eval \
    --benchmark_path "${BENCHMARK_PATH}" \
    --pred_program_path "${PRED_PROGRAM_PATH}" \
    --log_fname "${RUN_SUMMARY}" \
    --eval_log_fname "${EVAL_SUMMARY}" \
    --run_id "${RUN_ID}" \
    --max_turns "${MAX_TURNS}" \
    --docker_timeout "${DOCKER_TIMEOUT}" \
    ${SKIP_EVAL} \
    ${SKIP_INFER} \
    $INSTANCE_IDS_ARG

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Resume complete!${NC}"
echo -e "${GREEN}============================================${NC}"
