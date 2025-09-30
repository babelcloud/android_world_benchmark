"""Simple Claude Code agent for Android World."""

import asyncio
from typing import Any, Dict

from android_world.agents import base_agent
from android_world.env import interface
from android_world.env import json_action

from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions, HookMatcher,
    AssistantMessage, ResultMessage,
    TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock
)
from claude_agent_sdk.types import HookJSONOutput
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
        self._current_box_id = "235bed4d-f606-4335-8cbc-252115048d01"  # Track current Android box ID
        self._client: ClaudeSDKClient | None = None

    def _count_gbox_images_in_file(self, transcript_path: str) -> int:
        """Count the number of GBox images currently in the JSONL file."""
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            gbox_image_count = 0
            for line in lines:
                try:
                    line_data = json.loads(line.strip())
                    if not isinstance(line_data, dict):
                        continue

                    # Check if this line contains a GBox tool result with image
                    has_gbox_image = False

                    # Check toolUseResult[*] (top level)
                    try:
                        if line_data.get("toolUseResult"):
                            for item in line_data["toolUseResult"]:
                                if item.get("type") == "image":
                                    has_gbox_image = True
                                    break
                    except (KeyError, TypeError, AttributeError):
                        pass

                    if has_gbox_image:
                        gbox_image_count += 1

                except json.JSONDecodeError:
                    continue

            return gbox_image_count
        except (FileNotFoundError, IOError):
            return 0

    async def _screenshot_hook(self, data: Dict[str, Any], session_id: str | None, context: Any) -> HookJSONOutput:
        """Hook that runs after GBox tool completes with sliding window image replacement."""
        print(f"\n🔧 [Hook] Received data type: {type(data)}, session_id: {session_id}", flush=True)
        transcript_path = data.get('transcript_path')
        tool_name = data.get('tool_name')

        print(f"   🔧 Tool: {tool_name}, Transcript: {transcript_path}", flush=True)
        if not transcript_path:
            return HookJSONOutput()

        # Count actual GBox images in the JSONL file instead of using in-memory counter
        current_count = self._count_gbox_images_in_file(transcript_path)
        print(f"   📊 Total GBox images in file: {current_count}", flush=True)

        # Small placeholder image base64
        PLACEHOLDER_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAAL4AAAANAQAAAAA/UenrAAAAvUlEQVR42mP8z4AV/GViwAFIl2A4xMfEpMDwv42hgaGDo0O+ScaCQUmxicGGSZFsQirLp4Z1k87bnHac5eCu9MufqcjdJoGJgyGOocOB4UbClwt/K1gUGBgaSx4wMFxgYLr2gonhwQGGHf96DHw6GBh+/UvgUWBgMFjAwiGxgIFhAcMCve0vfjEwMPC8qK9i+N/wooLl/7sJD69q/Pffe5/B6pPzZvY738xv9j36t4GRgM8PQvkfHWAyOHUAALWRQwZjUuFKAAAAAElFTkSuQmCC"

        # If we have >= 10 tools, replace the image from (current_count - 10) position
        if current_count >= 10:
            target_position = current_count - 10  # 0-indexed position to replace
            print(f"   🎯 Replacing image at position {target_position} (sliding window)", flush=True)

            # Read and process JSONL file
            with open(transcript_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Find the GBox tool call at target_position and replace its image
            gbox_tool_index = -1
            modified = False

            for i, line in enumerate(lines):
                try:
                    line_data = json.loads(line.strip())
                    if not isinstance(line_data, dict):
                        continue

                    # Check if this line contains a GBox tool result with image
                    has_gbox_image = False

                    #toolUseResult[*] (top level)
                    try:
                        if line_data.get("toolUseResult"):
                            for item in line_data["toolUseResult"]:
                                if item.get("type") == "image":
                                    has_gbox_image = True
                                    break
                    except (KeyError, TypeError, AttributeError):
                        pass

                    # If this line has a GBox image, increment our index
                    if has_gbox_image:
                        gbox_tool_index += 1

                        # If this is the target position, replace the image
                        if gbox_tool_index == target_position:
                            print(f"   🔄 Found target at line {i}, replacing image", flush=True)
                            line_modified = False

                            # Replace in Location 1
                            try:
                                if (line_data.get("message", {}).get("content") and
                                    len(line_data["message"]["content"]) > 0 and
                                    line_data["message"]["content"][0].get("type") == "tool_result"):

                                    tool_result_content = line_data["message"]["content"][0].get("content", [])
                                    for item in tool_result_content:
                                        if (item.get("type") == "image" and
                                            item.get("source", {}).get("data")):
                                            item["source"]["data"] = PLACEHOLDER_IMAGE
                                            line_modified = True
                            except (KeyError, TypeError, AttributeError):
                                pass

                            # Replace in Location 2
                            try:
                                if line_data.get("toolUseResult"):
                                    for item in line_data["toolUseResult"]:
                                        if (item.get("type") == "image" and
                                            item.get("source", {}).get("data")):
                                            item["source"]["data"] = PLACEHOLDER_IMAGE
                                            line_modified = True
                            except (KeyError, TypeError, AttributeError):
                                pass

                            if line_modified:
                                lines[i] = json.dumps(line_data, separators=(',', ':')) + '\n'
                                modified = True
                                print(f"   ✅ Replaced image at position {target_position}", flush=True)
                                break  # Found and replaced, exit loop

                except json.JSONDecodeError:
                    continue

            if modified:
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
        else:
            print(f"   ⏳ Keeping all images (count < 10)", flush=True)

        return HookJSONOutput()

    def _create_options(self) -> ClaudeAgentOptions:
        """Create ClaudeAgentOptions with hooks for memory management."""
        # Define PostToolUse hook for ALL GBox tools (they all return screenshots)
        gbox_hook_matcher = HookMatcher(
            matcher="mcp__gbox-android__.*",
            hooks=[self._screenshot_hook]
        )

        return ClaudeAgentOptions(
            setting_sources=["user", "project", "local"],
            allowed_tools=[
                "mcp__gbox-android__screenshot",
                "mcp__gbox-android__wait",
                "mcp__gbox-android__open_app",
                "mcp__gbox-android__close_app",
                "mcp__gbox-android__long_press",
                "mcp__gbox-android__press_button",
                "mcp__gbox-android__swipe",
                "mcp__gbox-android__tap",
                "mcp__gbox-android__type",
                "mcp__task-completion__answer_action",
                "mcp__task-completion__finish_task",
                "Read", "Write", "Bash",
            ],
            permission_mode="acceptEdits",
            system_prompt=f"""ANDROID WORLD BENCHMARK AGENT — RELENTLESS, VERIFY-THEN-REPORT MODE

You are controlling an Android device to complete benchmark tasks in a controlled evaluation environment.

Current box ID (if any): {self._current_box_id}

=== CORE CONTRACT ===
- EVERYTHING IS SOLVABLE with the tools you have. Assume the required control exists until you have truly exhausted discovery.
- FOLLOW VERBATIM: Use the exact values and labels provided in the goal. Never substitute "close enough" labels or accept defaults.
- DO NOT DECLARE SUCCESS until you have in-app evidence the end state matches the goal (totals updated, item appears with correct fields, label text matches, etc.).

=== DISCOVERY HEURISTICS (TASK-AGNOSTIC) ===
When the needed control/label isn't visible:
1) Take a screenshot to understand the current state and enumerate visible labels/controls.
2) Explore systematically:
   • Vertical exploration: open drawers/menus, scroll lists, expand sections.
   • Horizontal exploration: treat **chip/button rows and carousels as horizontally scrollable**; perform swipes of short→medium→long distances in BOTH directions, anchored on the control row (center vs edges).
   • Tabs/filters/overflow (…) menus: open and inspect them.
3) After any gesture or navigation, **take another screenshot** to confirm the new state before deciding the next action.
4) If a tool call is denied or a gesture fails (e.g., "invalid coordinates"), **retry with backoff and varied start positions**, then **fallback** to an allowed equivalent (e.g., swipe instead of scroll) rather than stopping.

=== INPUT DISCIPLINE ===
- **QUOTED VALUES**: If a value appears in quotes in the goal, type it EXACTLY.
- Numeric/text fields: enter values exactly; omit symbols if the field already shows the unit. After typing, re-check the field visually to confirm formatting took.
- Selection chips/radios/categories: do **not** accept defaults. Select the label that exactly matches the requested label. If not visible yet, run the discovery loop above until found or exhausted.

=== PERSISTENCE BUDGET ===
For each missing control/label perform at least **two full discovery passes**:
- Pass A: short→medium→long left/right swipes on the suspected row + necessary vertical checks.
- Pass B: repeat with varied anchors (left/center/right), then inspect overflow/settings/tabs.
Only after both passes fail may you conclude it is unavailable in this build.

=== VERIFICATION & SELF-CHECK ===
- In-app confirmation is mandatory: check the relevant screen section (e.g., a "Recent" list, totals, selected tags) to confirm the exact entry/label/amount is present.
- If any harness/post-state indicator disagrees with what you see, treat it as a fix-needed signal: continue troubleshooting rather than finishing.

=== ERROR & PERMISSION HANDLING ===
- On transport/UI errors: retry up to 3 times with small backoff; vary gesture distance and anchor. If a permission/tool isn't available, switch to a permitted alternative.
- Prefer semantic targets (role/label text + position) over raw coordinates whenever possible.

=== TOOL PRECISION ===
When tapping/typing, specify **role + label + position** where possible:
  Good: tap("chip button labeled 'Social' in the category row")
  Good: tap("SAVE button at bottom of form with white text on blue background")

=== APP DISCOVERY ===
ALWAYS check for apps thoroughly:
1. Take screenshot to see current state
2. If target app not visible, swipe up to open app drawer
3. Look through ALL available apps before concluding an app doesn't exist

=== TASK COMPLETION ===
For questions that require a specific answer (like quantities, measurements, or facts):
1. First call: answer_action(text="the exact answer requested")
2. Then call: finish_task(success=true)

For tasks without specific answers:
- Only call finish_task(success=true) **after** you verify on-screen that all required fields/labels/amounts are present and correct.
- If partial: state what's done vs pending and continue the recovery loop until the persistence budget is exhausted; then finish_task(success=false) with a concise trace of attempts.

Remember: do not improvise or accept defaults; discover, verify, then report.""",
            model="claude-sonnet-4-5-20250929",
            hooks={
                "PostToolUse": [gbox_hook_matcher]
            }
        )

    async def _process_claude_query(self, query_text: str, use_sonnet_4: bool = False) -> tuple[str, bool, bool]:
        """Process a query with Claude using ClaudeSDKClient with hooks.

        Args:
            query_text: The query to send to Claude
            use_sonnet_4: If True, use Sonnet 4 instead of Sonnet 4.5

        Returns:
            tuple: (response_text, is_done, has_error)
        """
        response_text = ""
        is_done = False
        has_error = False

        # Create client with hooks
        options = self._create_options()

        # Override model if using fallback
        if use_sonnet_4:
            options.model = "claude-sonnet-4-20250514"
            print(f"\n[Claude Agent Step {self._step_count}] Starting query with FALLBACK model: {options.model}...", flush=True)
        else:
            print(f"\n[Claude Agent Step {self._step_count}] Starting query with model: {options.model}...", flush=True)

        try:
            async with ClaudeSDKClient(options) as client:
                await client.query(query_text)

                async for message in client.receive_response():
                    # Check for Usage Policy violation via isApiErrorMessage flag
                    if hasattr(message, 'isApiErrorMessage') and message.isApiErrorMessage:
                        print(f"\n🚨 [USAGE POLICY VIOLATION] Detected - triggering fallback", flush=True)
                        has_error = True
                        is_done = True
                        # Extract error message
                        if hasattr(message, 'message') and hasattr(message.message, 'content'):
                            for block in message.message.content:
                                if isinstance(block, dict) and block.get('type') == 'text':
                                    response_text = block.get('text', '')
                                    print(f"   {response_text[:200]}", flush=True)
                        break  # Exit loop immediately - no more messages coming

                    # Process any message that has content blocks
                    if hasattr(message, 'content') and isinstance(message.content, list):
                        for block in message.content:
                            if isinstance(block, ThinkingBlock):
                                print(block.thinking, end="", flush=True)
                            elif isinstance(block, TextBlock):
                                response_text += block.text
                                print(f"🤖 {block.text}", end="", flush=True)

                                # Also check TextBlock for API Error message
                                if "API Error: Claude Code is unable to respond" in block.text or "appears to violate our Usage Policy" in block.text:
                                    print(f"\n🚨 [USAGE POLICY IN TEXT] Detected - triggering fallback", flush=True)
                                    has_error = True
                                    is_done = True

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
        except Exception as e:
            error_msg = str(e)
            print(f"\n❌ [ERROR] Exception during Claude query: {error_msg}", flush=True)
            # Re-raise - we don't handle exceptions here, only isApiErrorMessage
            raise

        return response_text, is_done, has_error

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
        claude_output, is_done, has_error = asyncio.run(self._process_claude_query(query))

        # If Usage Policy violation detected, retry with Sonnet 4
        if has_error:
            print(f"\n🔄 [FALLBACK] Retrying with Sonnet 4...", flush=True)
            # Temporarily switch to Sonnet 4 for this query
            claude_output, is_done, has_error = asyncio.run(self._process_claude_query(query, use_sonnet_4=True))

        # Return result
        print(f"\n🏁 [STEP END] Step {self._step_count} completed. Done: {is_done}, Error: {has_error}", flush=True)

        return base_agent.AgentInteractionResult(
            done=is_done,
            data={
                'agent_output': claude_output,
                'step_count': self._step_count,
                'goal': goal,
                'error': has_error,
            }
        )

    def reset(self, go_home: bool = False) -> None:
        """Reset the agent."""
        super().reset(go_home)
        self._step_count = 0