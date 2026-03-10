import asyncio
import json
from typing import Dict, List, Any
from utils.llm import get_llm, generate_response


# Field types that are rendered as checked/unchecked (checkmark drawn when true)
BOOLEAN_FIELD_TYPES = ("checkbox", "radio")

# Radio-style fields: LLM must return the selected option string (e.g. "Female", "Single")
# so the overlay can draw the checkmark in the correct circle.
RADIO_FIELD_OPTIONS = {
    "gender": ("Male", "Female"),
    "status": ("Single", "Married"),
}


def _normalize_boolean_value(value: Any) -> bool:
    """Normalize various truthy representations to bool for checkbox/radio overlay."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    return s in ("true", "yes", "1", "checked", "x", "✓", "✔", "on")


def _is_radio_option_value(field_key: str, value: Any) -> bool:
    """True if value is a valid option string for a radio-style field (e.g. Female, Single)."""
    if value is None or field_key not in RADIO_FIELD_OPTIONS:
        return False
    s = str(value).strip()
    return any(s.lower() == opt.lower() for opt in RADIO_FIELD_OPTIONS[field_key])


class FormFillingService:
    """
    Service to map extracted document data onto form fields.
    Uses LLM to perform intelligent semantic matching with proper handling for
    addresses (present vs permanent), checkboxes, radio buttons, and dates.
    """
    
    def __init__(self):
        self.llm = get_llm()

    async def fill_form(
        self, 
        form_fields: List[Dict[str, Any]], 
        document_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Map document data to form fields using AI for intelligent mapping.
        
        Args:
            form_fields: List of field dicts (from FormProcessingService)
            document_data: Merged data from documents (from DocumentProcessingService)
            
        Returns:
            Updated form_fields with a new 'value' key for each field
        """
        print("\n🤖 Mapping document data to form fields (AI)...")
        
        # 1. Prepare target schema with full context for the LLM (key, label, type)
        target_schema = [
            {
                "key": f.get("field_key"), 
                "label": f.get("field_name"), 
                "type": (f.get("field_type") or "text_input").strip().lower(),
            } 
            for f in form_fields
        ]

        # 2. Build the detailed prompt
        prompt = self._build_mapping_prompt(document_data, target_schema)
        system_prompt = self._get_system_prompt()
        
        try:
            # 3. Call LLM (sync in thread to not block event loop)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            content = await asyncio.to_thread(generate_response, self.llm, messages)
            content = self._clean_json_response(content)
            mapped_values = json.loads(content)
            
            if not isinstance(mapped_values, dict):
                mapped_values = {}
            print(f"  ✓ Mapped {len(mapped_values)} fields")

            # 4. Merge values back and normalize checkbox/radio to boolean
            filled_fields = []
            for field in form_fields:
                key = field.get("field_key")
                field_type = (field.get("field_type") or "text_input").strip().lower()
                new_field = field.copy()
                
                if key in mapped_values:
                    raw = mapped_values[key]
                    # Radio-style (Gender, Status): keep option string "Female"/"Single" etc. for correct circle
                    if field_type in BOOLEAN_FIELD_TYPES and _is_radio_option_value(key, raw):
                        new_field["value"] = raw if isinstance(raw, str) else str(raw).strip()
                    elif field_type in BOOLEAN_FIELD_TYPES:
                        new_field["value"] = _normalize_boolean_value(raw)
                    else:
                        new_field["value"] = raw if raw is not None else None
                else:
                    new_field["value"] = None
                
                filled_fields.append(new_field)
                
            return filled_fields

        except Exception as e:
            print(f"  ❌ Mapping failed: {e}")
            return [dict(f, value=None) for f in form_fields]

    def _get_system_prompt(self) -> str:
        return """You are an expert form-filling assistant. You map data extracted from user documents (ID cards, CVs, certificates, domicile, etc.) onto form fields.

Your job is to:
1. Match source data to form fields by meaning (semantic match), not just key names.
2. Follow field-type rules below exactly.
3. Never invent data. Use only what appears in the SOURCE DATA. If nothing matches, use null.

FIELD-TYPE RULES:

— ADDRESSES (critical distinction):
• "Present Address" / "address" (in present section): Current residence, where the person lives NOW. Use: contact_info.address, current address from CV, or any "current/present" address in source. If only one address exists and it's clearly permanent (e.g. from ID/domicile), you may use it but prefer labeling as present when form asks for "Present".
• "Permanent Address" / "permanent_address" / "address_permanent": Permanent/native address, usually on ID or domicile. Use: applicant.address_in_pakistan (format as full address string), place_of_domicile, or any "permanent" address. For nested address_in_pakistan use: street, mohallah, city, tehsil, district, province to build one string.
• "Address" alone: Infer from context. If the form groups it with "Permanent" or "Division" (permanent), use permanent address. If with "Present", use present address.
• Division fields (division, division_permanent): Use district/division from the corresponding address (e.g. Lahore, PUNJAB).

— CHECKBOX and RADIO (critical for correct overlay):
• For "Gender" field: return the selected option as string: "Male" or "Female" (from source gender, applicant data, or infer from name/context). Use "Female" if source says female or suggests it; "Male" otherwise. Never return true/false for Gender.
• For "Status" field (Single/Married): return "Single" or "Married" from marital_status or equivalent in source. Never return true/false for Status.
• For other checkbox fields (e.g. Employed/Student): return boolean true or false.
• Do not return null for Gender/Status when source has the info; use "Female"/"Male" and "Single"/"Married" so the correct radio circle is filled.

— TEXT / TEXTAREA / DATE (strict mapping — wrong field = wrong box on form):
• "Student's Name" / "Candidate Name" → ONLY name, full_name, applicant.full_name. Never occupation, CNIC, or phone.
• "Father's Name" → ONLY father_name. Never occupation (e.g. JOBLESS), never CNIC.
• "Mother's Name" → ONLY mother_name. Never CNIC, never NID, never phone.
• "Birth Date" / "Date of Birth" → ONLY date_of_birth. Never phone number, never CNIC. Format YYYY-MM-DD.
• "Phone Number" / "Phone" → ONLY phone_number, contact_info.phone_number. Never date, never email.
• "Email Address" → ONLY email, contact_info.email. Never put email next to Gender or other wrong label.
• "Occupation" → ONLY designation, trade_or_occupation, job title. Never father's name or person name.
• "Course Name" → ONLY course name, degree name, or education program. Never student name.
• "Religion" → ONLY religion from source. Never address or nationality.
• "Nationality" → ONLY nationality. Never address or religion.
• "NID Number" / "CNIC" → ONLY nid/cnic from source. Never phone or date.
• Dates: normalize to YYYY-MM-DD when possible. Phone/CNIC: use format from source.

— DROPDOWN:
• Return the exact option text that matches the source (e.g. source "PUNJAB" → return "Punjab" or the form's option text).

OUTPUT: Return a single JSON object. Keys = TARGET field "key", values = mapped value (string, number, boolean, or null). Include every target key; use null when no source data fits."""

    def _build_mapping_prompt(self, source_data: Dict, target_schema: List[Dict]) -> str:
        return f"""SOURCE DATA (extracted from user documents):
{json.dumps(source_data, indent=2, ensure_ascii=False)}

TARGET FORM FIELDS (key = use this as key in your JSON output; label = human label on form; type = how to fill):
{json.dumps(target_schema, indent=2, ensure_ascii=False)}

TASK: For each TARGET field "key", set the value from SOURCE DATA using the rules you were given. Pay special attention to:
- present_address vs permanent_address (present = current residence; permanent = ID/domicile address).
- Gender: return "Male" or "Female" (string). Status: return "Single" or "Married" (string). Other checkboxes: true/false.
- Match each label to the correct source key: Student's Name→name, Father's Name→father_name, Mother's Name→mother_name, Birth Date→date_of_birth, Phone Number→phone_number, Email→email, Occupation→designation/trade, Course Name→course/degree. Do not mix (e.g. never put occupation in Father's Name or CNIC in Mother's Name).
- Dates as YYYY-MM-DD when possible.

Return ONLY a single JSON object: keys = target "key", values = filled value (string, number, boolean, or null). No explanation, no markdown code fence."""

    def _clean_json_response(self, content: str) -> str:
        content = content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].strip()
        return content

# Create singleton
form_filling_service = FormFillingService()