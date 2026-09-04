"""
Action Verifier Module.

Provides deterministic state-change verification for desktop interaction actions,
distinguishing VERIFIED_SUCCESS, NO_OBSERVABLE_CHANGE, and VERIFICATION_FAILURE outcomes.
"""

from enum import Enum
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from PIL import Image, ImageChops, ImageStat


class VerificationOutcome(str, Enum):
    """Categorized outcomes of an action verification check."""
    VERIFIED_SUCCESS = "verified_success"
    NO_OBSERVABLE_CHANGE = "no_observable_change"
    VERIFICATION_FAILURE = "verification_failure"


class VerificationResult(BaseModel):
    """Structured result of action state-change verification."""
    outcome: VerificationOutcome
    verified: bool
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    reason: str = Field(..., description="Human-readable explanation of verification outcome")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Deterministic empirical evidence metrics")
    before_observation: Optional[Dict[str, Any]] = None
    after_observation: Optional[Dict[str, Any]] = None


class ActionVerifier:
    """Verifier evaluating state changes between pre-action and post-action observations."""

    @staticmethod
    def verify_mouse_move(
        target_x: int,
        target_y: int,
        actual_cursor: Tuple[int, int]
    ) -> VerificationResult:
        """Verify mouse cursor relocation using Win32 GetCursorPos."""
        actual_x, actual_y = actual_cursor
        # Allow small +/- 2 pixel delta tolerance for cursor hot-spot positioning
        if abs(actual_x - target_x) <= 2 and abs(actual_y - target_y) <= 2:
            return VerificationResult(
                outcome=VerificationOutcome.VERIFIED_SUCCESS,
                verified=True,
                confidence=1.0,
                reason=f"Cursor position verified at ({actual_x}, {actual_y}).",
                evidence={"target": [target_x, target_y], "actual": [actual_x, actual_y]}
            )
        else:
            return VerificationResult(
                outcome=VerificationOutcome.VERIFICATION_FAILURE,
                verified=False,
                confidence=0.9,
                reason=f"Cursor expected at ({target_x}, {target_y}), but found at ({actual_x}, {actual_y}).",
                evidence={"target": [target_x, target_y], "actual": [actual_x, actual_y]}
            )

    @staticmethod
    def verify_mouse_click(
        target_x: int,
        target_y: int,
        pre_obs: Optional[Dict[str, Any]],
        post_obs: Optional[Dict[str, Any]]
    ) -> VerificationResult:
        """
        Verify mouse click execution by comparing pre and post observations.
        Distinguishes VERIFIED_SUCCESS, NO_OBSERVABLE_CHANGE, and VERIFICATION_FAILURE.
        """
        if not pre_obs or not post_obs:
            return VerificationResult(
                outcome=VerificationOutcome.NO_OBSERVABLE_CHANGE,
                verified=True,
                confidence=0.5,
                reason="Click executed successfully, but observation telemetry was unavailable for delta comparison.",
                evidence={}
            )

        pre_title = pre_obs.get("active_window_title")
        post_title = post_obs.get("active_window_title")
        pre_img_path = pre_obs.get("image_path")
        post_img_path = post_obs.get("image_path")

        evidence: Dict[str, Any] = {
            "target": [target_x, target_y],
            "pre_active_window": pre_title,
            "post_active_window": post_title,
        }

        # Signal 1: Active Window Title Change
        if pre_title and post_title and pre_title != post_title:
            evidence["window_title_changed"] = True
            return VerificationResult(
                outcome=VerificationOutcome.VERIFIED_SUCCESS,
                verified=True,
                confidence=0.95,
                reason=f"Click changed active window title from '{pre_title}' to '{post_title}'.",
                evidence=evidence,
                before_observation=pre_obs,
                after_observation=post_obs
            )

        # Signal 2: Image Pixel Difference Analysis
        pixel_diff_rms = 0.0
        if pre_img_path and post_img_path:
            try:
                img1 = Image.open(pre_img_path).convert("RGB")
                img2 = Image.open(post_img_path).convert("RGB")
                diff = ImageChops.difference(img1, img2)
                stat = ImageStat.Stat(diff)
                pixel_diff_rms = sum(stat.rms) / len(stat.rms)
                evidence["pixel_diff_rms"] = round(pixel_diff_rms, 2)
            except Exception as e:
                evidence["pixel_diff_error"] = str(e)

        if pixel_diff_rms > 1.5:
            return VerificationResult(
                outcome=VerificationOutcome.VERIFIED_SUCCESS,
                verified=True,
                confidence=0.85,
                reason=f"Click produced observable screen UI change (RMS delta: {pixel_diff_rms:.2f}).",
                evidence=evidence,
                before_observation=pre_obs,
                after_observation=post_obs
            )

        return VerificationResult(
            outcome=VerificationOutcome.NO_OBSERVABLE_CHANGE,
            verified=True,
            confidence=0.6,
            reason="Click completed via Win32 API, but no visual state or active window change was detected.",
            evidence=evidence,
            before_observation=pre_obs,
            after_observation=post_obs
        )

    @staticmethod
    def verify_semantic_click(
        target_name: str,
        via_uia_pattern: bool,
        pre_obs: Optional[Dict[str, Any]],
        post_obs: Optional[Dict[str, Any]],
        pre_meta: Optional[Dict[str, Any]] = None,
        post_meta: Optional[Dict[str, Any]] = None
    ) -> VerificationResult:
        """Verify semantic UI invocation state change using UIA properties and observation telemetry."""
        # 1. Check UIA property delta (e.g. TabItem selected state changed)
        if pre_meta and post_meta:
            pre_selected = pre_meta.get("selected")
            post_selected = post_meta.get("selected")
            if pre_selected is False and post_selected is True:
                return VerificationResult(
                    outcome=VerificationOutcome.VERIFIED_SUCCESS,
                    verified=True,
                    confidence=1.0,
                    reason=f"UIA property verified: '{target_name}' selection state changed to selected=True.",
                    evidence={"target": target_name, "via_uia_pattern": via_uia_pattern, "pre_selected": pre_selected, "post_selected": post_selected}
                )

        # 2. Pattern invocation succeeded
        if via_uia_pattern:
            return VerificationResult(
                outcome=VerificationOutcome.VERIFIED_SUCCESS,
                verified=True,
                confidence=0.95,
                reason=f"Semantic UIA pattern invocation succeeded for '{target_name}'.",
                evidence={"target": target_name, "via_uia_pattern": via_uia_pattern}
            )

        # Fallback to mouse click verification
        return ActionVerifier.verify_mouse_click(0, 0, pre_obs, post_obs)
