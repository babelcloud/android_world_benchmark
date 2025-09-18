"""Simple Claude Code agent for Android World."""

import asyncio
from typing import Any
from contextlib import aclosing

from android_world.agents import base_agent
from android_world.env import interface

from claude_code_sdk import (
    query, ClaudeCodeOptions,
    AssistantMessage, ResultMessage,
    TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock
)


class SimpleClaude(base_agent.EnvironmentInteractingAgent):
    """Simple agent using Claude Code SDK with streaming output."""

    def __init__(
        self,
        env: interface.AsyncEnv,
        name: str = 'simple_claude',
        transition_pause: float | None = 1.0,
    ):
        super().__init__(env, name, transition_pause)
        self._step_count = 0
        self._current_box_id = "box-id"  # Track current Android box ID

    async def _process_claude_query(self, query_text: str) -> tuple[str, bool]:
        """Process a query with Claude using standalone query() function."""
        # Create options for each query (fresh session each time)
        options = ClaudeCodeOptions(
            allowed_tools=["Read", "Write", "Bash"],
            permission_mode="acceptEdits",
            system_prompt=f"""You are controlling an Android device to accomplish specific goals.

You have access to tools that can interact with the Android device. 

Current box ID (if any): {self._current_box_id}

Always start by taking a screenshot to see the current state, then proceed with appropriate actions to accomplish the given goal.

Be methodical and take one action at a time. Explain your reasoning for each action.

IMPORTANT: When you have successfully completed the task, you must call the finish_task tool to signal completion. Use:
- finish_task(success=true, reason="explanation of what was accomplished") for successful completion
- finish_task(success=false, reason="explanation of what went wrong") if the task could not be completed

This tool call signals to the system that no further steps are needed.""",
            model = "claude-sonnet-4-20250514",
        )
        
        response_text = ""
        is_done = False
        
        # Process streaming response
        print(f"\n[Claude Agent Step {self._step_count}] Claude: ", end="", flush=True)
        stream = query(prompt=query_text, options=options)
        async with aclosing(stream) as s:
            async for message in s:
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ThinkingBlock):
                            print(block.thinking, end="", flush=True)
                        elif isinstance(block, TextBlock):
                            response_text += block.text
                            print(f"🤖 {block.text}", end="", flush=True)
                        elif isinstance(block, ToolUseBlock):
                            if block.name == "mcp__task-completion__finish_task":
                                is_done = True
                            print(f"\n🔧 [ToolUse] {block.name} input={block.input}", flush=True)
                        elif isinstance(block, ToolResultBlock):
                            status = "error" if block.is_error else "ok"
                            print(f"\n✅ [ToolResult:{status}] {block.content}", flush=True)
                elif isinstance(message, ResultMessage):
                    print(f"\n[Result] turns={message.num_turns} duration_ms={message.duration_ms}", flush=True)
                    break

        return response_text, is_done

    def step(self, goal: str) -> base_agent.AgentInteractionResult:
        """Perform a single step with Claude."""
        self._step_count += 1
        print(f"\n🚀 [STEP START] Step {self._step_count} beginning", flush=True)
        
        # Get current state
        state = self.get_post_transition_state()
        
        # Create query with goal and state information
        query = f"""Goal: {goal}

Current step: {self._step_count}
Please analyze the current Android screen state and take the next appropriate action to accomplish the goal. If you need to see the screen, use available tools to take a screenshot first."""        
        claude_output, is_done = asyncio.run(self._process_claude_query(query))

        # Return result
        print(f"\n🏁 [STEP END] Step {self._step_count} completed. Done: {is_done}", flush=True)
        
        return base_agent.AgentInteractionResult(
            done=is_done,
            data={
                'agent_output': claude_output,
                'step_count': self._step_count,
                'goal': goal,
            }
        )

    def reset(self, go_home: bool = False) -> None:
        """Reset the agent."""
        super().reset(go_home)
        self._step_count = 0