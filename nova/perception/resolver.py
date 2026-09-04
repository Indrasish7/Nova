"""
Target Resolver Engine.

Provides multi-tier TargetResolver abstraction (UIA -> Vision -> Physical Fallback)
converting target resolution requests into canonical SemanticTarget instances.
Enforces Nova launcher exclusion and strict disambiguation rules.
"""

import os
from typing import Optional, List
from nova.perception.models import SemanticTarget, ResolutionResult
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
        Tier 5: Vision Perception (Fallback)
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

        if uia_res.success and uia_res.element:
            # Check disambiguation safety
            if uia_res.disambiguation_count > 3:
                err_msg = f"Target '{clean_target}' is ambiguous: {uia_res.disambiguation_count} matching controls found. Please specify additional context."
                logger.warning(f"TargetResolver | Ambiguity Guard Triggered: {err_msg}")
                return ResolutionResult(
                    success=False,
                    resolver_source="uia",
                    confidence=0.5,
                    disambiguation_count=uia_res.disambiguation_count,
                    error=err_msg
                )

            semantic_target = self.uia_resolver.metadata_to_semantic_target(
                uia_res.element,
                resolver_source="uia",
                confidence=uia_res.match_confidence
            )

            logger.info(
                f"TargetResolver | Tier 2 UIA RESOLVED: '{semantic_target.target_name}' ({semantic_target.control_type}) in {semantic_target.process_name}"
            )

            return ResolutionResult(
                success=True,
                target=semantic_target,
                resolver_source="uia",
                confidence=semantic_target.confidence,
                disambiguation_count=uia_res.disambiguation_count
            )

        # UIA Resolution Failed -> Fallback Required
        logger.info(f"TargetResolver | Tier 2 UIA Unresolved for '{clean_target}'. Fallback required: {uia_res.error}")

        return ResolutionResult(
            success=False,
            resolver_source="physical_fallback",
            confidence=0.0,
            disambiguation_count=0,
            error=uia_res.error or f"Target '{clean_target}' could not be resolved by UI Automation."
        )
