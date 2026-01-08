#!/bin/bash
# Calculate final Success Rate (SR) and other metrics

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${PROJECT_DIR}/claude_code_outputs"
LOG_DIR="${OUTPUT_DIR}/logs"
RUN_SUMMARY="${LOG_DIR}/run_summary.jsonl"
EVAL_SUMMARY="${LOG_DIR}/eval_summary.jsonl"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Calculate Final Metrics${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if log files exist
if [ ! -f "${RUN_SUMMARY}" ]; then
    echo -e "${RED}Error: Run summary not found at ${RUN_SUMMARY}${NC}"
    echo "Please run inference first: ./run_inference.sh"
    exit 1
fi

if [ ! -f "${EVAL_SUMMARY}" ]; then
    echo -e "${RED}Error: Evaluation summary not found at ${EVAL_SUMMARY}${NC}"
    echo "Please run evaluation first: ./run_evaluation.sh"
    exit 1
fi

# Count entries
RUN_COUNT=$(wc -l < "${RUN_SUMMARY}")
EVAL_COUNT=$(wc -l < "${EVAL_SUMMARY}")

echo "Log files:"
echo "  Run summary:  ${RUN_SUMMARY} (${RUN_COUNT} entries)"
echo "  Eval summary: ${EVAL_SUMMARY} (${EVAL_COUNT} entries)"
echo ""

if [ "${RUN_COUNT}" -ne "${EVAL_COUNT}" ]; then
    echo -e "${YELLOW}Warning: Run and eval counts don't match${NC}"
    echo "Some tasks may not have been evaluated yet."
    echo ""
fi

# Change to project directory
cd "${PROJECT_DIR}"

# Ensure PYTHONPATH is set
export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH}"

# Activate conda environment
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
    conda activate claude-sab
elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
    conda activate claude-sab
fi

echo -e "${GREEN}Calculating metrics...${NC}"
echo ""

# Calculate metrics
python calculate_metrics.py \
    --run_logs "${RUN_SUMMARY}" \
    --eval_logs "${EVAL_SUMMARY}"

echo ""

# Quick stats from per-task logs
TASK_LOG_DIR="${LOG_DIR}/tasks"
if [ -d "${TASK_LOG_DIR}" ]; then
    echo -e "${BLUE}Per-task status:${NC}"
    PASSED=$(find "${TASK_LOG_DIR}" -name "PASSED" 2>/dev/null | wc -l)
    FAILED=$(find "${TASK_LOG_DIR}" -name "FAILED" 2>/dev/null | wc -l)
    TOTAL=$((PASSED + FAILED))
    echo "  Passed: ${PASSED}"
    echo "  Failed: ${FAILED}"
    echo "  Total:  ${TOTAL}"
    if [ "${TOTAL}" -gt 0 ]; then
        PASS_RATE=$(echo "scale=4; ${PASSED} / ${TOTAL}" | bc)
        echo "  Pass rate: ${PASS_RATE}"
    fi
    echo ""
fi

echo -e "${GREEN}Done!${NC}"
