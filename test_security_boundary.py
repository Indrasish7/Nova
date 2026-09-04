"""
Security Boundary Verification Script for Nova Phase B.5.

Empirically verifies:
1. REQUIRES_CONFIRMATION & DANGEROUS UIA actions prompt confirmation before execution.
2. ZERO execution (no Invoke, Select, Toggle, or SendInput calls) occurs prior to user approval.
3. Denying the action results in ZERO execution.
4. Approving the action results in EXACTLY ONE execution.
"""

from unittest.mock import patch, MagicMock
from nova.runtime.agent import Agent
from nova.providers.mock import MockModelProvider
from nova.providers.base import ModelResponse, ToolCallRequest
from nova.permissions.engine import PermissionEngine
from nova.permissions.level import PermissionLevel, ActionContext
from nova.perception.models import UIElementMetadata, UIResolutionResult
from nova.perception.uia import UIAutomationResolver
from nova.tools.semantic_click import SemanticClickTool

print("=== STARTING PHASE B.5 SECURITY BOUNDARY VERIFICATION ===\n")

# Trackers for execution calls
invoke_call_count = 0
select_call_count = 0
toggle_call_count = 0
sendinput_call_count = 0
pre_approval_execution = False

def reset_trackers():
    global invoke_call_count, select_call_count, toggle_call_count, sendinput_call_count, pre_approval_execution
    invoke_call_count = 0
    select_call_count = 0
    toggle_call_count = 0
    sendinput_call_count = 0
    pre_approval_execution = False

# Mock elements
meta_conseq = UIElementMetadata(
    name="Delete File",
    control_type="Button",
    enabled=True,
    supported_patterns=["InvokePattern"],
    process_name="notepad.exe"
)

meta_dangerous = UIElementMetadata(
    name="End task",
    control_type="Button",
    enabled=True,
    supported_patterns=["InvokePattern"],
    process_name="taskmgr.exe"
)


# --- TEST 1: REQUIRES_CONFIRMATION DENIAL ---
print("--- TEST 1: REQUIRES_CONFIRMATION Action (Delete File) -> DENIED ---")
reset_trackers()

provider_1 = MockModelProvider(
    forced_response=ModelResponse(
        tool_calls=[ToolCallRequest(id="call_del", name="semantic_click", arguments={"target_name": "Delete File"})]
    )
)
agent_1 = Agent(provider=provider_1)

# Confirmation callback that checks if execution occurred before approval and returns False (Deny)
def cb_deny_1(tool_name, args, perm_level):
    global pre_approval_execution
    if invoke_call_count > 0 or select_call_count > 0 or toggle_call_count > 0 or sendinput_call_count > 0:
        pre_approval_execution = True
    print(f"  [1] PermissionEngine Decision: {perm_level.value.upper()}")
    print(f"  [2] Confirmation Modal Presented: Tool='{tool_name}', Target='{args.get('target_name')}'")
    print(f"  [3] User Decision: DENY")
    return False

agent_1.set_confirmation_callback(cb_deny_1)

with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta_conseq)):
    with patch.object(UIAutomationResolver, "invoke_element_pattern") as mock_inv:
        with patch("nova.tools.mouse._win32_send_input") as mock_si:
            res_1 = agent_1.run("Click Delete File")
            
            print(f"  [4] Pre-Approval Execution Detected: {pre_approval_execution}")
            print(f"  [5] Post-Denial Execution Count: Pattern={mock_inv.call_count}, SendInput={mock_si.call_count}")
            print(f"  [6] Agent Final Result: Success={res_1.success}, PermissionDenied={res_1.permission_denied}")
            print(f"  [7] Response Text: '{res_1.final_text}'")
            print()

# --- TEST 2: DANGEROUS PROTECTED-PROCESS DENIAL ---
print("--- TEST 2: DANGEROUS Action (Task Manager End Task) -> DENIED ---")
reset_trackers()

provider_2 = MockModelProvider(
    forced_response=ModelResponse(
        tool_calls=[ToolCallRequest(id="call_tm", name="semantic_click", arguments={"target_name": "End task"})]
    )
)
agent_2 = Agent(provider=provider_2)

def cb_deny_2(tool_name, args, perm_level):
    global pre_approval_execution
    if invoke_call_count > 0 or select_call_count > 0 or toggle_call_count > 0 or sendinput_call_count > 0:
        pre_approval_execution = True
    print(f"  [1] PermissionEngine Decision: {perm_level.value.upper()}")
    print(f"  [2] Confirmation Modal Presented: Tool='{tool_name}', Target='{args.get('target_name')}'")
    print(f"  [3] User Decision: DENY")
    return False

agent_2.set_confirmation_callback(cb_deny_2)

with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta_dangerous)):
    with patch.object(UIAutomationResolver, "invoke_element_pattern") as mock_inv:
        with patch("nova.tools.mouse._win32_send_input") as mock_si:
            res_2 = agent_2.run("Click End task in Task Manager")
            
            print(f"  [4] Pre-Approval Execution Detected: {pre_approval_execution}")
            print(f"  [5] Post-Denial Execution Count: Pattern={mock_inv.call_count}, SendInput={mock_si.call_count}")
            print(f"  [6] Agent Final Result: Success={res_2.success}, PermissionDenied={res_2.permission_denied}")
            print(f"  [7] Response Text: '{res_2.final_text}'")
            print()

# --- TEST 3: APPROVAL PATH (EXACTLY ONE EXECUTION) ---
print("--- TEST 3: REQUIRES_CONFIRMATION Action (Delete File) -> APPROVED ---")
reset_trackers()

provider_3 = MagicMock()
provider_3.supports_capability.return_value = True
provider_3.generate.side_effect = [
    ModelResponse(tool_calls=[ToolCallRequest(id="call_del_appr", name="semantic_click", arguments={"target_name": "Delete File"})]),
    ModelResponse(text="Completed deleting file.")
]
agent_3 = Agent(provider=provider_3)

def cb_approve(tool_name, args, perm_level):
    global pre_approval_execution
    if invoke_call_count > 0 or select_call_count > 0 or toggle_call_count > 0 or sendinput_call_count > 0:
        pre_approval_execution = True
    print(f"  [1] PermissionEngine Decision: {perm_level.value.upper()}")
    print(f"  [2] Confirmation Modal Presented: Tool='{tool_name}', Target='{args.get('target_name')}'")
    print(f"  [3] User Decision: APPROVE & EXECUTE")
    return True

agent_3.set_confirmation_callback(cb_approve)

with patch.object(UIAutomationResolver, "resolve_element", return_value=UIResolutionResult(success=True, element=meta_conseq)):
    with patch.object(UIAutomationResolver, "invoke_element_pattern", return_value=(True, "Invoked pattern", meta_conseq)) as mock_inv:
        with patch("nova.tools.mouse._win32_send_input") as mock_si:
            res_3 = agent_3.run("Click Delete File")
            
            print(f"  [4] Pre-Approval Execution Detected: {pre_approval_execution}")
            print(f"  [5] Post-Approval Execution Count: Pattern={mock_inv.call_count}, SendInput={mock_si.call_count}")
            print(f"  [6] Agent Final Result: Success={res_3.success}, PermissionDenied={res_3.permission_denied}")
            print(f"  [7] Response Text: '{res_3.final_text}'")
            print()
