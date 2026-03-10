"""
Pydantic models for Document Processing
"""

from typing import TypedDict, Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# ENUMS
# ============================================================================

class DocumentType(str, Enum):
    """Types of documents"""
    ID_CARD = "id_card"
    PASSPORT = "passport"
    CERTIFICATE = "certificate"
    BIRTH_CERTIFICATE = "birth_certificate"
    DEGREE = "degree"
    TRANSCRIPT = "transcript"
    UTILITY_BILL = "utility_bill"
    OTHER = "other"


class ProcessingStatus(str, Enum):
    """Document processing status"""
    UPLOADED = "uploaded"
    OCR_PROCESSING = "ocr_processing"
    LLM_EXTRACTING = "llm_extracting"
    COMPLETE = "complete"
    ERROR = "error"


# ============================================================================
# OCR MODELS
# ============================================================================

class OCRResult(BaseModel):
    """Result from OCR processing"""
    english_text: Optional[str] = None
    urdu_text: Optional[str] = None
    combined_text: Optional[str] = None
    english_length: int = 0
    urdu_length: int = 0


# ============================================================================
# EXTRACTED DATA MODELS
# ============================================================================

class PersonalInfo(BaseModel):
    """Common personal information extracted from documents"""
    full_name: Optional[str] = None
    father_name: Optional[str] = None
    mother_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    religion: Optional[str] = None


class IdentificationInfo(BaseModel):
    """Identification numbers and IDs"""
    id_number: Optional[str] = Field(None, description="National ID / CNIC")
    passport_number: Optional[str] = None
    license_number: Optional[str] = None
    registration_number: Optional[str] = None


class AddressInfo(BaseModel):
    """Address information"""
    permanent_address: Optional[str] = None
    current_address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None


class ContactInfo(BaseModel):
    """Contact information"""
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None


class DocumentMetadata(BaseModel):
    """Metadata about the document itself"""
    document_type: Optional[DocumentType] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    issuing_authority: Optional[str] = None
    document_number: Optional[str] = None


class ExtractedDocumentData(BaseModel):
    """Complete extracted data from a document"""
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    identification: IdentificationInfo = Field(default_factory=IdentificationInfo)
    address: AddressInfo = Field(default_factory=AddressInfo)
    contact: ContactInfo = Field(default_factory=ContactInfo)
    document_info: DocumentMetadata = Field(default_factory=DocumentMetadata)
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Any additional extracted fields")


# ============================================================================
# DOCUMENT PROCESSING STATE (for LangGraph)
# ============================================================================

class DocumentAgentState(TypedDict):
    """
    The state that flows through the document processing LangGraph agent.
    """
    
    # INPUT
    file_path: str
    user_id: Optional[str]
    document_type: Optional[str]
    languages: List[str]
    
    # TRACKING
    status: ProcessingStatus
    errors: List[str]
    
    # OCR OUTPUTS
    english_text: Optional[str]
    urdu_text: Optional[str]
    combined_text: Optional[str]
    
    # LLM OUTPUTS
    extracted_data: Optional[Dict]
    
    # FINAL RESULTS
    success: bool
    output_path: Optional[str]


# ============================================================================
# API REQUEST/RESPONSE MODELS
# ============================================================================

class DocumentUploadRequest(BaseModel):
    """Request model for document upload"""
    document_type: Optional[DocumentType] = None
    process: bool = True
    languages: List[str] = Field(default=["english", "urdu"])


class DocumentUploadResponse(BaseModel):
    """Response model for document upload"""
    success: bool
    user_id: str
    original_filename: str
    document_type: Optional[str]
    processed: bool
    errors: List[str] = Field(default_factory=list)
    data: Optional[Dict[str, Any]] = None


class DocumentDataResponse(BaseModel):
    """Response model for getting document data"""
    success: bool
    user_id: str
    filename: str
    ocr: OCRResult
    extracted: Dict[str, Any]


class DocumentListItem(BaseModel):
    """Single item in document list"""
    filename: str
    document_type: Optional[str]
    path: str
    size: int
    processed: bool
    created_at: float


class DocumentListResponse(BaseModel):
    """Response model for listing documents"""
    user_id: str
    total_documents: int
    documents: List[DocumentListItem]


class MergedDocumentData(BaseModel):
    """Merged data from multiple documents"""
    user_id: str
    sources: List[str]
    total_fields: int
    merged_data: Dict[str, Any]