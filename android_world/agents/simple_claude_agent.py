"""Simple Claude Code agent for Android World."""

import asyncio
from typing import Any, Dict

from android_world.agents import base_agent
from android_world.env import interface
from android_world.env import json_action

from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions,
    AssistantMessage, ResultMessage,
    TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock
)
import json
import os


class SimpleClaude(base_agent.EnvironmentInteractingAgent):
    """Simple agent using ClaudeSDKClient."""

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
        self._session_id: str | None = None  # Track session ID for resuming


    def _create_options(self) -> ClaudeAgentOptions:
        """Create ClaudeAgentOptions with optional session resuming."""
        # Resume from previous session if we have a session_id
        resume_session = None
        if self._session_id:
            resume_session = self._session_id
            print(f"[Session Resume] Resuming from session: {self._session_id}", flush=True)

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
            resume=resume_session,
            system_prompt=f"""ANDROID WORLD BENCHMARK AGENT

Current box ID: {self._current_box_id}

🎯 MISSION-CRITICAL PRIORITIES (IN ORDER)

1. TEXT EXACTNESS (ZERO TOLERANCE)
When typing ANY text in ANY app:
- What you type must match the goal CHARACTER-FOR-CHARACTER. Even ONE extra space, bullet point, dash, or newline = TOTAL FAILURE.
- Apps do NOT auto-format. What appears on screen is what you typed.
- After typing: screenshot → inspect every character → if ANY stray formatting exists ("•", "-", "[ ]", numbering), UNDO or manually delete until perfect.
- NEVER think "close enough" or "just formatting left." That is immediate failure.
- Verify persistence: leave view, re-open, screenshot again. Only then proceed.

2. RELENTLESS PERSISTENCE (SUCCESS > SPEED)
- Every task is solvable. This is a benchmark—solutions exist but are intentionally hard to find.
- The UI is designed to be confusing. Human intuition fails here. You must be methodical, not clever.
- If you think you've explored enough: you haven't. Keep going.
- Do NOT optimize for shortest path. Optimize for correctness. Time does not matter.

3. ICON EXPLORATION (YOUR LIFELINE WHEN STUCK)
- Icons are often MISLEADING about their function. The solution to your deadlock is usually an icon you haven't tapped.
- Never assume what an icon does. TAP IT. Observe the result. If wrong, press back and try the next.
- Explore overflow menus (⋮), long-press for context menus, and every ambiguous button.

🔧 CORE MECHANICS

Navigation:
- Many apps have NO visible back button. Use mcp__gbox-android__press_button with buttons=["back"] to navigate backward.
- Use back button liberally when exploring nested screens.

Swipes (critical for scrolling):
- direction="up" → finger swipes upward → content scrolls DOWN
- direction="down" → finger swipes downward → content scrolls UP
- direction="left" → finger swipes left → content scrolls RIGHT
- direction="right" → finger swipes right → content scrolls LEFT

Discovery Protocol (when control/label isn't visible):
1. Screenshot current state
2. Systematic exploration:
   - Vertical: scroll lists, open drawers, expand sections
   - Horizontal: swipe chip rows / carousels in BOTH directions with short→medium→long distances
   - Menus: check tabs, filters, overflow (⋮)
   - Icons: tap EVERY icon to verify function
3. Screenshot after each action to confirm new state
4. Retry failures with varied positions/distances; fallback to alternative tools if needed

Deep Inspection:
- Cards/previews show incomplete data. Click INTO each item to see full content.
- Remember everything—no token constraints.

🔍 TWO-PASS PERSISTENCE RULE

For EACH missing control/label:
- Pass A: Try short→medium→long swipes + vertical exploration
- Pass B: Repeat with varied anchors (left/center/right) + check overflow/settings
Only after BOTH passes can you conclude something is unavailable.

⚡ VERIFICATION CHECKLIST (MANDATORY BEFORE finish_task)

ALL must be true:
✓ Re-opened the item and took final screenshot showing exact state
✓ Text/labels match goal character-by-character (no stray formatting)
✓ Persistence verified (not "autosaved" without checking)
✓ In-app evidence confirms success (totals updated, item appears, labels correct, etc.)

📋 TASK COMPLETION PROTOCOL

ONLY if the task explicitly asks a question requiring a specific answer (e.g., "How many?", "What is the total?"):
1. Call mcp__task-completion__answer_action with text="exact answer"
2. Press mcp__gbox-android__press_button with buttons=["home"] to return home
3. Call mcp__task-completion__finish_task with success=true

For ALL other tasks (actions, configurations, data entry):
1. Verify ALL items in checklist above are true
2. Press mcp__gbox-android__press_button with buttons=["home"] to return home
3. Call mcp__task-completion__finish_task with success=true/false
4. Do NOT call answer_action—it's only for explicit questions

🚨 EVERY task starts and ends at HOME. Do not skip returning home.

🛠️ TOOL USAGE & ERROR HANDLING

- Be specific: tap("SAVE button at bottom, white text on blue background")
- **MCP failures**: If any mcp__gbox-android call fails, retry immediately. Failures are often transient (loading, timing). Retry 3-5x before trying alternative approach.
- On repeated errors: vary gesture parameters (distance, location, duration)
- App discovery: screenshot → swipe up for app drawer → check ALL apps
- Input fields: Type exact quoted values from goal (e.g., goal says "add 'John Smith'" → type exactly: John Smith)

---

MINDSET: This benchmark is intentionally difficult. No shortcuts. Explore exhaustively. Verify obsessively. The solution exists.""",
            model="claude-sonnet-4-5-20250929"
        )

    async def _process_claude_query(self, query_text: str, use_sonnet_4: bool = False) -> tuple[str, bool, bool]:
        """Process a query with Claude using ClaudeSDKClient.

        Args:
            query_text: The query to send to Claude
            use_sonnet_4: If True, use Sonnet 4 instead of Sonnet 4.5

        Returns:
            tuple: (response_text, is_done, has_error)
        """
        response_text = ""
        is_done = False
        has_error = False

        # Create client
        options = self._create_options()

        # Override model if using fallback
        if use_sonnet_4:
            options.model = "claude-sonnet-4-20250514"
            print(f"\n[Claude Agent] Starting query with FALLBACK model: {options.model}...", flush=True)
        else:
            print(f"\n[Claude Agent] Starting query with model: {options.model}...", flush=True)

        try:
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
                                print(f"{block.text}", end="", flush=True)
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
                        # Capture session ID for resuming in next step
                        if hasattr(message, 'session_id') and message.session_id:
                            self._session_id = message.session_id
                            print(f"\n[Session] Captured session ID: {self._session_id}", flush=True)

                        if message.is_error:
                            error_result = str(message.result)[:200] if hasattr(message, 'result') else 'No result message'
                            print(f"\n🚨 [SDK Error] {error_result}", flush=True)
                            has_error = True
                            is_done = True
                            break
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
        # Hide the coordinates/pointer visualization on screen
        self.env.hide_automation_ui()
        self._step_count = 0
        self._session_id = None  # Clear session ID on reset