"""
Docker image definitions for Claude Code CLI evaluation on ScienceAgentBench.

This extends the SAB base image with Node.js and Claude Code CLI.
"""

# Dockerfile for Claude Code agent container
# Extends SAB base image with Node.js 20.x LTS and Claude Code CLI
_DOCKERFILE_CLAUDE_BASE = r"""
FROM --platform={platform} sab.base.{arch}:latest

# Install Node.js 20.x LTS (required for Claude Code CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Create workspace directory and set permissions for nonroot user
# Note: nonroot user already created in base image
RUN mkdir -p /workspace /output /home/nonroot/.claude \
    && chown -R nonroot:nonroot /workspace /output /home/nonroot

# Set working directory
WORKDIR /workspace

# Switch to non-root user (required for --dangerously-skip-permissions)
USER nonroot

# Environment for non-interactive/autonomous operation
ENV CI=true
ENV CLAUDE_DISABLE_TELEMETRY=1
ENV HOME=/home/nonroot
"""


def get_dockerfile_claude_base(platform: str, arch: str) -> str:
    """
    Get the Dockerfile content for the Claude Code agent container.

    Args:
        platform: Docker platform string (e.g., "linux/x86_64")
        arch: Architecture string (e.g., "x86_64" or "arm64")

    Returns:
        Dockerfile content as a string
    """
    return _DOCKERFILE_CLAUDE_BASE.format(platform=platform, arch=arch)


def get_image_name(arch: str) -> str:
    """
    Get the Docker image name for the given architecture.

    Args:
        arch: Architecture string (e.g., "x86_64" or "arm64")

    Returns:
        Docker image name
    """
    return f"sab.claude.{arch}:latest"
