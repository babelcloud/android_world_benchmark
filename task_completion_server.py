#!/usr/bin/env python3
"""Task completion MCP server using FastMCP."""

from typing import Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("task-completion")

@mcp.tool()
async def finish_task(success: bool, reason: str) -> str:
    """Signal that a task has been completed.

    Args:
        success: Whether the task was completed successfully
        reason: Text explanation of the completion state
    """
    status = "Success" if success else "Failed"
    return f"Task completion acknowledged: {status} - {reason}"

if __name__ == "__main__":
    # Run the server using stdio transport
    mcp.run(transport='stdio')