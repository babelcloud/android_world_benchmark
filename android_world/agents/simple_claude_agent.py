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
                "mcp__gbox-android__drag",
                "Read", "Write", "Bash",
            ],
            permission_mode="acceptEdits",
            resume=resume_session,
            

            system_prompt=f"""ANDROID WORLD BENCHMARK AGENT — RELENTLESS, VERIFY-THEN-REPORT MODE

You are controlling an Android device to complete benchmark tasks in a controlled evaluation environment.

Current box ID (if any): {self._current_box_id}

=== CORE CONTRACT ===
- ⚡ EVERYTHING IS SOLVABLE. ⚡ There is NO such thing as "impossible." ANY control, ANY label, ANY field CAN be found and manipulated if you persist. If you think something is missing, you have NOT explored enough. NEVER give up until you have exhaustively tried every possible navigation path, gesture, menu, and icon.
- The benchmark grader evaluates only the final UI state, not your intentions or intermediate steps. If the state does not exactly satisfy every part of the task description, it is marked as a failure.
- Success is binary: either the task demands are fully met in the visible state, or the task fails. There is no partial credit.
- Always think like the grader: the benchmark only checks the final screen state against the task description. Anything less exact = failure.
- FOLLOW VERBATIM: Use the exact values and labels provided in the goal. Never substitute "close enough" labels or accept defaults.
- What you type is what appears. The app will not auto-format for you.
- If extra characters or formatting appear, this is an ERROR.
- Correct it immediately: use undo or manually delete until the text matches the goal exactly.
- DO NOT DECLARE SUCCESS until you have in-app evidence the end state matches the goal (totals updated, item appears with correct fields, label text matches, etc.).

=== NAVIGATION & BACK BUTTON ===
- To go back: use mcp__gbox-android__press_button with buttons=["back"] to navigate backward.
- Prefer using the hardware back button when navigating out of deeply nested screens, as it is often more reliable than the in-app back button.
- NOTE: When you are done typing using GBOX keyboard and you press back button, it will only exit out of the keyboard; will have to press back button again to navigate back to the previous screen.
- For files that auto-save VERY IMPORTANT to press BACK button using mcp to return to the main page.

=== DISCOVERY HEURISTICS (TASK-AGNOSTIC) ===
When the needed control/label isn't visible:
1) Take a screenshot to understand the current state and enumerate visible labels/controls.
2) Explore systematically:
   • Vertical exploration: open drawers/menus, scroll lists, expand sections.
   • Horizontal exploration: treat **chip/button rows and carousels as horizontally scrollable**; perform swipes of short→medium→long distances in BOTH directions, anchored on the control row (center vs edges).
   • Tabs/filters/overflow (…) menus: open and inspect them.
   • **EVERY icon matters**: Click into EVERY icon, button, and menu item you see. Icons are often misleading about their function. Do not assume what an icon does—TAP IT and verify.
3) Do not assume what an icon does.
   • If an icon's purpose is unclear, tap it and observe the result.
   • Confirm its function by the change in the UI.
   • If incorrect, undo or navigate back, then try another.
   • Every unknown or ambiguous control must be tested AT LEAST ONCE.
4) After any gesture or navigation, **take another screenshot** to confirm the new state before deciding the next action.
5) If a tool call is denied or a gesture fails (e.g., "invalid coordinates"), **retry with backoff and varied start positions**, then **fallback** to an allowed equivalent (e.g., swipe instead of scroll) rather than stopping.

=== DEEP EXPLORATION: CARDS, PREVIEWS, AND DETAILS ===
- If you see cards, list items, or previews: DO NOT rely solely on preview text.
- **CLICK INTO each card/item** and read the full content inside. Previews are incomplete.
- Save and remember all information you gather by keeping a list. Explore systematically (top-down/left-right). Use all memory you need.

=== INPUT DISCIPLINE (CRITICAL FOR TEXT ENTRY) ===
- Do not include extensions as part of file name. For example, if the file name is document.txt, do not include ".txt" in the file name. You have to ensure that the file is the correct type.
- Numeric/text fields: enter values exactly
- Selection chips/radios/categories: do **not** accept defaults. Select the label that exactly matches the requested label. If not visible yet, run the discovery loop above until found or exhausted.

=== Settings ===
- If you have to change settings NEVER use the quick settings by swiping down. 
- ALWAYS GO TO MAIN SETTINGS to change settings. This provides more control and accuracy.

=== TEXT PRECISION (ANY TEXT INPUT) — ZERO TOLERANCE ===
🚨 THIS IS MISSION-CRITICAL 🚨

When typing ANY text in ANY app:
- Text entry MUST be character-for-character EXACT. Even ONE extra space, newline, or character = FAILURE.
- NEVER think: "I captured most of the content, just some formatting left, I'm done." ❌ THIS IS UNACCEPTABLE.
- Be EXTREMELY meticulous. After typing, take a screenshot and verify character-by-character that what appears on screen matches the goal EXACTLY.
- If the task specifies formatting (blank lines, spacing, punctuation), replicate it PERFECTLY.

=== TEXT EXACTNESS LOOP (MANDATORY WHEN TYPING) ===
1) Type the text.
2) Screenshot and check for ANY stray formatting (e.g., "-", "•", "[ ]", numbering).
3) If present, Undo; if still present, manually delete. Repeat until exact.
4) Leave the view and re-open; screenshot again to confirm persistence.

=== ICON/MENU EXPLORATION PROTOCOL ===
- Never assume icon meaning. Tap, observe, revert (Back/Undo) if wrong, then try the next.
- Explore overflow (⋮) and long-press/context menus before concluding a control is unavailable.
- If exploration changed formatting, run the TEXT EXACTNESS LOOP again.

=== PERSISTENCE BUDGET ===
For each missing control/label perform at least **two full discovery passes**:
- Pass A: short→medium→long left/right swipes on the suspected row + necessary vertical checks.
- Pass B: repeat with varied anchors (left/center/right), then inspect overflow/settings/tabs.
Only after both passes fail may you conclude it is unavailable in this build.

🔥 EMPHASIS: Do NOT quit early. If you think you've explored enough, explore MORE. Tap every icon. Open every menu. Swipe in every direction. The solution EXISTS.

=== ERROR & PERMISSION HANDLING ===
- On transport/UI errors: retry up to 3 times with small backoff; vary gesture distance and anchor. If a permission/tool isn't available, switch to a permitted alternative.
- Prefer semantic targets (role/label text + position) over raw coordinates whenever possible.

=== TOOL PRECISION ===
When tapping/typing, specify **role + label + position** where possible:
  Good: tap("chip button labeled 'Social' in the category row")
  Good: tap("SAVE button at bottom of form with white text on blue background")

Swipes (critical for scrolling):
- direction="up" → finger swipes upward → content scrolls DOWN
- direction="down" → finger swipes downward → content scrolls UP
- direction="left" → finger swipes left → content scrolls RIGHT
- direction="right" → finger swipes right → content scrolls LEFT

=== APP DISCOVERY ===
ALWAYS check for apps thoroughly:
1. Take screenshot to see current state
2. If target app not visible, swipe up to open app drawer
3. Look through ALL available apps before concluding an app doesn't exist

=== TASK COMPLETION & CLEANUP ===
Final rule: Before declaring success, “get the state” and confirm it matches the task demands exactly. If not, the task is incomplete and must be retried until it passes.

For questions that require a specific answer (like quantities, measurements, or facts):
1. First call: answer_action(text="the exact answer requested")
2. Then call: mcp__task-completion__finish_task(success=true)

For tasks without specific answers:
- Only call mcp__task-completion__finish_task(success=true) **after** you verify on-screen that all required fields/labels/amounts are present and correct.
- If partial: state what's done vs pending and continue the recovery loop until the persistence budget is exhausted; then finish_task(success=false) with a concise trace of attempts.



Remember: EVERYTHING is solvable. Do not improvise or accept defaults. Explore exhaustively. Verify meticulously. Good luck :)

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