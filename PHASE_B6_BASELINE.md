# Nova V0.3 Phase B.6 — Semantic Desktop Interaction Baseline Freeze Document

## 1. Executive Summary
* **Milestone**: Nova V0.3 Phase B.6 (Semantic Desktop Interaction Architecture)
* **Status**: **FROZEN & ACCEPTED**
* **Git Baseline Commit**: `phase-b6-semantic-interaction-baseline` (`f8abd5f`)
* **Git Tag**: `v0.3-b6`
* **Automated Test Results**: **79/79 PASSED** (0 failed, 0 skipped)
* **Phase C Status**: **NOT IMPLEMENTED** (Keyboard typing, hotkeys, and text entry remain strictly unimplemented as required).

---

## 2. Architecture Overview
Milestone V0.3 Phase B.6 establishes **Semantic Windows UI Interaction** as Nova's primary execution abstraction:

$$\text{User Prompt} \longrightarrow \text{Semantic Intent Extraction} \longrightarrow \text{Local UIA Target Resolver} \longrightarrow \text{PermissionEngine Authority} \longrightarrow \text{Direct UIA Pattern Invocation} \longrightarrow \text{State Verification}$$

Physical coordinates, visual bounding boxes, and `SendInput` hardware mouse events serve as a **fail-closed last-resort fallback** invoked only when UI Automation is genuinely unavailable.

---

## 3. Execution Hierarchy

| Tier | Component | Description | SendInput Calls |
| :--- | :--- | :--- | :--- |
| **Tier 1** | **Semantic Intent Extraction** | Converts natural-language requests into structured parameters (`target_name`, `control_type`, `application_context`, `action`). | 0 |
| **Tier 2** | **Direct UIA Pattern Invocation** *(Primary)* | Resolves native UI Automation elements and invokes control patterns (`InvokePattern.Invoke()`, `SelectionItemPattern.Select()`, `TogglePattern.Toggle()`, `ExpandCollapsePattern.Expand()`). | **0** |
| **Tier 3** | **Bounding Box Physical Fallback** | If a UIA element is resolved but exposes no COM pattern, calculates bounding box center and executes verified click. | 1 (conditional) |
| **Tier 4** | **Perception / Vision Fallback** | If UIA resolution fails, captures screenshot observation for vision-based coordinates. | 1 (conditional) |
| **Tier 5** | **Cursor Round-Trip Verification** | Before any physical click, moves cursor and queries Win32 `GetCursorPos()`. If $|X_{\text{actual}} - X_{\text{target}}| > 2$, **click is immediately aborted**. | 0 (abort) |
| **Tier 6** | **Post-Action State Verification** | Verifies UI mutation (e.g. Calculator display string, selection state). Distinguishes `SUCCESS` from `VERIFICATION_FAILED`. | 0 |

---

## 4. Security Invariants & Policy Enforcement

1. **PermissionEngine as Final Authority**: Gemini is untrusted. PermissionEngine locally evaluates `process_name`, `target_name`, `enabled` state, and bounding coordinates.
2. **Protected Process Invariant**: Actions targeting protected processes (`taskmgr.exe`, `regedit.exe`, `mmc.exe`, `cmd.exe`, `powershell.exe`) evaluate to **`DANGEROUS`**. User confirmation is mandatory.
3. **Pre-Approval Execution Invariant**: Zero UIA invocation and zero `SendInput` calls occur prior to explicit user approval.
4. **Denial Invariant**: If a user denies confirmation, zero pattern calls, zero `SendInput` calls, and zero state mutations occur.
5. **Calculator Low-Risk Invariant**: Under `BALANCED` mode, standard Calculator number and operator buttons evaluate to **`SAFE`** with no confirmation.
6. **Disabled Control Invariant**: Disabled controls (`enabled=False`) evaluate to **`BLOCKED`**.
7. **Nova Launcher Exclusion Invariant**: Launcher PID (`os.getpid()`) and windows are strictly excluded from UIA enumeration.
8. **Fail-Closed Physical Fallback**: Physical clicks cannot occur if cursor round-trip verification fails.

---

