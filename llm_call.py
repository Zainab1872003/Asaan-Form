import os
import json
from typing import List, Optional, Union
from pydantic import BaseModel
from groq import Groq
import time
from dotenv import load_dotenv

load_dotenv()


class FormField(BaseModel):
    field_name: str
    field_type: str
    coordinates: List[float]
    span: dict
    required_info: str
    instructions: Optional[str] = None
    confidence: float
    page_number: Optional[int] = None


class FormExtraction(BaseModel):
    fields: List[FormField]


def estimate_tokens(text: str) -> int:
    """Rough token estimation (4 chars per token)"""
    return len(text) // 4


def chunk_json_by_tokens(json_data: Union[dict, list], max_tokens: int = 3000) -> List[dict]:
    """
    Split JSON data into chunks by token count
    
    Args:
        json_data: Full document JSON
        max_tokens: Maximum tokens per chunk
    
    Returns:
        List of JSON chunks
    """
    json_str = json.dumps(json_data, ensure_ascii=False)
    total_tokens = estimate_tokens(json_str)
    
    print(f"📊 Total JSON size: ~{total_tokens:,} tokens")
    print(f"   Target: {max_tokens} tokens per chunk")
    
    # If small enough, return as single chunk
    if total_tokens <= max_tokens:
        print(f"   ✓ JSON fits in single chunk")
        return [json_data]
    
    chunks = []
    num_chunks_needed = (total_tokens // max_tokens) + 1
    
    # Handle different JSON structures
    if isinstance(json_data, dict) and 'pages' in json_data:
        pages = json_data['pages']
        metadata = json_data.get('metadata', {})
        
        # Handle pages as list
        if isinstance(pages, list):
            print(f"   Found {len(pages)} pages in list format")
            items_per_chunk = max(1, len(pages) // num_chunks_needed)
            
            for i in range(0, len(pages), items_per_chunk):
                chunk_pages = pages[i:i + items_per_chunk]
                chunk = {
                    'pages': chunk_pages,
                    'metadata': metadata,
                    'chunk_index': len(chunks) + 1,
                    'total_chunks': 'TBD'
                }
                chunks.append(chunk)
        
        # Handle pages as dict
        elif isinstance(pages, dict):
            print(f"   Found {len(pages)} pages in dict format")
            page_items = list(pages.items())
            items_per_chunk = max(1, len(page_items) // num_chunks_needed)
            
            for i in range(0, len(page_items), items_per_chunk):
                chunk_items = dict(page_items[i:i + items_per_chunk])
                chunk = {
                    'pages': chunk_items,
                    'metadata': metadata,
                    'chunk_index': len(chunks) + 1,
                    'total_chunks': 'TBD'
                }
                chunks.append(chunk)
    
    # Handle JSON as list
    elif isinstance(json_data, list):
        print(f"   JSON is a list with {len(json_data)} items")
        items_per_chunk = max(1, len(json_data) // num_chunks_needed)
        
        for i in range(0, len(json_data), items_per_chunk):
            chunk_items = json_data[i:i + items_per_chunk]
            chunk = {
                'data': chunk_items,
                'chunk_index': len(chunks) + 1,
                'total_chunks': 'TBD'
            }
            chunks.append(chunk)
    
    # Handle JSON as dict (other structures)
    elif isinstance(json_data, dict):
        print(f"   JSON is a dict with {len(json_data)} keys")
        items = list(json_data.items())
        items_per_chunk = max(1, len(items) // num_chunks_needed)
        
        for i in range(0, len(items), items_per_chunk):
            chunk_items = dict(items[i:i + items_per_chunk])
            chunk_items['chunk_index'] = len(chunks) + 1
            chunk_items['total_chunks'] = 'TBD'
            chunks.append(chunk_items)
    
    else:
        # Fallback
        chunks = [json_data]
    
    # Update total_chunks count
    for chunk in chunks:
        if isinstance(chunk, dict) and 'total_chunks' in chunk:
            chunk['total_chunks'] = len(chunks)
    
    # Verify chunk sizes
    for i, chunk in enumerate(chunks):
        chunk_tokens = estimate_tokens(json.dumps(chunk, ensure_ascii=False))
        print(f"   Chunk {i+1}: ~{chunk_tokens} tokens")
        
        # If still too large, split further
        if chunk_tokens > max_tokens * 1.2:  # 20% buffer
            print(f"   ⚠️ Chunk {i+1} still too large, will be truncated")
    
    print(f"   ✓ Created {len(chunks)} JSON chunks")
    return chunks


def extract_form_fields_batch(
    markdown_content: str,
    json_content: dict,
    api_key: str,
    max_json_tokens: int = 3000,
    delay_between_calls: float = 1.0
) -> FormExtraction:
    """
    Extract form fields by processing JSON in chunks while passing full markdown each time
    
    Args:
        markdown_content: Full markdown text (passed to every API call)
        json_content: Full JSON metadata (will be chunked)
        api_key: Groq API key
        max_json_tokens: Maximum tokens for JSON per API call
        delay_between_calls: Delay in seconds between API calls
    
    Returns:
        Aggregated FormExtraction with all fields
    """
    
    client = Groq(api_key=api_key)
    
    # Check markdown size
    md_tokens = estimate_tokens(markdown_content)
    print(f"📊 Markdown size: ~{md_tokens:,} tokens")
    
    # Truncate markdown if too large (leaving room for JSON and prompt)
    max_md_tokens = 1500
    if md_tokens > max_md_tokens:
        print(f"   ⚠️ Markdown too large, truncating to {max_md_tokens} tokens")
        markdown_preview = markdown_content[:max_md_tokens * 4]  # ~4 chars per token
    else:
        markdown_preview = markdown_content
    
    # Split JSON into chunks
    print("\n📦 Chunking JSON data...")
    json_chunks = chunk_json_by_tokens(json_content, max_json_tokens)
    
    print(f"\n🔄 Will process {len(json_chunks)} API calls")
    print(f"{'='*60}\n")
    
    all_fields = []
    
    # Process each JSON chunk with full markdown
    for idx, json_chunk in enumerate(json_chunks, 1):
        print(f"🔍 API Call {idx}/{len(json_chunks)}")
        print(f"   Processing JSON chunk {idx}...")
        
        # Prepare JSON chunk (with size check)
        json_str = json.dumps(json_chunk, indent=2, ensure_ascii=False)
        json_tokens = estimate_tokens(json_str)
        
        # Truncate if still too large
        if json_tokens > max_json_tokens:
            print(f"   ⚠️ Truncating JSON from {json_tokens} to {max_json_tokens} tokens")
            json_str = json_str[:max_json_tokens * 4]
        
        print(f"   Prompt size: ~{estimate_tokens(markdown_preview + json_str)} tokens")
        
        prompt = f"""Extract form fields from this document. You are processing chunk {idx} of {len(json_chunks)}.

**IMPORTANT:** Extract ALL form fields you find in the provided JSON metadata below.

**Required JSON output format:**
{{
  "fields": [
    {{
      "field_name": "Full Name",
      "field_type": "text",
      "coordinates": [100.5, 200.3, 300.7, 220.8],
      "span": {{"offset": 123, "length": 10}},
      "required_info": "User's complete legal name",
      "instructions": null,
      "confidence": 0.95,
      "page_number": 1
    }}
  ]
}}

**Field types:** text, checkbox, radio, dropdown, signature, date, number, email, phone, address, textarea

**Document Markdown (for context):**
{markdown_preview}

**JSON Metadata (Chunk {idx}/{len(json_chunks)}):**
{json_str}

Extract ALL form fields from the JSON metadata above. Return ONLY valid JSON."""

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a form field extraction expert. Extract ALL form fields from the provided JSON metadata and return valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4000
            )
            
            # Parse response
            content = json.loads(response.choices[0].message.content)
            
            # Extract fields
            if 'fields' in content and isinstance(content['fields'], list):
                fields_found = 0
                
                for field_dict in content['fields']:
                    try:
                        # Set page_number if missing
                        if 'page_number' not in field_dict or field_dict['page_number'] is None:
                            field_dict['page_number'] = idx
                        
                        # Validate before creating
                        if validate_field(field_dict):
                            field = FormField(**field_dict)
                            all_fields.append(field)
                            fields_found += 1
                        else:
                            print(f"   ⚠️ Invalid field structure, skipping")
                    
                    except Exception as e:
                        print(f"   ⚠️ Error creating field: {str(e)[:60]}")
                        continue
                
                print(f"   ✅ Extracted {fields_found} fields from chunk {idx}")
            
            else:
                print(f"   ⚠️ No 'fields' array in response")
            
            # Rate limiting delay (not on last chunk)
            if idx < len(json_chunks):
                print(f"   ⏳ Waiting {delay_between_calls}s before next call...\n")
                time.sleep(delay_between_calls)
        
        except Exception as e:
            print(f"   ❌ API Error: {str(e)[:100]}")
            print(f"   Continuing with next chunk...\n")
            continue
    
    print(f"\n{'='*60}")
    print(f"✅ Completed {len(json_chunks)} API calls")
    print(f"✅ Total fields extracted: {len(all_fields)}")
    
    # Remove duplicates
    unique_fields = []
    seen = set()
    
    for field in all_fields:
        # Create unique key from name and approximate position
        coord_key = tuple(round(c, 1) for c in field.coordinates[:2]) if field.coordinates else (0, 0)
        key = (field.field_name.lower().strip(), coord_key)
        
        if key not in seen:
            seen.add(key)
            unique_fields.append(field)
    
    if len(unique_fields) < len(all_fields):
        print(f"🔄 Removed {len(all_fields) - len(unique_fields)} duplicate fields")
    
    print(f"📊 Final unique fields: {len(unique_fields)}")
    
    return FormExtraction(fields=unique_fields)


def validate_field(field_dict: dict) -> bool:
    """Validate field has required structure"""
    required_keys = ['field_name', 'field_type', 'coordinates', 'span', 'required_info', 'confidence']
    
    # Check required keys
    if not all(k in field_dict for k in required_keys):
        return False
    
    # Validate coordinates
    if not isinstance(field_dict['coordinates'], list):
        return False
    if len(field_dict['coordinates']) != 4:
        return False
    
    # Validate span
    if not isinstance(field_dict['span'], dict):
        return False
    if 'offset' not in field_dict['span'] or 'length' not in field_dict['span']:
        return False
    
    # Validate confidence is a number
    try:
        float(field_dict['confidence'])
    except:
        return False
    
    return True


# Main execution
if __name__ == "__main__":
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    
    if not GROQ_API_KEY:
        print("❌ Error: GROQ_API_KEY not found in environment variables")
        print("   Please add GROQ_API_KEY=your_key_here to your .env file")
        exit(1)
    
    # Load files
    try:
        print("📂 Loading files...")
        
        with open("output/form1.md", "r", encoding="utf-8") as f:
            markdown_data = f.read()
        print(f"   ✓ Loaded markdown: {len(markdown_data)} characters")
        
        with open("output/form1.json", "r", encoding="utf-8") as f:
            json_data = json.load(f)
        print(f"   ✓ Loaded JSON")
    
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        exit(1)
    
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON file: {e}")
        exit(1)
    
    # Extract form fields
    try:
        print(f"\n{'='*60}")
        print("🚀 Starting Form Field Extraction")
        print(f"{'='*60}\n")
        
        extraction = extract_form_fields_batch(
            markdown_content=markdown_data,
            json_content=json_data,
            api_key=GROQ_API_KEY,
            max_json_tokens=3000,  # Max 3000 tokens per JSON chunk
            delay_between_calls=1.0  # 1 second delay
        )
        
        # Display results
        print(f"\n{'='*60}")
        print("📊 EXTRACTION RESULTS")
        print(f"{'='*60}\n")
        
        for idx, field in enumerate(extraction.fields, 1):
            print(f"{idx}. {field.field_name}")
            print(f"   Type: {field.field_type}")
            print(f"   Coordinates: {field.coordinates}")
            print(f"   Required: {field.required_info[:70]}...")
            if field.instructions:
                print(f"   Instructions: {field.instructions[:70]}...")
            print(f"   Confidence: {field.confidence:.2f}")
            print(f"   Page/Chunk: {field.page_number or 'N/A'}")
            print()
        
        # Save to file
        output_path = "extracted_fields.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(extraction.model_dump(), f, indent=2, ensure_ascii=False)
        
        print(f"{'='*60}")
        print(f"✅ Extraction complete!")
        print(f"✅ Saved {len(extraction.fields)} fields to {output_path}")
        print(f"{'='*60}")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Extraction interrupted by user")
    
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
