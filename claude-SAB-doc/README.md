# Claude Code CLI for ScienceAgentBench

This document describes how to run Claude Code CLI on all 102 ScienceAgentBench tasks.

## Features
- Per-task directory logging with evaluation results
- Resume functionality for both inference and evaluation
- Final SR (Success Rate) score calculation
- Security: Claude Code cannot access gold/eval programs

---

## Prerequisites

1. **Docker** installed and running
2. **Claude Code CLI** configured (`~/.claude` directory with valid credentials)
3. **Base Docker images** built (`sab.base.{arch}:latest`)
4. **Conda environment** activated (`claude-sab`)

### Build Base Images (First Time Only)
```bash
cd /homes/gws/tuxm/Project/ScienceAgentBench
conda activate claude-sab
export PYTHONPATH=.

python -m evaluation.harness.run_evaluation \
    --benchmark_path /homes/gws/tuxm/Project/Paper2Bench-dev/data/ScienceAgentBench/benchmark/benchmark \
    --pred_program_path pred_programs \
    --log_fname temp.jsonl \
    --run_id base_build \
    --instance_ids 0 \
    --cache_level base
```

---

## Quick Start

### Run All Tasks (Inference + Evaluation)
```bash
./run_all.sh
```

### Run Only Inference
```bash
./run_inference.sh
```

### Run Only Evaluation
```bash
./run_evaluation.sh
```

### Resume Interrupted Run
```bash
./resume.sh
```

### Calculate Final SR Score
```bash
./calculate_sr.sh
```

---

## Task Range Support

All scripts support running specific task ranges. Resume functionality is preserved.

### Examples
```bash
# Run tasks 1 to 10
./run_inference.sh 1-10

# Run tasks 1-5 and 10-15
./run_inference.sh 1-5,10-15

# Run specific tasks
./run_inference.sh 1 5 10 20

# Run all 102 tasks
./run_inference.sh

# Resume only tasks 50-60
./resume.sh 50-60
```

### Range Formats
| Format | Example | Description |
|--------|---------|-------------|
| Single range | `1-10` | Tasks 1 through 10 |
| Multiple ranges | `1-5,10-15` | Tasks 1-5 and 10-15 |
| Specific IDs | `1 5 10` | Only tasks 1, 5, and 10 |
| All tasks | (no argument) | All 102 tasks |

---

## Directory Structure

After running, the output structure will be:

```
claude_code_outputs/
├── pred_programs/              # Generated Python programs
│   ├── pred_task1.py
│   ├── pred_task2.py
│   └── ...
├── logs/
│   ├── run_summary.jsonl       # Summary for metrics calculation
│   ├── eval_summary.jsonl      # Evaluation summary
│   └── tasks/                  # Per-task detailed logs
│       ├── 1/
│       │   ├── task_info.json      # Task metadata
│       │   ├── inference.json      # Inference result
│       │   ├── evaluation.json     # Evaluation result
│       │   ├── conversation.log    # Full Claude conversation
│       │   └── PASSED or FAILED    # Status marker
│       ├── 2/
│       │   └── ...
│       └── ...
└── debug_logs/                 # Additional debug info
```

---

## Per-Task Log Format

### task_info.json
```json
{
  "instance_id": "1",
  "domain": "bioinformatics",
  "task_inst": "Task instruction...",
  "gold_program_name": "task_name.py",
  "output_fname": "output.csv"
}
```

### inference.json
```json
{
  "instance_id": "1",
  "duration": 161.6,
  "success": true,
  "extracted_code_length": 6098,
  "exit_code": 0,
  "pred_program_path": "pred_programs/pred_task_name.py"
}
```

### evaluation.json
```json
{
  "instance_id": "1",
  "valid_program": 1,
  "success_rate": 1,
  "codebert_score": 0.95,
  "log_info": "{'data_correctness': True, 'func_correctness': True}"
}
```

---

## Security Model

Claude Code runs in an isolated Docker container with:

1. **Only input data copied**: `benchmark/datasets/<dataset_name>/`
2. **No access to**:
   - `gold_programs/` (reference solutions)
   - `eval_programs/` (evaluation scripts)
   - `scoring_rubrics/`
3. **Workspace isolation**: Container only sees `/workspace` mount

This ensures fair benchmark evaluation.

---

## Execution Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Max turns | 50 | Maximum Claude Code turns per task |
| Docker timeout | 1800s | 30 minutes per task |
| Execution mode | Sequential | One task at a time |

### Override Settings
```bash
# Custom max turns
MAX_TURNS=100 ./run_inference.sh

# Custom timeout (seconds)
DOCKER_TIMEOUT=3600 ./run_inference.sh
```

---

## Manual Verification

To manually check if a task passed:

```bash
# Check status marker
ls claude_code_outputs/logs/tasks/1/
# Look for PASSED or FAILED file

# View evaluation result
cat claude_code_outputs/logs/tasks/1/evaluation.json

# View conversation log
less claude_code_outputs/logs/tasks/1/conversation.log
```

### Quick Status Check for All Tasks
```bash
# Count passed/failed
find claude_code_outputs/logs/tasks -name "PASSED" | wc -l
find claude_code_outputs/logs/tasks -name "FAILED" | wc -l
```

---

## Troubleshooting

### Task Failed
1. Check `conversation.log` for Claude Code errors
2. Check `inference.json` for exit code
3. Check `evaluation.json` for specific failure reason

### Resume Not Working
- Ensure both `inference.json` exists AND succeeded
- Force re-run specific task: use `--instance_ids` flag

### Docker Issues
- Verify base image exists: `docker images | grep sab.base`
- Rebuild if needed: run base image build command above

---

## Expected Output

After completing all 102 tasks:
```
================
Success Rate: 0.XXXX
CodeBERTScore: 0.XXXX
Valid Program Rate: 0.XXXX
Cost: N/A (subscription-based)
================
```
