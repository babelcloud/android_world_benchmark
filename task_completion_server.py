#!/usr/bin/env python3
"""Task completion MCP server using FastMCP."""

from typing import Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("task-completion")

@mcp.tool()
async def answer_action(text: str) -> str:
    """Provide an answer that will be submitted to the evaluation system.

    Args:
        text: The answer text
    """
    return f"ANSWER_ACTION:{text}"

@mcp.tool()
async def finish_task(success: bool) -> str:
    """Signal that a task has been completed.

    Args:
        success: Whether the task was completed successfully
    """
    status = "Success" if success else "Failed"
    return f"Task completion acknowledged: {status}"

if __name__ == "__main__":
    # Run the server using stdio transport
    mcp.run(transport='stdio')