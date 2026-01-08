# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

ScienceAgentBench is a benchmark for evaluating language agents on data-driven scientific discovery tasks. It contains 102 tasks extracted from peer-reviewed publications across four scientific disciplines. The benchmark evaluates agents' ability to generate self-contained Python programs that solve scientific tasks.

## Environment Setup

Two conda environments are required:

```bash
# Main environment for running agents
conda create -n sci-agent python=3.10 pip setuptools wheel
conda activate sci-agent
pip install -r requirements.txt
export PYTHONPATH=.

# Evaluation environment (keep clean, only install pip-tools)
conda create -n sci-agent-eval python=3.10 pip setuptools wheel
conda activate sci-agent-eval
pip install pip-tools
conda deactivate
```

## API Keys

- OpenAI models: `export OPENAI_API_KEY={key}`
- Amazon Bedrock models: Configure `~/.aws/config` with AWS credentials

## Common Commands

### Run Agent Inference
```bash
python -u run_infer.py \
    --llm_engine_name {MODEL_NAME} \
    --log_fname {LOG_FNAME} \
    [--use_knowledge] \
    [--use_self_debug]
```

### Extract Predictions from Logs
```bash
python -u recover_pred_from_log.py --log_fname {LOG_FNAME} [--is_opendevin]
```

### Dockerized Evaluation (Recommended)
```bash
export OPENAI_API_KEY={key}
python -m evaluation.harness.run_evaluation \
    --benchmark_path benchmark \
    --pred_program_path pred_programs \
    --log_fname {EVAL_LOG}.jsonl \
    --run_id {RUN_ID} \
    --max_workers 4
```

### Direct Evaluation (Non-Docker)
```bash
export OPENAI_API_KEY={key}
python -u run_eval.py --log_fname {EVAL_LOG}.jsonl
```

### Calculate Metrics
```bash
python calculate_metrics.py \
    --run_logs run1.jsonl --run_logs run2.jsonl --run_logs run3.jsonl \
    --eval_logs eval1.jsonl --eval_logs eval2.jsonl --eval_logs eval3.jsonl
```

## Architecture

### Core Components

**Agent (`agent.py`)**: `ScienceAgent` class that generates Python code to solve scientific tasks.
- Supports direct prompting and self-debug modes
- Uses `litellm` for context trimming
- Extracts Python code from LLM responses using regex

**LLM Engines (`engine/`)**: Abstraction layer for LLM providers
- `base_engine.py`: `LLMEngine` factory that routes to provider-specific engines
- `openai_engine.py`: OpenAI API (gpt-*, o1-*)
- `bedrock_engine.py`: Amazon Bedrock (claude, llama, mistral)

**Evaluation Harness (`evaluation/harness/`)**: Docker-based parallel evaluation system adapted from SWE-bench
- `run_evaluation.py`: Main entry point for dockerized evaluation
- `test_spec.py`: Creates test specifications for each instance
- `docker_build.py`: Handles Docker image building
- `grading.py`: Scoring logic

### Data Flow

1. `run_infer.py` loads tasks from HuggingFace (`osunlp/ScienceAgentBench`)
2. `ScienceAgent.solve_task()` generates Python code, optionally with self-debug loop
3. Trajectories saved to JSONL log files
4. `recover_pred_from_log.py` extracts final code to `pred_programs/`
5. Evaluation runs code in isolated environments, checks outputs against gold programs
6. GPT-4o judges visual outputs; CodeBERTScore measures code similarity
7. `calculate_metrics.py` aggregates results across multiple runs

### Benchmark Data Structure

After downloading and unzipping the full benchmark:
```
benchmark/
├── datasets/       # Input datasets for tasks
├── eval_programs/  # Evaluation scripts per task
├── gold_programs/  # Reference solutions
└── scoring_rubrics/
```

### Key Metrics

- **Success Rate**: Whether generated code produces correct output
- **Valid Program Rate**: Whether code executes without errors
- **CodeBERTScore**: Code similarity to gold programs
- **Cost**: API cost per task