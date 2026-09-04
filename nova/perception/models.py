"""
Perception Data Models.

Structured Pydantic models for screen observations, display metrics, Windows UI Automation metadata,
and canonical SemanticTarget / ResolutionResult objects for Phase B.6.
"""

from enum import Enum
from typing import Optional, Dict, Any, Tuple, List, Literal
from pydantic import BaseModel, Field, model_validator


class DisplayInfo(BaseModel):
    """Primary screen display information."""
    width: int
    height: int
    dpi_scale: float = 1.0


class ScreenObservation(BaseModel):
    """Structured observation of the desktop display state."""
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of observation")
    width: int = Field(..., description="Screen width in pixels")
    height: int = Field(..., description="Screen height in pixels")
    cursor_x: Optional[int] = Field(None, description="Cursor X coordinate in pixels")
    cursor_y: Optional[int] = Field(None, description="Cursor Y coordinate in pixels")
    active_window_title: Optional[str] = Field(None, description="Foreground window title")
    image_path: str = Field(..., description="Path to ephemeral screenshot image artifact")
    ocr_text: Optional[str] = Field(None, description="Optional extracted text from OCR")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional perception metadata")


class InteractionAction(str, Enum):
    """Semantic interaction actions supported by Nova."""
    INVOKE = "invoke"
    SELECT = "select"
    TOGGLE = "toggle"
    EXPAND = "expand"
    COLLAPSE = "collapse"


class UIElementMetadata(BaseModel):
    """Metadata representation of a resolved Windows UI Automation element."""
    name: str = Field("", description="Name/Label of element")
    control_type: str = Field("Unknown", description="UIA Control Type name (e.g. TabItem, Button, Edit)")
    localized_control_type: str = Field("", description="Localized control type string")
    automation_id: str = Field("", description="Windows Automation ID")
    class_name: str = Field("", description="Win32/UWP Window Class name")
    process_id: int = Field(0, description="Owning Process ID")
    process_name: str = Field("unknown", description="Executable image name (e.g. taskmgr.exe, calc.exe)")
    enabled: bool = Field(True, description="Whether element is enabled for user interaction")
    selected: Optional[bool] = Field(None, description="Selection state if applicable (e.g. TabItem)")
    supported_patterns: List[str] = Field(default_factory=list, description="Supported UIA patterns (Invoke, SelectionItem, Toggle, Value, ExpandCollapse)")
    bounding_box: Tuple[int, int, int, int] = Field((0, 0, 0, 0), description="Physical screen bounding box (left, top, right, bottom)")
    center_point: Tuple[int, int] = Field((0, 0), description="Physical screen center coordinates (x, y)")
    handle: int = Field(0, description="Win32 HWND if control possesses window handle")


class SemanticTarget(BaseModel):
    """Canonical internal data model representing a target UI element."""
    target_name: str = Field(..., description="Name or label of target element")
    control_type: str = Field("Unknown", description="UIA Control Type (Button, TabItem, Edit, etc.)")
    automation_id: str = Field("", description="Windows Automation ID")
    class_name: str = Field("", description="Window/Control Class Name")
    process_id: int = Field(0, description="Owning Process ID")
    process_name: str = Field("unknown", description="Target application process image (e.g. calc.exe)")
    window_handle: int = Field(0, description="Target window HWND")
    window_title: str = Field("", description="Target window title")
    enabled: bool = Field(True, description="Whether target is enabled for interaction")
    selected: Optional[bool] = Field(None, description="Selection state if applicable")
    bounding_rectangle: Tuple[int, int, int, int] = Field((0, 0, 0, 0), description="Physical bounding box (left, top, right, bottom)")
    center_point: Tuple[int, int] = Field((0, 0), description="Physical center point (x, y)")
    supported_patterns: List[str] = Field(default_factory=list, description="Supported UIA COM patterns")
    resolver_source: Literal["uia", "vision", "physical_fallback"] = Field("uia", description="Resolver tier source")
    confidence: float = Field(1.0, description="Resolution confidence score (0.0 to 1.0)")


class ResolutionStatus(str, Enum):
    """Formal resolution status distinguishing discrete terminal and fallback states."""
    SUCCESS = "SUCCESS"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


class UIResolutionResult(BaseModel):
    """Structured result of UI Automation element resolution attempt."""
    success: bool = Field(..., description="Whether a matching UI element was resolved successfully")
    status: ResolutionStatus = Field(ResolutionStatus.NOT_FOUND, description="Formal resolution status")
    element: Optional[UIElementMetadata] = Field(None, description="Resolved element metadata if successful")
    candidates: List[UIElementMetadata] = Field(default_factory=list, description="Candidate elements matched")
    match_confidence: float = Field(0.0, description="Resolution confidence score (0.0 to 1.0)")
    disambiguation_count: int = Field(0, description="Count of candidate elements matched")
    error: Optional[str] = Field(None, description="Error message if resolution failed")

    @model_validator(mode="after")
    def _sync_status(self):
        if self.success and self.status in [ResolutionStatus.NOT_FOUND, ResolutionStatus.UNAVAILABLE, ResolutionStatus.ERROR]:
            self.status = ResolutionStatus.SUCCESS
        elif not self.success and self.status == ResolutionStatus.SUCCESS:
            self.status = ResolutionStatus.NOT_FOUND
        return self


class ResolutionResult(BaseModel):
    """Canonical multi-tier resolution result for TargetResolver."""
    success: bool = Field(..., description="Whether target was resolved")
    status: ResolutionStatus = Field(ResolutionStatus.NOT_FOUND, description="Formal resolution status")
    target: Optional[SemanticTarget] = Field(None, description="Canonical SemanticTarget if resolved")
    resolver_source: Literal["uia", "vision", "physical_fallback"] = Field("uia", description="Resolution tier source")
    confidence: float = Field(0.0, description="Confidence score")
    candidates: List[SemanticTarget] = Field(default_factory=list, description="List of matched candidate targets")
    disambiguation_count: int = Field(0, description="Count of matching candidate targets")
    error: Optional[str] = Field(None, description="Error message if resolution failed")

    @model_validator(mode="after")
    def _sync_status(self):
        if self.success and self.status in [ResolutionStatus.NOT_FOUND, ResolutionStatus.UNAVAILABLE, ResolutionStatus.ERROR]:
            self.status = ResolutionStatus.SUCCESS
        elif not self.success and self.status == ResolutionStatus.SUCCESS:
            self.status = ResolutionStatus.NOT_FOUND
        return self
