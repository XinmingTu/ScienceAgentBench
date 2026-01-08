"""
Prompt templates for autonomous Claude Code CLI execution on ScienceAgentBench.

The prompt is designed to guide Claude through a structured workflow:
1. Understand the task
2. Explore the data
3. Self-Q&A (ask and answer questions autonomously)
4. Plan the implementation
5. Implement the solution
6. Verify the output
"""

AGENTIC_PROMPT_TEMPLATE = """
You are solving a scientific programming task. Work autonomously through these phases:

## PHASE 1: UNDERSTAND THE TASK
Read and understand the task requirements below carefully.

## PHASE 2: EXPLORE THE DATA
Use your file reading tools to explore the dataset files. Look at:
- File structure and formats (CSV, JSON, etc.)
- Column names and data types
- Sample values and data distributions
- Any special formatting or encoding

## PHASE 3: SELF-Q&A (Ask and answer your own questions)
Before coding, think through these questions and answer them based on your data exploration:

**Q1: What is the exact input data format?**
(Answer based on what you found in the files)

**Q2: What preprocessing or data cleaning is needed?**
(Consider missing values, data types, normalization)

**Q3: What algorithm or approach should I use for this task?**
(Consider the task requirements and data characteristics)

**Q4: What is the expected output format?**
(Check the output filename and task instructions)

**Q5: Are there any edge cases or potential issues to handle?**
(Consider data quality, special cases, error handling)

Write out your answers to help guide your implementation.

## PHASE 4: PLAN THE IMPLEMENTATION
Write a step-by-step plan for the solution:
1. Data loading
2. Data preprocessing
3. Core algorithm/analysis
4. Output generation
5. File saving

## PHASE 5: IMPLEMENT
Write the complete Python program. The program must:
1. Load data from the dataset path
2. Process/analyze as required by the task
3. Save output to the specified output file path

**CRITICAL PATH REQUIREMENTS:**
Your program will be evaluated in a different environment. You MUST use these EXACT paths:
- Dataset files: `/testbed/benchmark/datasets/<dataset_name>/...`
- Output file: `/testbed/pred_results/<output_filename>`

Replace <dataset_name> with the actual dataset folder name from the task.
Replace <output_filename> with the actual output filename (e.g., clintox_test_pred.csv).

Example paths:
- Input: `/testbed/benchmark/datasets/clintox/clintox_train.csv`
- Output: `/testbed/pred_results/clintox_test_pred.csv`

Other implementation requirements:
- All imports must be at the top of the file
- Ensure the output directory exists before writing (use os.makedirs)
- Handle potential errors gracefully
- The program must be complete and runnable standalone

## PHASE 6: VERIFY
After writing the code, verify:
- All imports are at the top
- The code is complete and can run standalone
- Output is saved to the correct path
- No placeholder code or TODOs remain

---

## TASK INSTRUCTION:
{task_inst}

## DATASET LOCATION (for exploration):
{dataset_path}
(Note: Use these paths to explore data. But in your final program, use /testbed/benchmark/datasets/... paths as specified above.)

## DATASET STRUCTURE:
```
{dataset_folder_tree}
```

## DATA PREVIEW:
{dataset_preview}

## REQUIRED OUTPUT FILE:
The output filename is: {output_fname}
In your final program, save to: /testbed/{output_fname}

---

NOW BEGIN: Start with Phase 1 and work through all phases autonomously.
Use your tools to explore files, then write and save the final Python program.
"""


def format_task_prompt(
    task_inst: str,
    dataset_path: str,
    dataset_folder_tree: str,
    dataset_preview: str,
    output_fname: str,
) -> str:
    """
    Format the agentic prompt for a ScienceAgentBench task.

    Args:
        task_inst: Task instruction text
        dataset_path: Path to the dataset directory
        dataset_folder_tree: Directory tree structure of the dataset
        dataset_preview: Preview of dataset contents
        output_fname: Path where output should be saved

    Returns:
        Formatted prompt string
    """
    return AGENTIC_PROMPT_TEMPLATE.format(
        task_inst=task_inst,
        dataset_path=dataset_path,
        dataset_folder_tree=dataset_folder_tree,
        dataset_preview=dataset_preview,
        output_fname=output_fname,
    )


def format_task_prompt_from_example(example: dict, workspace_path: str = "/workspace") -> str:
    """
    Format the prompt from a HuggingFace dataset example.

    Args:
        example: Task instance from HuggingFace dataset
        workspace_path: Base workspace path in the container

    Returns:
        Formatted prompt string

    Raises:
        KeyError: If required fields are missing from the example
    """
    # Validate required fields
    required_fields = ["dataset_folder_tree", "output_fname", "task_inst", "dataset_preview"]
    missing = [f for f in required_fields if f not in example]
    if missing:
        raise KeyError(f"Missing required fields in example: {missing}")

    # Extract dataset folder name from tree
    folder_tree = example["dataset_folder_tree"]
    if not folder_tree or not folder_tree.strip():
        raise ValueError("dataset_folder_tree is empty")

    dataset_name = folder_tree.split("\n")[0].strip("|-- ").rstrip("/")
    if not dataset_name:
        raise ValueError(f"Could not extract dataset name from folder tree: {folder_tree[:100]}")

    # Construct paths relative to workspace (for exploration)
    # Note: final program should use /testbed/... paths as specified in prompt
    dataset_path = f"{workspace_path}/benchmark/datasets/{dataset_name}"
    output_fname = example['output_fname']  # Just the relative path, prompt specifies /testbed prefix

    return format_task_prompt(
        task_inst=example["task_inst"],
        dataset_path=dataset_path,
        dataset_folder_tree=folder_tree,
        dataset_preview=example["dataset_preview"],
        output_fname=output_fname,
    )
