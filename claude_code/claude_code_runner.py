"""
Claude Code CLI Runner for ScienceAgentBench.

Handles individual task execution inside Docker containers with:
- Autonomous multi-turn execution
- Self-Q&A workflow
- File-based output extraction
"""

import docker
import json
import logging
import os
import platform
import shutil
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional

from .dockerfiles_claude import get_dockerfile_claude_base, get_image_name
from .prompts import format_task_prompt_from_example
from .utils import extract_program_from_workspace, extract_python_code

logger = logging.getLogger("claude_code.runner")


class ClaudeCodeRunner:
    """
    Runs Claude Code CLI on ScienceAgentBench tasks inside Docker containers.

    Features:
    - Autonomous multi-turn execution (up to max_turns)
    - Self-Q&A workflow guided by structured prompt
    - Sandbox isolation with temp workspace
    - Output extraction from files or code blocks
    """

    WORKSPACE_PATH = "/workspace"
    CLAUDE_CONFIG_PATH = "/home/nonroot/.claude"  # Non-root user for --dangerously-skip-permissions
    DEFAULT_MAX_TURNS = 10
    DEFAULT_TIMEOUT = 1800  # 30 minutes

    def __init__(
        self,
        benchmark_path: str,
        pred_program_path: str,
        claude_home: str,
        run_id: str,
        max_turns: int = DEFAULT_MAX_TURNS,
        docker_timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Initialize the Claude Code runner.

        Args:
            benchmark_path: Path to the benchmark directory containing datasets/
            pred_program_path: Path to save predicted programs
            claude_home: Path to Claude authentication directory (~/.claude)
            run_id: Unique identifier for this run
            max_turns: Maximum turns for Claude Code execution
            docker_timeout: Timeout in seconds for Docker container
        """
        self.benchmark_path = Path(benchmark_path).resolve()
        self.pred_program_path = Path(pred_program_path).resolve()
        self.claude_home = Path(claude_home).resolve()
        self.run_id = run_id
        self.max_turns = max_turns
        self.docker_timeout = docker_timeout

        self.client = docker.from_env()
        self.arch = self._detect_arch()
        self.image_name = get_image_name(self.arch)

        # Ensure output directory exists
        self.pred_program_path.mkdir(parents=True, exist_ok=True)

    def _detect_arch(self) -> str:
        """Detect system architecture."""
        machine = platform.machine()
        if machine in {"aarch64", "arm64"}:
            return "arm64"
        return "x86_64"

    @property
    def docker_platform(self) -> str:
        """Get Docker platform string for the current architecture."""
        if self.arch == "arm64":
            return "linux/arm64/v8"
        return "linux/x86_64"

    def ensure_docker_image(self):
        """Build Docker image if it doesn't exist."""
        try:
            self.client.images.get(self.image_name)
            logger.info(f"Docker image {self.image_name} already exists")
        except docker.errors.ImageNotFound:
            logger.info(f"Building Docker image {self.image_name}...")
            self._build_docker_image()

    def _build_docker_image(self):
        """Build the Claude Code Docker image."""
        # First ensure base image exists
        base_image = f"sab.base.{self.arch}:latest"
        try:
            self.client.images.get(base_image)
        except docker.errors.ImageNotFound:
            raise RuntimeError(
                f"Base image {base_image} not found. "
                "Please run the standard evaluation first to build base images:\n"
                "python -m evaluation.harness.run_evaluation --run_id base_build --instance_ids 0"
            )

        # Create temporary build context
        with tempfile.TemporaryDirectory() as build_dir:
            dockerfile_content = get_dockerfile_claude_base(self.docker_platform, self.arch)
            dockerfile_path = Path(build_dir) / "Dockerfile"
            dockerfile_path.write_text(dockerfile_content)

            logger.info("Building Claude Code Docker image...")
            try:
                self.client.images.build(
                    path=build_dir,
                    tag=self.image_name,
                    rm=True,
                    platform=self.docker_platform,
                )
                logger.info(f"Successfully built {self.image_name}")
            except docker.errors.BuildError as e:
                logger.error(f"Failed to build Docker image: {e}")
                raise

    def run_task(self, example: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run Claude Code on a single task.

        Args:
            example: Task instance from HuggingFace dataset

        Returns:
            Dictionary with output, duration, success status, and any errors
        """
        instance_id = str(example["instance_id"])
        gold_program_name = example["gold_program_name"]
        pred_fname = self.pred_program_path / f"pred_{gold_program_name}"

        logger.info(f"Processing task {instance_id}")

        # Create temporary workspace in /tmp to avoid NFS issues
        temp_workspace = Path(tempfile.mkdtemp(prefix=f"sab_claude_{instance_id}_"))

        try:
            # Setup workspace with task inputs
            self._setup_workspace(temp_workspace, example)

            # Format agentic prompt
            prompt = format_task_prompt_from_example(example, workspace_path=self.WORKSPACE_PATH)

            # Run Claude Code in Docker
            start_time = time.time()
            output, exit_code = self._run_claude_in_docker(temp_workspace, prompt)
            duration = time.time() - start_time

            # Extract Python code from output or workspace files
            python_code = extract_program_from_workspace(temp_workspace, output)

            # If still not found, try to extract from raw output
            if python_code == "ERROR":
                python_code = extract_python_code(output)

            # Save predicted program
            pred_fname.write_text(python_code)

            # Save conversation log for debugging
            log_file = temp_workspace / "conversation.log"
            log_file.write_text(output)

            # Copy log to persistent storage
            debug_log_dir = self.pred_program_path.parent / "debug_logs" / instance_id
            debug_log_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(log_file, debug_log_dir / "conversation.log")

            result = {
                "instance_id": instance_id,
                "output_length": len(output),
                "extracted_code_length": len(python_code),
                "duration": duration,
                "exit_code": exit_code,
                "success": python_code != "ERROR",
            }

            logger.info(
                f"Task {instance_id} completed: "
                f"success={result['success']}, duration={duration:.1f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Error running task {instance_id}: {e}")
            # Write ERROR placeholder so evaluation can proceed
            pred_fname.write_text("ERROR")
            return {
                "instance_id": instance_id,
                "error": str(e),
                "success": False,
            }

        finally:
            # Cleanup temp workspace
            shutil.rmtree(temp_workspace, ignore_errors=True)

    def _setup_workspace(self, workspace: Path, example: Dict[str, Any]):
        """
        Setup workspace with task inputs.

        Copies:
        - Dataset files for the task (from benchmark/datasets/)

        Does NOT copy:
        - Gold programs (would be cheating!)
        - Evaluation scripts (not needed for inference)
        """
        # Create directory structure
        (workspace / "pred_results").mkdir(parents=True, exist_ok=True)
        (workspace / "benchmark" / "datasets").mkdir(parents=True, exist_ok=True)

        # Extract dataset folder name from folder tree
        folder_tree = example["dataset_folder_tree"]
        dataset_name = folder_tree.split("\n")[0].strip("|-- ").rstrip("/")

        # Copy dataset files
        src_dataset = self.benchmark_path / "datasets" / dataset_name
        dst_dataset = workspace / "benchmark" / "datasets" / dataset_name

        if src_dataset.exists():
            shutil.copytree(src_dataset, dst_dataset)
            logger.debug(f"Copied dataset: {src_dataset} -> {dst_dataset}")
        else:
            logger.warning(f"Dataset not found: {src_dataset}")

        # Copy Claude auth files to workspace (will be copied into container)
        claude_dir = workspace / ".claude"
        if self.claude_home.exists():
            shutil.copytree(self.claude_home, claude_dir)
            logger.debug(f"Copied Claude config: {self.claude_home} -> {claude_dir}")

        # Make all files world-readable/writable for nonroot user in container
        import subprocess
        subprocess.run(["chmod", "-R", "777", str(workspace)], check=True)
        logger.debug(f"Set workspace permissions to 777")

    def _run_claude_in_docker(self, workspace: Path, prompt: str) -> tuple:
        """
        Run Claude Code CLI inside Docker container.

        Mounts:
        - workspace -> /workspace
        - ~/.claude -> /root/.claude (authentication)

        Args:
            workspace: Path to the temporary workspace
            prompt: Formatted task prompt

        Returns:
            Tuple of (output_string, exit_code)
        """
        container = None

        try:
            # Write prompt to file (avoid shell escaping issues)
            prompt_file = workspace / "task_prompt.txt"
            prompt_file.write_text(prompt)

            # Create container with volume mounts
            # Note: Claude config is copied to workspace/.claude so set HOME=/workspace
            container = self.client.containers.create(
                image=self.image_name,
                command="tail -f /dev/null",  # Keep alive
                detach=True,
                platform=self.docker_platform,
                volumes={
                    str(workspace): {
                        "bind": self.WORKSPACE_PATH,
                        "mode": "rw"
                    },
                },
                working_dir=self.WORKSPACE_PATH,
                environment={
                    "HOME": self.WORKSPACE_PATH,  # So Claude finds config at /workspace/.claude
                    "CI": "true",
                    "CLAUDE_DISABLE_TELEMETRY": "1",
                },
            )

            # Start container
            container.start()
            logger.debug(f"Container started: {container.id[:12]}")

            # Build Claude Code command
            # Note: -p (print mode) outputs the response and exits
            # --output-format stream-json gives full conversation as JSONL
            # --verbose is required for stream-json with print mode
            claude_cmd = (
                f"claude "
                f"-p "
                f"--dangerously-skip-permissions "
                f"--max-turns {self.max_turns} "
                f"--verbose "
                f"--output-format stream-json "
                f"\"$(cat {self.WORKSPACE_PATH}/task_prompt.txt)\" "
                f"2>&1"
            )

            # Execute Claude Code with timeout
            exec_result = container.exec_run(
                cmd=["bash", "-c", claude_cmd],
                workdir=self.WORKSPACE_PATH,
                environment={
                    "HOME": self.WORKSPACE_PATH,
                    "CI": "true",
                },
            )

            output = exec_result.output.decode("utf-8", errors="replace")
            exit_code = exec_result.exit_code

            if exit_code != 0:
                logger.warning(f"Claude Code exited with code {exit_code}")

            return output, exit_code

        except Exception as e:
            logger.error(f"Error running Claude Code in Docker: {e}")
            return str(e), -1

        finally:
            # Cleanup container
            if container:
                try:
                    container.stop(timeout=5)
                    container.remove(force=True)
                    logger.debug(f"Container cleaned up: {container.id[:12]}")
                except Exception as e:
                    logger.warning(f"Error cleaning up container: {e}")

    def get_pred_filename(self, example: Dict[str, Any]) -> Path:
        """Get the path for the predicted program file."""
        return self.pred_program_path / f"pred_{example['gold_program_name']}"
