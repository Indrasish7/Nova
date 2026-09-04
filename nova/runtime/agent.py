"""
Agent Runtime Module.

Central orchestrator for Nova AI agent.
Manages the core conceptual loop with Semantic-First execution hierarchy and Vision fallback:
User Request -> Model Provider -> Semantic UIA Resolution / Tool Selection -> Schema Validation ->
Permission Engine Evaluation -> Confirmation -> Execution -> Verification -> Structured Result -> Agent -> Final Response.
"""

import time
from typing import Callable, Optional, List, Dict, Any
from pydantic import BaseModel, ValidationError

from nova.providers.base import ModelProvider, ModelCapability, ChatMessage, ModelResponse, ToolCallRequest
from nova.tools.registry import ToolRegistry, create_default_registry
from nova.tools.base import BaseTool, ToolResult
from nova.permissions.engine import PermissionEngine
from nova.permissions.level import PermissionLevel, ActionContext
from nova.config import Settings
from nova.logger import log_agent_step, log_tool_decision, log_tool_execution
from nova.perception.screen import ScreenPerception
from nova.perception.verifier import ActionVerifier
from nova.perception.uia import UIAutomationResolver


# Type alias for user confirmation callback
ConfirmationCallback = Callable[[str, Dict[str, Any], PermissionLevel], bool]


class AgentStepResult(BaseModel):
    """Result of an agent step execution."""
    success: bool
    final_text: str
    tool_calls_executed: List[Dict[str, Any]] = []
    permission_denied: bool = False


