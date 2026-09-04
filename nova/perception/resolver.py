"""
Target Resolver Engine.

Provides multi-tier TargetResolver abstraction (UIA -> Vision -> Physical Fallback)
converting target resolution requests into canonical SemanticTarget instances.
Enforces Nova launcher exclusion and strict disambiguation rules.
"""

import os
from typing import Optional, List
from nova.perception.models import SemanticTarget, ResolutionResult, ResolutionStatus
from nova.perception.uia import UIAutomationResolver
from nova.logger import logger


class TargetResolver:
    """Canonical Multi-Tier Target Resolver for Nova desktop controls."""

    def __init__(self):
        self.uia_resolver = UIAutomationResolver()

    def resolve(
        self,
        target_name: str,
        control_type: Optional[str] = None,
        process_name: Optional[str] = None,
        window_title: Optional[str] = None,
        application_context: Optional[str] = None
    ) -> ResolutionResult:
        """
        Resolve a semantic target using the resolution hierarchy:
        Tier 2: Windows UI Automation (Primary)
        Tier 5: Vision Perception (Fallback for NOT_FOUND / UNAVAILABLE only)
        Tier 6: Physical Bounding Box (Last-resort Fallback)
        """
        clean_target = target_name.strip()
        app_ctx = (application_context or process_name or window_title or "").strip()

        logger.info(
            f"TargetResolver | Searching target='{clean_target}' | ControlType='{control_type or 'Any'}' | AppContext='{app_ctx or 'Foreground'}'"
        )

        # Tier 2: Windows UI Automation Resolution (Primary)
        uia_res = self.uia_resolver.resolve_element(
            target_name=clean_target,
            control_type=control_type,
            window_title=window_title,
            process_name=process_name,
            application_context=app_ctx
        )

        if uia_res.status == ResolutionStatus.AMBIGUOUS or uia_res.disambiguation_count > 1:
            logger.warning(f"[TargetResolver] Ambiguity guard triggered: {uia_res.error or 'Multiple matching controls'}")
            candidates = [
                self.uia_resolver.metadata_to_semantic_target(c, resolver_source="uia")
                for c in uia_res.candidates
            ] if uia_res.candidates else ([self.uia_resolver.metadata_to_semantic_target(uia_res.element)] if uia_res.element else [])
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.AMBIGUOUS,
                resolver_source="uia",
                confidence=0.0,
                candidates=candidates,
                disambiguation_count=uia_res.disambiguation_count,
                error=uia_res.error or f"Target '{clean_target}' is ambiguous: {uia_res.disambiguation_count} matching controls found."
            )

        elif uia_res.status == ResolutionStatus.SUCCESS and uia_res.element:
            semantic_target = self.uia_resolver.metadata_to_semantic_target(
                uia_res.element,
                resolver_source="uia",
                confidence=uia_res.match_confidence
            )

            logger.info(
                f"[TargetResolver] Resolved target:\n"
                f"Name={semantic_target.target_name}\n"
                f"AutomationId={semantic_target.automation_id}\n"
                f"ControlType={semantic_target.control_type}\n"
                f"Process={semantic_target.process_name}\n"
                f"Source=uia"
            )

            return ResolutionResult(
                success=True,
                status=ResolutionStatus.SUCCESS,
                target=semantic_target,
                resolver_source="uia",
                confidence=semantic_target.confidence,
                candidates=[semantic_target],
                disambiguation_count=1
            )

        elif uia_res.status == ResolutionStatus.DISABLED:
            logger.warning(f"[TargetResolver] Disabled target element: {uia_res.error}")
            disabled_target = (
                self.uia_resolver.metadata_to_semantic_target(uia_res.element, resolver_source="uia")
                if uia_res.element else None
            )
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.DISABLED,
                target=disabled_target,
                resolver_source="uia",
                confidence=0.0,
                candidates=[disabled_target] if disabled_target else [],
                disambiguation_count=uia_res.disambiguation_count,
                error=uia_res.error
            )

        elif uia_res.status == ResolutionStatus.NOT_FOUND:
            logger.info(f"[TargetResolver] UIA target not found for '{clean_target}'. Fallback permitted: {uia_res.error}")
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.NOT_FOUND,
                resolver_source="physical_fallback",
                confidence=0.0,
                disambiguation_count=0,
                error=uia_res.error or f"Target '{clean_target}' was not found in UI Automation."
            )

        elif uia_res.status == ResolutionStatus.UNAVAILABLE:
            logger.info(f"[TargetResolver] UIA target unavailable for '{clean_target}'. Fallback permitted: {uia_res.error}")
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.UNAVAILABLE,
                resolver_source="physical_fallback",
                confidence=0.0,
                disambiguation_count=0,
                error=uia_res.error or f"Target application for '{clean_target}' is unavailable."
            )

        else:  # ResolutionStatus.ERROR
            logger.error(f"[TargetResolver] UIA resolution error for '{clean_target}': {uia_res.error}")
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.ERROR,
                resolver_source="uia",
                confidence=0.0,
                disambiguation_count=0,
                error=uia_res.error or f"UIA error occurred while resolving '{clean_target}'."
            )
