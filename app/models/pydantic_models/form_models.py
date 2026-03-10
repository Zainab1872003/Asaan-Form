"""
Pydantic models for Form Processing
"""

from typing import TypedDict, Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# ENUMS
# ============================================================================

class ProcessingStage(str, Enum):
    """Stages in form processing workflow"""
    UPLOAD = "upload"
    DOCLING_CONVERT = "docling_convert"
    LLM_EXTRACT = "llm_extract"
    VALIDATE = "validate"
    COMPLETE = "complete"
    ERROR = "error"


class FieldType(str, Enum):
    """Types of form fields"""
    TEXT_INPUT = "text_input"
    TEXTAREA = "textarea"
    DATE = "date"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SIGNATURE = "signature"
    DROPDOWN = "dropdown"
    IMAGE_UPLOAD = "image_upload"
    NUMBER = "number"


# ============================================================================
# FORM FIELD MODELS
# ============================================================================

class FieldCoordinates(BaseModel):
    """Bounding box coordinates for a field"""
    left: float
    top: float
    right: float
    bottom: float
    
    @classmethod
    def from_list(cls, coords: List[float]) -> "FieldCoordinates":
        """Create from [left, top, right, bottom] list"""
        if len(coords) >= 4:
            return cls(left=coords[0], top=coords[1], right=coords[2], bottom=coords[3])
        return cls(left=0, top=0, right=0, bottom=0)


class FieldSpan(BaseModel):
    """Character span in the text"""
    offset: int
    length: int


class FormField(BaseModel):
    """A single form field with all its properties"""
    field_name: str = Field(..., description="Display name of the field")
    field_key: str = Field(..., description="Unique key for the field (snake_case)")
    field_type: FieldType = Field(default=FieldType.TEXT_INPUT)
    required: bool = Field(default=True)
    validation: Optional[str] = Field(None, description="Validation rule")
    coordinates: Optional[List[float]] = Field(None, description="[left, top, right, bottom]")
    span: Optional[FieldSpan] = None
    page_number: int = Field(default=1)
    placeholder: Optional[str] = None
    options: Optional[List[str]] = Field(None, description="Options for dropdown/radio")


class SpecialArea(BaseModel):
    """Special areas like signature boxes, photo areas"""
    type: str = Field(..., description="signature, image_upload, stamp")
    label: str
    requirements: Optional[str] = None
    coordinates: Optional[List[float]] = None
    page_number: int = Field(default=1)


class FormExtractionResult(BaseModel):
    """Result of form field extraction"""
    form_fields: List[FormField] = Field(default_factory=list)
    instructions: List[str] = Field(default_factory=list)
    special_areas: List[SpecialArea] = Field(default_factory=list)


# ============================================================================
# FORM PROCESSING STATE (for LangGraph)
# ============================================================================

class FormAgentState(TypedDict):
    """
    The state that flows through the form processing LangGraph agent.
    Each node reads from and writes to this state.
    """
    
    # INPUT
    file_path: str
    user_id: Optional[str]
    form_name: Optional[str]
    
    # TRACKING
    current_stage: ProcessingStage
    errors: List[str]
    
    # DOCLING OUTPUTS
    markdown_content: Optional[str]
    docling_json: Optional[Dict]
    page_count: Optional[int]
    
    # LLM OUTPUTS
    extracted_fields: Optional[Dict]
    field_count: Optional[int]
    
    # FINAL RESULTS
    success: bool
    output_paths: Dict[str, str]


# ============================================================================
# API REQUEST/RESPONSE MODELS
# ============================================================================

class FormUploadRequest(BaseModel):
    """Request model for form upload"""
    form_name: Optional[str] = None
    process: bool = True


class FormUploadResponse(BaseModel):
    """Response model for form upload"""
    success: bool
    user_id: str
    form_id: str
    original_filename: str
    form_name: Optional[str]
    page_count: int
    processed: bool
    errors: List[str] = Field(default_factory=list)
    data: Optional[Dict[str, Any]] = None


class FormFieldsResponse(BaseModel):
    """Response model for getting form fields"""
    success: bool
    user_id: str
    form_id: str
    form_fields: FormExtractionResult
    output_paths: Dict[str, str]


class FormListItem(BaseModel):
    """Single item in form list"""
    form_id: str
    form_name: Optional[str]
    original_filename: Optional[str]
    page_count: int
    processed: bool
    uploaded_at: Optional[str]


class FormListResponse(BaseModel):
    """Response model for listing forms"""
    user_id: str
    total_forms: int
    forms: List[FormListItem]