#!/bin/bash
# Run both Claude Code inference and evaluation on ScienceAgentBench tasks
#
# Usage:
#   ./run_all.sh              # Run all 102 tasks
#   ./run_all.sh 1-10         # Run tasks 1 to 10
#   ./run_all.sh 1-5,10-15    # Run tasks 1-5 and 10-15
#   ./run_all.sh 1 5 10       # Run specific tasks 1, 5, 10

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
MAX_TURNS="${MAX_TURNS:-50}"
DOCKER_TIMEOUT="${DOCKER_TIMEOUT:-1800}"

# Evaluation settings
MAX_EVAL_WORKERS="${MAX_EVAL_WORKERS:-4}"

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
echo -e "${BLUE}Claude Code Full Run for ScienceAgentBench${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "This will run both inference and evaluation."
echo ""
echo "Configuration:"
echo "  Project dir:      ${PROJECT_DIR}"
echo "  Benchmark path:   ${BENCHMARK_PATH}"
echo "  Output dir:       ${OUTPUT_DIR}"
echo "  Run ID:           ${RUN_ID}"
echo "  Max turns:        ${MAX_TURNS}"
echo "  Docker timeout:   ${DOCKER_TIMEOUT}s"
echo "  Eval workers:     ${MAX_EVAL_WORKERS}"
echo -e "  Task range:       ${BLUE}${TASK_RANGE_DISPLAY}${NC}"
echo ""

# Check prerequisites
if [ ! -d "${BENCHMARK_PATH}/datasets" ]; then
    echo -e "${RED}Error: Benchmark datasets not found at ${BENCHMARK_PATH}/datasets${NC}"
    echo "Please download and extract the benchmark first."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
    exit 1
fi

if [ ! -d "$HOME/.claude" ]; then
    echo -e "${YELLOW}Warning: ~/.claude directory not found${NC}"
    echo "Make sure Claude Code CLI is configured."
fi

if [ -z "${OPENAI_API_KEY}" ]; then
    echo -e "${YELLOW}Warning: OPENAI_API_KEY not set${NC}"
    echo "GPT-4o visual judge may not work without it."
fi

# Create output directories
mkdir -p "${PRED_PROGRAM_PATH}"
mkdir -p "${LOG_DIR}/tasks"

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

# Record start time
START_TIME=$(date +%s)

echo -e "${GREEN}Starting full run...${NC}"
echo ""

# Run Claude Code (inference + evaluation)
python -m claude_code.run_claude_code_eval \
    --benchmark_path "${BENCHMARK_PATH}" \
    --pred_program_path "${PRED_PROGRAM_PATH}" \
    --log_fname "${RUN_SUMMARY}" \
    --eval_log_fname "${EVAL_SUMMARY}" \
    --run_id "${RUN_ID}" \
    --max_turns "${MAX_TURNS}" \
    --docker_timeout "${DOCKER_TIMEOUT}" \
    --max_eval_workers "${MAX_EVAL_WORKERS}" \
    $INSTANCE_IDS_ARG

# Calculate elapsed time
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
HOURS=$((ELAPSED / 3600))
MINUTES=$(((ELAPSED % 3600) / 60))
SECONDS=$((ELAPSED % 60))

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Full run complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Total time: ${HOURS}h ${MINUTES}m ${SECONDS}s"
echo ""
echo "Outputs:"
echo "  Predicted programs: ${PRED_PROGRAM_PATH}"
echo "  Run summary:        ${RUN_SUMMARY}"
echo "  Eval summary:       ${EVAL_SUMMARY}"
echo "  Task logs:          ${LOG_DIR}/tasks/"
echo ""
echo "Next steps:"
echo "  Calculate final SR: ./calculate_sr.sh"
