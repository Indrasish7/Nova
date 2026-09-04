# Nova V0.3 Phase B.6 — Semantic Desktop Interaction Baseline Freeze Document

## 1. Executive Summary
* **Milestone**: Nova V0.3 Phase B.6 (Semantic Desktop Interaction Architecture)
* **Status**: **FROZEN & ACCEPTED**
* **Git Baseline Commit**: `phase-b6-semantic-interaction-baseline` (`f8abd5f`)
* **Git Tag**: `v0.3-b6`
* **Automated Test Results**: **102/102 PASSED** (0 failed, 0 skipped)
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
| **Tier 1** | **Semantic Intent Extraction** | Converts natural-language requests into structured parameters (`target_name`, `control_type`, `application_context`, `action`). Suffix normalization extracts base targets. | 0 |
| **Tier 2** | **Direct UIA Pattern Invocation** *(Primary)* | Resolves native UI Automation elements and invokes control patterns (`InvokePattern.Invoke()`, `SelectionItemPattern.Select()`, `TogglePattern.Toggle()`, `ExpandCollapsePattern.Expand()`). | **0** |
| **Tier 3** | **Bounding Box Physical Fallback** | If a UIA element is resolved but exposes no COM pattern, calculates bounding box center and executes verified click. | 1 (conditional) |
| **Tier 4** | **Perception / Vision Fallback** | If UIA resolution fails (NOT_FOUND / UNAVAILABLE only), captures screenshot observation for vision-based coordinates. | 1 (conditional) |
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
7. **Nova Launcher & Taskbar Exclusion Invariant**: Launcher PID (`os.getpid()`) and Windows Taskbar (`explorer.exe`) are strictly excluded from UIA application window enumeration.
8. **Elevation Boundary Invariant**: When running non-elevated, actions targeting elevated windows fail closed with `ELEVATION_REQUIRED`. No coordinate fallback or phantom clicks are permitted.
9. **Fail-Closed Physical Fallback**: Physical clicks cannot occur if cursor round-trip verification fails.

---

## 5. Automated Test Suite Regression Results

* **Command**: `pytest -q`
* **Tests Collected**: 102
* **Passed**: 102
* **Failed**: 0
* **Skipped**: 0

### Test Breakdown by Module:
* `tests/test_agent.py`: 6 tests passed
* `tests/test_desktop_interaction.py`: 14 tests passed
* `tests/test_gemini_provider.py`: 7 tests passed
* `tests/test_perception.py`: 9 tests passed
* `tests/test_permissions.py`: 6 tests passed
* `tests/test_semantic_interaction.py`: 47 tests passed
* `tests/test_semantic_ui.py`: 8 tests passed
* `tests/test_tools.py`: 5 tests passed

---

## 6. Manual Acceptance Results

| Test | Semantic Target Resolved | Execution Path | SendInput Calls | Permission Level | Verification Outcome | Final Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Calculator 1** | `Name='One'`, `AutoID='num1Button'` | `InvokePattern.Invoke()` | **0** | `SAFE` (BALANCED) | Display = `"Display is 1"` | `SUCCESS` |
| **Task Manager Performance** | `Name='Performance'`, `ControlType='TabItem'` | `SelectionItemPattern.Select()` | **0** | `DANGEROUS` | Tab selected = `True` | `SUCCESS` |
| **Task Manager App history** | `Name='App history'`, `ControlType='TabItem'` | `SelectionItemPattern.Select()` | **0** | `DANGEROUS` | Tab selected = `True` | `SUCCESS` |
| **This PC Physical Fallback** | Desktop icon "This PC" | Physical click after cursor verification | 1 | Evaluated by PermissionEngine | Cursor verified ($\le 2$px) | `SUCCESS` |
| **This PC Double-Click** | Desktop icon "This PC" | Double-click SendInput | 2 | Evaluated by PermissionEngine | Explorer window opened | `SUCCESS` |
| **Spotify Rejection** | `app_name="spotify"` | Blocked by AppResolver | **0** | `DANGEROUS` / `BLOCKED` | Not in allowlist | `REJECTED` |
| **Invalid App Context** | Non-existent window | Not found in UIA / Win32 | **0** | Evaluated | Target window unavailable | `REJECTED` |
| **Elevation Guard** | `taskmgr.exe` without admin Nova | Fails closed: ELEVATION_REQUIRED | **0** | `DANGEROUS` | Zero phantom clicks | `FAIL_CLOSED` |
| **Ambiguity Guard** | >1 matching control | Fails closed: AMBIGUOUS | **0** | Evaluated | Zero pattern / mouse calls | `FAIL_CLOSED` |

---

## 7. Operational Modes
1. **Standard User Applications**: Run Nova normally (`python main.py`). Interacts seamlessly with standard applications (Calculator, Notepad, File Explorer, etc.).
2. **Administrative Applications**: Run Nova with Administrator privileges (`run_admin.bat` or "Run as Administrator"). Interacts with elevated tools (Task Manager) via native UIA patterns.

---

## 8. Files Changed in Phase B.6
* `nova/config.py`: Updated `SYSTEM_PROMPT` establishing `semantic_click` as primary interaction mechanism.
* `nova/perception/models.py`: Added `SemanticTarget`, `UIElementMetadata`, `ResolutionStatus`, and canonical `ResolutionResult`.
* `nova/perception/resolver.py`: Implemented multi-tier `TargetResolver` with strict ambiguity and status handling.
* `nova/perception/uia.py`: Added UIA COM pattern execution, Taskbar exclusion, suffix normalization, Win32 fallback, and UIPI elevation checking.
* `nova/perception/verifier.py`: Added `verify_semantic_click()` and Calculator display verification.
* `nova/permissions/engine.py`: Added UIA element and `application_context` evaluation; protected process rating.
* `nova/runtime/agent.py`: Integrated fail-closed gates for ambiguity and elevation, truthful metadata enrichment.
* `nova/tools/mouse.py`: Added fail-closed Cursor Round-Trip Verification.
* `nova/tools/open_app.py`: Added `runas` support for administrative applications.
* `nova/tools/semantic_click.py`: Implemented `semantic_click` tool with UIA COM patterns and verification.
* `nova/ui/widgets.py`: Truthful confirmation dialog strictly distinguishing UIA from physical mouse clicks.
* `run_admin.bat`: 1-Click Administrator launcher for elevated desktop interactions.
* `tests/test_semantic_interaction.py`: 47 comprehensive architectural and live scenario tests.
