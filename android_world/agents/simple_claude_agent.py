"""Simple Claude Code agent for Android World."""

import asyncio
from typing import Any, Dict

from android_world.agents import base_agent
from android_world.env import interface
from android_world.env import json_action

from claude_code_sdk import (
    ClaudeSDKClient, ClaudeCodeOptions, HookMatcher,
    AssistantMessage, ResultMessage,
    TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock
)
from claude_code_sdk.types import HookJSONOutput
import json
import os


class SimpleClaude(base_agent.EnvironmentInteractingAgent):
    """Simple agent using ClaudeSDKClient with hooks for memory management."""

    def __init__(
        self,
        env: interface.AsyncEnv,
        name: str = 'simple_claude',
        transition_pause: float | None = 1.0,
    ):
        super().__init__(env, name, transition_pause)
        self._step_count = 0
        self._current_box_id = "50ad1fa3-3295-4095-b4ec-68600d47d6c6"  # Track current Android box ID
        self._client: ClaudeSDKClient | None = None

    async def _screenshot_hook(self, data: Dict[str, Any], session_id: str | None, context: Any) -> HookJSONOutput:
        """Hook that runs after GBox tool completes to replace large images with placeholders."""
        # Debug: Print what we're receiving
        print(f"\n🔧 [Hook] Received data type: {type(data)}, session_id: {session_id}", flush=True)
        transcript_path = data.get('transcript_path')
        tool_name = data.get('tool_name')

        print(f"   🔧 Tool: {tool_name}, Transcript: {transcript_path}", flush=True)
        if not transcript_path:
            return HookJSONOutput()

        # Small placeholder image base64
        PLACEHOLDER_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAAL4AAAANAQAAAAA/UenrAAAAvUlEQVR42mP8z4AV/GViwAFIl2A4xMfEpMDwv42hgaGDo0O+ScaCQUmxicGGSVFsQirLp4Z1k87bnHac5eCu9MufqcjdJoGJgyGOocOB4UbClwt/K1gUGBgaSx4wMFxgYLr2gonhwQGGHf96DHw6GBh+/UvgUWBgMFjAwiGxgIFhAcMCve0vfjEwMPC8qK9i+N/wooLl/7sJD69q/Pffe5/B6pPzZvY738xv9j36t4GRgM8PQvkfHWAyOHUAALWRQwZjUuFKAAAAAElFTkSuQmCC"

        # Read and process JSONL file
        with open(transcript_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        modified = False
        for i, line in enumerate(lines):
            try:
                line_data = json.loads(line.strip())

                # Ensure line_data is a dictionary
                if not isinstance(line_data, dict):
                    continue

                line_modified = False

                # Location 1: message.content[0].content[*] (tool result)
                try:
                    if (line_data.get("message", {}).get("content") and
                        len(line_data["message"]["content"]) > 0 and
                        line_data["message"]["content"][0].get("type") == "tool_result"):

                        tool_result_content = line_data["message"]["content"][0].get("content", [])
                        for item in tool_result_content:
                            if (item.get("type") == "image" and
                                item.get("source", {}).get("data") and
                                len(item["source"]["data"]) > 1000):
                                item["source"]["data"] = PLACEHOLDER_IMAGE
                                line_modified = True
                except (KeyError, TypeError, AttributeError):
                    pass  # Skip if structure is unexpected

                # Location 2: toolUseResult[*] (top level)
                try:
                    if line_data.get("toolUseResult"):
                        for item in line_data["toolUseResult"]:
                            if (item.get("type") == "image" and
                                item.get("source", {}).get("data") and
                                len(item["source"]["data"]) > 1000):
                                item["source"]["data"] = PLACEHOLDER_IMAGE
                                line_modified = True
                except (KeyError, TypeError, AttributeError):
                    pass  # Skip if structure is unexpected

                if line_modified:
                    lines[i] = json.dumps(line_data, separators=(',', ':')) + '\n'
                    modified = True

            except json.JSONDecodeError:
                continue

        if modified:
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            print(f"   ✅ Memory optimization completed", flush=True)

        return HookJSONOutput()

    def _create_options(self) -> ClaudeCodeOptions:
        """Create ClaudeCodeOptions with hooks for memory management."""
        # Define PostToolUse hook for ALL GBox tools (they all return screenshots)
        gbox_hook_matcher = HookMatcher(
            matcher="mcp__gbox-android__.*",
            hooks=[self._screenshot_hook]
        )

        return ClaudeCodeOptions(
            allowed_tools=[
                "mcp__gbox-android__screenshot",
                "mcp__gbox-android__swipe",
                "mcp__gbox-android__tap",
                "mcp__gbox-android__type",
                "mcp__gbox-android__scroll",
                "mcp__task-completion__answer_action",
                "mcp__task-completion__finish_task",
                "Read", "Write", "Bash",
            ],
            permission_mode="acceptEdits",
            system_prompt=f"""You are controlling an Android device to accomplish specific goals.

You have access to tools that can interact with the Android device.

Current box ID (if any): {self._current_box_id}

Always start by taking a screenshot to see the current state, then proceed with appropriate actions to accomplish the given goal.

Be methodical and take one action at a time. Explain your reasoning for each action.

IMPORTANT: When you have successfully completed the task:

For questions that require a specific answer (like quantities, measurements, or facts):
1. First call: answer_action(text="the exact answer requested")
2. Then call: finish_task(success=true)

For tasks without specific answers:
- finish_task(success=true) for successful completion
- finish_task(success=false) if the task could not be completed

The finish_task tool signals to the system that no further steps are needed.""",
            model="claude-sonnet-4-20250514",
            hooks={
                "PostToolUse": [gbox_hook_matcher]
            }
        )

    async def _process_claude_query(self, query_text: str) -> tuple[str, bool]:
        """Process a query with Claude using ClaudeSDKClient with hooks."""
        response_text = ""
        is_done = False

        # Create client with hooks
        options = self._create_options()

        print(f"\n[Claude Agent Step {self._step_count}] Starting query...", flush=True)

        async with ClaudeSDKClient(options) as client:
            await client.query(query_text)

            async for message in client.receive_response():
                # Process any message that has content blocks
                if hasattr(message, 'content') and isinstance(message.content, list):
                    for block in message.content:
                        if isinstance(block, ThinkingBlock):
                            print(block.thinking, end="", flush=True)
                        elif isinstance(block, TextBlock):
                            response_text += block.text
                            print(f"🤖 {block.text}", end="", flush=True)
                        elif isinstance(block, ToolUseBlock):
                            if block.name == "mcp__task-completion__finish_task":
                                is_done = True
                            elif block.name == "mcp__task-completion__answer_action":
                                # Extract answer text from tool input and create JSONAction
                                answer_text = block.input.get('text', '') if hasattr(block, 'input') and block.input else ''
                                if answer_text:
                                    answer_action = json_action.JSONAction(
                                        action_type=json_action.ANSWER,
                                        text=answer_text
                                    )
                                    self.env.execute_action(answer_action)
                                    print(f"\n🔧 [ANSWER] Executed answer action: {answer_text}", flush=True)
                            print(f"\n🔧 [ToolUse] {block.name} input={block.input}", flush=True)
                        elif isinstance(block, ToolResultBlock):
                            status = "error" if block.is_error else "ok"
                            content_str = str(block.content)
                            if "data:image" not in content_str and len(content_str) < 500:
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