## 5. Automated Test Suite Regression Results

* **Command**: `.venv\Scripts\pytest.exe -v`
* **Tests Collected**: 79
* **Passed**: 79
* **Failed**: 0
* **Skipped**: 0

### Test Breakdown by Module:
* `tests/test_agent.py`: 6 tests passed
* `tests/test_desktop_interaction.py`: 14 tests passed
* `tests/test_gemini_provider.py`: 7 tests passed
* `tests/test_perception.py`: 9 tests passed
* `tests/test_permissions.py`: 6 tests passed
* `tests/test_semantic_interaction.py`: 24 tests passed
* `tests/test_semantic_ui.py`: 8 tests passed
* `tests/test_tools.py`: 5 tests passed

---

## 6. Manual Acceptance Results

| Test | Semantic Target Resolved | Execution Path | SendInput Calls | Permission Level | Verification Outcome | Final Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Calculator 1** | `Name='One'`, `AutoID='num1Button'` | `InvokePattern.Invoke()` | **0** | `SAFE` (BALANCED) | Display = `"Display is 1"` | `SUCCESS` |
| **Calculator 4** | `Name='Four'`, `AutoID='num4Button'` | `InvokePattern.Invoke()` | **0** | `SAFE` (BALANCED) | Display = `"Display is 4"` | `SUCCESS` |
| **Calculator 7** | `Name='Seven'`, `AutoID='num7Button'` | `InvokePattern.Invoke()` | **0** | `SAFE` (BALANCED) | Display = `"Display is 7"` | `SUCCESS` |
| **Calculator 147** | `num1Button` $\rightarrow$ `num4Button` $\rightarrow$ `num7Button` | `InvokePattern.Invoke()` $\times 3$ | **0** | `SAFE` (BALANCED) | Display = `"Display is 147"` | `SUCCESS` |
| **Task Manager Performance** | `Name='Performance'`, `ControlType='TabItem'` | `SelectionItemPattern.Select()` | **0** | `DANGEROUS` | Tab selected = `True` | `SUCCESS` |
| **Protected End Task Denied** | `Name='End task'`, `Process='taskmgr.exe'` | None (Aborted on denial) | **0** | `DANGEROUS` | State mutation = 0 | `PERMISSION_DENIED` |
| **Disabled Control** | Resolved with `enabled=False` | None (Blocked before execution) | **0** | `BLOCKED` | State mutation = 0 | `BLOCKED` |
| **Vision Fallback** | Un-indexed Canvas Widget | SendInput after cursor verification | 1 | Evaluated by PermissionEngine | Cursor verified ($\le 2$px) | `SUCCESS` |

---

## 7. Known Limitations
1. **Elevated Windows**: UIA inspection of processes running with higher integrity level than Nova (e.g. Administrator Task Manager when Nova runs as non-admin) requires running Nova elevated.
2. **Owner-Drawn Canvas Controls**: Non-standard controls without accessibility wrappers (e.g. custom OpenGL/DirectX surfaces) require Tier 4 Vision Fallback.

---

## 8. Files Changed in Phase B.6
* `nova/perception/models.py`: Added `SemanticTarget`, `InteractionAction`, `ResolutionResult`.
* `nova/perception/resolver.py`: Implemented multi-tier `TargetResolver` with ambiguity guards.
* `nova/perception/uia.py`: Added `_attach_default_desktop()`, two-pass exact matching, and UIA COM pattern execution.
* `nova/perception/verifier.py`: Added `verify_semantic_click()` and Calculator display verification.
* `nova/permissions/engine.py`: Added UIA and `application_context` evaluation; classified Calculator buttons as `SAFE`.
* `nova/runtime/agent.py`: Added `application_context` passing to pre-resolution and verification integration.
* `nova/tools/mouse.py`: Added fail-closed Cursor Round-Trip Verification.
* `nova/tools/semantic_click.py`: Integrated `TargetResolver`, UIA COM patterns, and verification.
* `tests/test_semantic_interaction.py`: 24 comprehensive architectural unit tests.
* `tests/test_semantic_ui.py`: 8 semantic UI tests.
