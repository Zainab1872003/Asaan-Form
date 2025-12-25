from groq import Groq
from dotenv import load_dotenv
import os
import json
import time
from typing import List, Dict, Union

# Load environment variables
load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def load_markdown(file_path):
    """Load markdown file content"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: {file_path} not found")
        return None


def load_json(file_path):
    """Load JSON file content"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {file_path} not found")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return None


def chunk_json_by_size(json_data: Union[dict, list], max_chars: int = 8000) -> List[str]:
    """
    Split JSON into chunks - focusing on the texts array
    """
    json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
    total_chars = len(json_str)
    
    print(f"📊 JSON size: {total_chars:,} characters")
    print(f"   Target: {max_chars:,} characters per chunk")
    
    # If small enough, return as single chunk
    if total_chars <= max_chars:
        print(f"   ✓ JSON fits in single chunk")
        return [json_str]
    
    chunks = []
    
    # Extract the texts array if it exists
    if isinstance(json_data, dict) and 'texts' in json_data:
        texts = json_data['texts']
        metadata = {k: v for k, v in json_data.items() if k != 'texts'}
        
        print(f"   Found {len(texts)} text items")
        
        # Calculate items per chunk
        num_chunks = (total_chars // max_chars) + 1
        items_per_chunk = max(5, len(texts) // num_chunks)  # At least 5 items per chunk
        
        for i in range(0, len(texts), items_per_chunk):
            chunk_items = texts[i:i + items_per_chunk]
            chunk_data = {
                'texts': chunk_items,
                'metadata': metadata.get('origin', {}),
                'chunk_info': f'items {i} to {i + len(chunk_items) - 1} of {len(texts)}'
            }
            chunk_str = json.dumps(chunk_data, indent=2, ensure_ascii=False)
            chunks.append(chunk_str)
        
        print(f"   ✓ Created {len(chunks)} JSON chunks")
        for idx, chunk in enumerate(chunks, 1):
            print(f"      Chunk {idx}: {len(chunk):,} characters")
        
        return chunks
    
    # Fallback: split by character count
    print(f"   Using fallback: chunking raw JSON string")
    for i in range(0, total_chars, max_chars):
        chunks.append(json_str[i:i + max_chars])
    
    return chunks if chunks else [json_str[:max_chars]]


def extract_fields_with_llm(markdown_content: str, json_chunk: str, chunk_num: int, total_chunks: int):
    """
    Extract fields with coordinates and span from one JSON chunk
    """
    
    prompt = f"""
You are a form analysis expert. Extract form fields from the JSON chunk provided.

**THIS IS CHUNK {chunk_num} OF {total_chunks}**

**FULL FORM MARKDOWN (for context):**
{markdown_content}

**JSON METADATA CHUNK ({chunk_num}/{total_chunks}):**
{json_chunk}

**EXTRACTION INSTRUCTIONS:**

1. **Field Identification**: Look for text items in the JSON that represent form field labels (like "Name", "Registration No.", "Date of Birth", etc.)

2. **Coordinates Extraction**: Each text item has a "prov" array. Extract bbox coordinates:
   - bbox.l = left (x1)
   - bbox.t = top (y1)  
   - bbox.r = right (x2)
   - bbox.b = bottom (y2)
   - Example: {{"l": 59.74, "t": 952.25, "r": 124.59, "b": 938.32}} → [59.74, 952.25, 124.59, 938.32]

3. **Span Extraction**: Extract "charspan" from prov array:
   - charspan: [start, end] → {{"offset": start, "length": end - start}}
   - Example: "charspan": [0, 11] → {{"offset": 0, "length": 11}}

4. **Page Number**: Extract "page_no" from prov array

**OUTPUT FORMAT:**
{{
  "form_fields": [
    {{
      "field_name": "Registration No.",
      "field_key": "registration_number",
      "field_type": "text_input",
      "required": true,
      "validation": "numeric",
      "coordinates": [59.74, 952.25, 124.59, 938.32],
      "span": {{"offset": 0, "length": 11}},
      "page_number": 1
    }}
  ],
  "instructions": [],
  "special_areas": []
}}

**FIELD TYPES**: text_input, textarea, date, checkbox, signature, dropdown, image_upload

Extract ALL form fields found in this chunk with their coordinates and span data.
"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": "You are a form extraction expert. Extract form fields with precise coordinates (bbox) and span (charspan) from JSON metadata."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_schema", "json_schema": {
                "name": "form_extraction",
                "schema": {
                    "type": "object",
                    "properties": {
                        "form_fields": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field_name": {"type": "string"},
                                    "field_key": {"type": "string"},
                                    "field_type": {"type": "string"},
                                    "required": {"type": "boolean"},
                                    "validation": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                                    "coordinates": {
                                        "anyOf": [
                                            {
                                                "type": "array",
                                                "items": {"type": "number"},
                                                "minItems": 4,
                                                "maxItems": 4
                                            },
                                            {"type": "null"}
                                        ]
                                    },
                                    "span": {
                                        "anyOf": [
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "offset": {"type": "integer"},
                                                    "length": {"type": "integer"}
                                                },
                                                "required": ["offset", "length"]
                                            },
                                            {"type": "null"}
                                        ]
                                    },
                                    "page_number": {"anyOf": [{"type": "integer"}, {"type": "null"}]}
                                },
                                "required": ["field_name", "field_key", "field_type", "required"]
                            }
                        },
                        "instructions": {"type": "array", "items": {"type": "string"}},
                        "special_areas": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "label": {"type": "string"},
                                    "requirements": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                                    "coordinates": {
                                        "anyOf": [
                                            {"type": "array", "items": {"type": "number"}},
                                            {"type": "null"}
                                        ]
                                    }
                                },
                                "required": ["type", "label"]
                            }
                        }
                    },
                    "required": ["form_fields", "instructions", "special_areas"]
                }
            }},
            temperature=0.1,
            max_tokens=8000
        )
        
        return json.loads(response.choices[0].message.content)
    
    except Exception as e:
        print(f"   ❌ API Error: {str(e)[:100]}")
        return None


def merge_extractions(all_extractions: List[Dict]) -> Dict:
    """Merge multiple extraction results"""
    merged = {
        "form_fields": [],
        "instructions": [],
        "special_areas": []
    }
    
    seen_fields = set()
    seen_instructions = set()
    seen_special = set()
    
    for extraction in all_extractions:
        for field in extraction.get('form_fields', []):
            field_key = field.get('field_key', '')
            if field_key and field_key not in seen_fields:
                seen_fields.add(field_key)
                merged['form_fields'].append(field)
        
        for instruction in extraction.get('instructions', []):
            if instruction and instruction not in seen_instructions:
                seen_instructions.add(instruction)
                merged['instructions'].append(instruction)
        
        for area in extraction.get('special_areas', []):
            area_key = area.get('label', '')
            if area_key and area_key not in seen_special:
                seen_special.add(area_key)
                merged['special_areas'].append(area)
    
    return merged


def main():
    markdown_file = "output/form13.md"
    json_file = "output/form13.json"  # Updated path
    
    print(f"\n{'='*70}")
    print("🚀 FORM FIELD EXTRACTION SYSTEM (WITH COORDINATES & SPAN)")
    print(f"{'='*70}\n")
    
    print("📂 Loading files...")
    
    markdown_content = load_markdown(markdown_file)
    if not markdown_content:
        print("❌ Failed to load markdown file")
        return None, None
    print(f"   ✓ Markdown: {len(markdown_content):,} characters")
    
    docling_json = load_json(json_file)
    if not docling_json:
        print("❌ Failed to load JSON file")
        return None, None
    print(f"   ✓ JSON loaded successfully")
    
    print(f"\n{'='*70}")
    print("📦 CHUNKING JSON")
    print(f"{'='*70}")
    json_chunks = chunk_json_by_size(docling_json, max_chars=8000)
    total_chunks = len(json_chunks)
    
    print(f"\n{'='*70}")
    print(f"🔄 PROCESSING {total_chunks} CHUNKS")
    print(f"{'='*70}\n")
    
    all_extractions = []
    successful = 0
    failed = 0
    
    for i, json_chunk in enumerate(json_chunks, 1):
        print(f"┌{'─'*68}┐")
        print(f"│ 🔍 CHUNK {i}/{total_chunks}".ljust(69) + "│")
        print(f"└{'─'*68}┘")
        print(f"   Markdown: {len(markdown_content):,} chars")
        print(f"   JSON chunk: {len(json_chunk):,} chars")
        print(f"   ⏳ Calling API...")
        
        extraction = extract_fields_with_llm(markdown_content, json_chunk, i, total_chunks)
        
        if extraction:
            all_extractions.append(extraction)
            fields_count = len(extraction.get('form_fields', []))
            print(f"   ✅ Extracted {fields_count} fields")
            successful += 1
        else:
            print(f"   ⚠️ Failed to extract from this chunk")
            failed += 1
        
        if i < total_chunks:
            print(f"   ⏳ Waiting 1.5s...\n")
            time.sleep(1.5)
        else:
            print()
    
    print(f"{'='*70}")
    print("📊 MERGING RESULTS")
    print(f"{'='*70}")
    print(f"API calls: {total_chunks} | Success: {successful} | Failed: {failed}")
    
    llm_fields = merge_extractions(all_extractions)
    
    print(f"\n✓ Total unique fields: {len(llm_fields.get('form_fields', []))}")
    print(f"✓ Total instructions: {len(llm_fields.get('instructions', []))}")
    print(f"✓ Total special areas: {len(llm_fields.get('special_areas', []))}")
    
    output_file = 'llm_extracted_fields_with_coords.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(llm_fields, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Saved to '{output_file}'")
    
    print(f"\n{'='*70}")
    print("📋 SAMPLE EXTRACTED FIELDS (WITH COORDINATES)")
    print(f"{'='*70}\n")
    
    fields = llm_fields.get('form_fields', [])
    for i, field in enumerate(fields[:10], 1):
        print(f"{i}. {field.get('field_name', 'N/A')}")
        print(f"   Key: {field.get('field_key', 'N/A')}")
        print(f"   Type: {field.get('field_type', 'N/A')}")
        
        if field.get('coordinates'):
            coords = field['coordinates']
            print(f"   📍 Coordinates: [{coords[0]:.2f}, {coords[1]:.2f}, {coords[2]:.2f}, {coords[3]:.2f}]")
        else:
            print(f"   📍 Coordinates: Not found")
        
        if field.get('span'):
            span = field['span']
            print(f"   📏 Span: offset={span['offset']}, length={span['length']}")
        else:
            print(f"   📏 Span: Not found")
        
        if field.get('page_number'):
            print(f"   📄 Page: {field['page_number']}")
        print()
    
    if len(fields) > 10:
        print(f"... and {len(fields) - 10} more fields\n")
    
    return llm_fields, docling_json


if __name__ == "__main__":
    try:
        llm_fields, docling_json = main()
        
        print(f"{'='*70}")
        if llm_fields:
            print("✅ EXTRACTION COMPLETED SUCCESSFULLY")
        else:
            print("⚠️ EXTRACTION FAILED")
        print(f"{'='*70}\n")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    
    except Exception as e:
        print(f"\n{'='*70}")
        print("❌ FATAL ERROR")
        print(f"{'='*70}")
        print(f"Error: {e}\n")
        import traceback
        traceback.print_exc()