class Agent:
    """
    Central Agent Runtime for Nova.
    
    Owns the model/tool reasoning loop and enforces permission checks.
    COMPLETELY PROVIDER-AGNOSTIC.
    """

    def __init__(
        self,
        provider: ModelProvider,
        registry: Optional[ToolRegistry] = None,
        permission_engine: Optional[PermissionEngine] = None,
        confirmation_callback: Optional[ConfirmationCallback] = None
    ):
        self.provider = provider
        self.registry = registry or create_default_registry()
        self.permission_engine = permission_engine or PermissionEngine()
        self.confirmation_callback = confirmation_callback
        self.history: List[ChatMessage] = []

    def set_confirmation_callback(self, callback: ConfirmationCallback) -> None:
        """Set or update the UI interactive confirmation callback."""
        self.confirmation_callback = callback

    def run(self, user_prompt: str, context: Optional[ActionContext] = None) -> AgentStepResult:
        """
        Execute full agent reasoning and action loop for a user request.
        """
        ctx = context or ActionContext()
        
        # Inject System Prompt at conversation start if missing
        if not self.history or not any(msg.role == "system" for msg in self.history):
            self.history.insert(0, ChatMessage(role="system", content=Settings.SYSTEM_PROMPT))

        self.history.append(ChatMessage(role="user", content=user_prompt))
        
        executed_tools: List[Dict[str, Any]] = []
        max_turns = Settings.NOVA_MAX_AGENT_STEPS
        turn_count = 0

        while turn_count < max_turns:
            turn_count += 1
            log_agent_step(turn_count, type(self.provider).__name__, Settings.MODEL_NAME, user_prompt)
            
            # Step 1: Model Provider generates completion / tool choice
            tool_defs = self.registry.get_definitions()
            model_response: ModelResponse = self.provider.generate(self.history, tool_defs)

            # If model returned text without tool calls, we are done
            if not model_response.tool_calls:
                final_text = model_response.text or "Completed request."
                self.history.append(ChatMessage(role="assistant", content=final_text))
                return AgentStepResult(
                    success=True,
                    final_text=final_text,
                    tool_calls_executed=executed_tools
                )

            # Add assistant's tool call message to history
            self.history.append(
                ChatMessage(
                    role="assistant",
                    content=model_response.text,
                    tool_calls=model_response.tool_calls
                )
            )

            # Step 2: Process tool calls (Treated as UNTRUSTED INPUT)
            for tool_call in model_response.tool_calls:
                # Tool Selection from Registry
                tool = self.registry.get_tool(tool_call.name)
                if not tool:
                    err_msg = f"Tool '{tool_call.name}' not found in registry."
                    self.history.append(
                        ChatMessage(role="tool", content=err_msg, tool_call_id=tool_call.id)
                    )
                    continue

                # Capability check: Vision perception requirement check
                if tool.name == "screen_observe" and not self.provider.supports_capability(ModelCapability.VISION):
                    err_msg = f"Model provider '{type(self.provider).__name__}' does not support vision capabilities."
                    self.history.append(
                        ChatMessage(role="tool", content=err_msg, tool_call_id=tool_call.id)
                    )
                    return AgentStepResult(
                        success=False,
                        final_text=err_msg,
                        tool_calls_executed=executed_tools
                    )

                # Tool Schema Validation via Pydantic
                try:
                    validated_args = tool.args_model(**tool_call.arguments)
                except ValidationError as val_err:
                    err_msg = f"Invalid tool arguments for '{tool.name}': {str(val_err)}"
                    self.history.append(
                        ChatMessage(role="tool", content=err_msg, tool_call_id=tool_call.id)
                    )
                    continue

                # Pre-resolution for semantic_click tool to extract UIA element metadata
                uia_element = None
                if tool.name == "semantic_click":
                    target_name = getattr(validated_args, "target_name", "")
                    control_type = getattr(validated_args, "control_type", None)
                    app_context = getattr(validated_args, "application_context", None)
                    res = UIAutomationResolver().resolve_element(
                        target_name,
                        control_type,
                        application_context=app_context
                    )
                    if res.success:
                        uia_element = res.element

                # Permission Engine Evaluation (inspects tool + arguments + UIA element + context)
                perm_level = self.permission_engine.evaluate(tool, validated_args, ctx, uia_element=uia_element)

                if perm_level == PermissionLevel.BLOCKED:
                    blocked_msg = f"Action '{tool.name}' was BLOCKED for security reasons or invalid parameters."
                    self.history.append(
                        ChatMessage(role="tool", content=blocked_msg, tool_call_id=tool_call.id)
                    )
                    return AgentStepResult(
                        success=False,
                        final_text=blocked_msg,
                        tool_calls_executed=executed_tools,
                        permission_denied=True
                    )

                # User Confirmation check if required
                approved = True
                if perm_level in [PermissionLevel.REQUIRES_CONFIRMATION, PermissionLevel.DANGEROUS]:
                    approved = False
                    if self.confirmation_callback:
                        approved = self.confirmation_callback(
                            tool.name,
                            tool_call.arguments,
                            perm_level
                        )
                    
                    log_tool_decision(tool.name, perm_level.value, approved)

                    if not approved:
                        rejection_msg = f"Action '{tool.name}' denied by user confirmation ({perm_level.value})."
                        self.history.append(
                            ChatMessage(role="tool", content=rejection_msg, tool_call_id=tool_call.id)
                        )
                        return AgentStepResult(
                            success=False,
                            final_text=f"Action '{tool.name}' was cancelled because user confirmation was declined.",
                            tool_calls_executed=executed_tools,
                            permission_denied=True
                        )
                else:
                    log_tool_decision(tool.name, perm_level.value, approved=True)

                # Pre-action observation capture
                pre_obs = None
                if tool.name in ["mouse_click", "mouse_double_click", "mouse_scroll", "semantic_click"]:
                    try:
                        pre_obs = ScreenPerception().capture_observation(reason=f"pre_{tool.name}")
                    except Exception:
                        pass

                # Tool Execution (Tools MUST NOT call LLM directly)
                start_time = time.time()
                tool_result: ToolResult = tool.execute(validated_args, ctx)
                latency_ms = (time.time() - start_time) * 1000.0

                # Post-action verification
                verification_result = None
                if tool_result.success:
                    if tool.name == "mouse_move":
                        actual_cursor = tool_result.metadata.get("actual_cursor", (0, 0))
                        target_x = getattr(validated_args, "x", 0)
                        target_y = getattr(validated_args, "y", 0)
                        verification_result = ActionVerifier.verify_mouse_move(target_x, target_y, tuple(actual_cursor))
                    elif tool.name == "semantic_click":
                        post_obs = None
                        try:
                            post_obs = ScreenPerception().capture_observation(reason="post_semantic_click")
                        except Exception:
                            pass
                        target_name = getattr(validated_args, "target_name", "")
                        via_pattern = tool_result.metadata.get("via_uia_pattern", False)
                        verification_result = ActionVerifier.verify_semantic_click(
                            target_name,
                            via_pattern,
                            pre_obs.model_dump() if pre_obs else None,
                            post_obs.model_dump() if post_obs else None,
                            pre_meta=uia_element.model_dump() if uia_element else None,
                            post_meta=tool_result.metadata.get("element")
                        )
                    elif tool.name in ["mouse_click", "mouse_double_click", "mouse_scroll"]:
                        post_obs = None
                        try:
                            post_obs = ScreenPerception().capture_observation(reason=f"post_{tool.name}")
                        except Exception:
                            pass
                        target_x = getattr(validated_args, "x", 0)
                        target_y = getattr(validated_args, "y", 0)
                        verification_result = ActionVerifier.verify_mouse_click(
                            target_x,
                            target_y,
                            pre_obs.model_dump() if pre_obs else None,
                            post_obs.model_dump() if post_obs else None
                        )

                if verification_result:
                    tool_result.metadata["verification"] = verification_result.model_dump()

                log_tool_execution(tool.name, tool_result.success, latency_ms, tool_result.error)

                executed_tools.append({
                    "tool": tool.name,
                    "arguments": tool_call.arguments,
                    "success": tool_result.success,
                    "output": tool_result.output,
                    "error": tool_result.error,
                    "metadata": tool_result.metadata
                })

                result_content = (
                    str(tool_result.output) if tool_result.success
                    else f"Error: {tool_result.error}"
                )
                
                if verification_result:
                    result_content += f" | Verification: {verification_result.reason}"

                img_path = tool_result.metadata.get("image_path") if tool_result.success else None

                self.history.append(
                    ChatMessage(
                        role="tool",
                        content=result_content,
                        tool_call_id=tool_call.id,
                        image_path=img_path
                    )
                )

        return AgentStepResult(
            success=False,
            final_text=f"Agent reached maximum execution step limit ({max_turns}).",
            tool_calls_executed=executed_tools
        )
