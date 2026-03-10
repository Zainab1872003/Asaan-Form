import asyncio
import json
from typing import Dict, List, Optional
from utils.llm import get_llm, generate_response


class FormExtractionService:
    """
    Service to extract form fields using Groq LLM.
    Takes JSON only (no markdown) and identifies form fields with coordinates.
    """
    
    def __init__(self):
        """Initialize the LLM service with Groq."""
        self.llm = get_llm()
        print("✓ LLM initialized (Groq)")
    
    async def extract_fields(
        self, 
        docling_json: Dict
    ) -> Dict:
        """
        Main method: Extract form fields from JSON only (no markdown)
        Filters JSON to only include useful parts (texts and tables with coordinates)
        
        Args:
            docling_json: JSON with bounding boxes from Docling
            
        Returns:
            Dict with:
                - form_fields: List of extracted fields
                - instructions: List of form instructions
                - special_areas: List of special areas (signature, photo, etc.)
        """
        print("🤖 Starting field extraction (JSON only)")
        
        # Filter JSON to only include useful parts (texts and tables)
        filtered_json = self._filter_useful_json(docling_json)
        print("✓ Filtered JSON: extracted only texts and tables with coordinates")
        
        # Split filtered JSON into chunks (LLM has token limits)
        # Increased chunk size since we're not sending markdown anymore
        chunks = self._chunk_json(filtered_json)
        print(f"✓ Split into {len(chunks)} chunks")
        
        # Process each chunk
        all_extractions = []
        for i, chunk in enumerate(chunks, 1):
            print(f"  Processing chunk {i}/{len(chunks)}...")
            
            extraction = await self._extract_from_chunk(
                chunk, 
                i, 
                len(chunks)
            )
            
            if extraction:
                field_count = len(extraction.get('form_fields', []))
                print(f"    ✓ Found {field_count} fields")
                all_extractions.append(extraction)
            else:
                print(f"    ⚠️  Chunk {i} failed")
        
        # Merge all extractions
        merged = self._merge_extractions(all_extractions)
        
        total_fields = len(merged.get('form_fields', []))
        total_instructions = len(merged.get('instructions', []))
        print(f"✓ Total extracted: {total_fields} fields, {total_instructions} instructions")
        
        return merged
    
    def _filter_useful_json(self, json_data: Dict) -> Dict:
        """
        Filter Docling JSON to only include useful parts for form extraction.
        Extracts only texts and tables with their essential data (content, bbox, page_no).
        Removes metadata, references, and structural information that's not needed.
        
        Args:
            json_data: Full Docling JSON output
            
        Returns:
            Filtered JSON with only texts and tables containing:
            - text content
            - bbox (bounding box coordinates)
            - page_number
            - label (if available)
            - charspan (if available)
        """
        filtered = {
            "texts": [],
            "tables": [],
            "metadata": {
                "total_pages": json_data.get("metadata", {}).get("total_pages", 0) if isinstance(json_data.get("metadata"), dict) else 0
            }
        }
        
        # Handle different JSON structures from Docling
        # Combined format (from _combine_jsons)
        if "all_texts" in json_data:
            texts = json_data["all_texts"]
        # Standard Docling format
        elif "texts" in json_data:
            texts = json_data["texts"]
        # Docling main-text format
        elif "main-text" in json_data:
            texts = json_data["main-text"]
        # Handle pages structure (extract texts from all pages)
        elif "pages" in json_data:
            texts = []
            for page in json_data["pages"]:
                if isinstance(page, dict):
                    if "texts" in page:
                        texts.extend(page["texts"])
                    elif "main-text" in page:
                        texts.extend(page["main-text"])
        else:
            texts = []
        
        # Filter texts - only keep essential fields
        for text_item in texts:
            if not isinstance(text_item, dict):
                continue
            
            # Extract useful fields
            filtered_text = {}
            
            # Get text content (could be in different fields based on Docling structure)
            text_content = None
            if "text" in text_item:
                text_content = text_item["text"]
            elif "content" in text_item:
                text_content = text_item["content"]
            elif "value" in text_item:
                text_content = text_item["value"]
            elif "text_content" in text_item:
                text_content = text_item["text_content"]
            
            # Skip if no text content found
            if not text_content or not str(text_content).strip():
                continue
            
            filtered_text["text"] = str(text_content).strip()
            
            # Get bounding box from prov array
            prov = text_item.get("prov", [])
            if prov and isinstance(prov, list) and len(prov) > 0:
                prov_item = prov[0] if isinstance(prov[0], dict) else {}
                bbox = prov_item.get("bbox", {})
                
                # Handle bbox as dict (l, t, r, b format)
                if bbox and isinstance(bbox, dict):
                    filtered_text["bbox"] = {
                        "l": bbox.get("l"),
                        "t": bbox.get("t"),
                        "r": bbox.get("r"),
                        "b": bbox.get("b")
                    }
                # Handle bbox as array [l, t, r, b]
                elif bbox and isinstance(bbox, list) and len(bbox) >= 4:
                    filtered_text["bbox"] = {
                        "l": bbox[0],
                        "t": bbox[1],
                        "r": bbox[2],
                        "b": bbox[3]
                    }
                
                # Get page number
                page_no = prov_item.get("page_no") or prov_item.get("page")
                if page_no is not None:
                    filtered_text["page_number"] = int(page_no)
            
            # Get page number from _page if available (from combined format)
            if "_page" in text_item:
                filtered_text["page_number"] = int(text_item["_page"])
            
            # Get label if available (useful for understanding element type)
            if "label" in text_item:
                filtered_text["label"] = text_item["label"]
            elif "name" in text_item:
                filtered_text["label"] = text_item["name"]
            
            # Get charspan if available (for text spans)
            if "charspan" in text_item:
                filtered_text["charspan"] = text_item["charspan"]
            elif "span" in text_item:
                filtered_text["charspan"] = text_item["span"]
            
            # Only add if we have text content and bbox
            if filtered_text.get("text") and filtered_text.get("bbox"):
                filtered["texts"].append(filtered_text)
        
        # Handle tables if present
        if "tables" in json_data:
            tables = json_data["tables"]
            for table_item in tables:
                if not isinstance(table_item, dict):
                    continue
                
                filtered_table = {}
                
                # Get table content/structure (could be nested)
                table_content = None
                if "table" in table_item:
                    table_content = table_item["table"]
                elif "content" in table_item:
                    table_content = table_item["content"]
                elif "data" in table_item:
                    table_content = table_item["data"]
                elif "cells" in table_item:
                    # Extract table structure from cells
                    cells = table_item.get("cells", [])
                    if cells:
                        table_content = {"cells": cells}
                
                if table_content:
                    filtered_table["table"] = table_content
                
                # Get bounding box
                prov = table_item.get("prov", [])
                if prov and isinstance(prov, list) and len(prov) > 0:
                    prov_item = prov[0] if isinstance(prov[0], dict) else {}
                    bbox = prov_item.get("bbox", {})
                    
                    # Handle bbox as dict
                    if bbox and isinstance(bbox, dict):
                        filtered_table["bbox"] = {
                            "l": bbox.get("l"),
                            "t": bbox.get("t"),
                            "r": bbox.get("r"),
                            "b": bbox.get("b")
                        }
                    # Handle bbox as array
                    elif bbox and isinstance(bbox, list) and len(bbox) >= 4:
                        filtered_table["bbox"] = {
                            "l": bbox[0],
                            "t": bbox[1],
                            "r": bbox[2],
                            "b": bbox[3]
                        }
                    
                    page_no = prov_item.get("page_no") or prov_item.get("page")
                    if page_no is not None:
                        filtered_table["page_number"] = int(page_no)
                
                # Get label if available
                if "label" in table_item:
                    filtered_table["label"] = table_item["label"]
                elif "name" in table_item:
                    filtered_table["label"] = table_item["name"]
                
                # Only add if we have table content and bbox
                if filtered_table.get("table") and filtered_table.get("bbox"):
                    filtered["tables"].append(filtered_table)
        
        return filtered
    
    def _chunk_json(self, json_data: Dict, max_size: int = 20000) -> List[str]:
        """
        Split large JSON into smaller chunks
        
        Args:
            json_data: The docling JSON (can be combined from multiple pages)
            max_size: Maximum characters per chunk
            
        Returns:
            List of JSON string chunks
        """
        json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
        
        # If small enough, return as single chunk
        if len(json_str) <= max_size:
            return [json_str]
        
        chunks = []
        
        # Handle combined multi-page JSON structure
        if isinstance(json_data, dict) and 'all_texts' in json_data:
            # This is our combined format from multiple pages
            texts = json_data['all_texts']
            metadata = json_data.get('metadata', {})
            
            # Calculate how many items per chunk
            num_chunks = max(1, (len(json_str) // max_size) + 1)
            items_per_chunk = max(5, len(texts) // num_chunks)
            
            # Create chunks
            for i in range(0, len(texts), items_per_chunk):
                chunk_texts = texts[i:i + items_per_chunk]
                chunk_data = {
                    'texts': chunk_texts,
                    'metadata': metadata,
                    'chunk_info': f'items {i} to {min(i + items_per_chunk, len(texts))} of {len(texts)}'
                }
                chunks.append(json.dumps(chunk_data, indent=2, ensure_ascii=False))
        
        # Handle single page format with 'texts' array
        elif isinstance(json_data, dict) and 'texts' in json_data:
            texts = json_data['texts']
            metadata = {k: v for k, v in json_data.items() if k != 'texts'}
            
            # Calculate how many items per chunk
            num_chunks = max(1, (len(json_str) // max_size) + 1)
            items_per_chunk = max(5, len(texts) // num_chunks)
            
            # Create chunks
            for i in range(0, len(texts), items_per_chunk):
                chunk_data = {
                    'texts': texts[i:i + items_per_chunk],
                    'metadata': metadata.get('origin', {}),
                    'chunk_info': f'items {i} to {min(i + items_per_chunk, len(texts))}'
                }
                chunks.append(json.dumps(chunk_data, indent=2, ensure_ascii=False))
        
        # Handle page-based structure
        elif isinstance(json_data, dict) and 'pages' in json_data:
            pages = json_data['pages']
            
            for page in pages:
                page_str = json.dumps(page, indent=2, ensure_ascii=False)
                if len(page_str) <= max_size:
                    chunks.append(page_str)
                else:
                    # Split large pages further
                    for i in range(0, len(page_str), max_size):
                        chunks.append(page_str[i:i + max_size])
        
        else:
            # Fallback: simple character split
            for i in range(0, len(json_str), max_size):
                chunks.append(json_str[i:i + max_size])
        
        return chunks if chunks else [json_str]
    
    async def _extract_from_chunk(
        self,
        json_chunk: str,
        chunk_num: int,
        total_chunks: int
    ) -> Optional[Dict]:
        """
        Extract fields from a single chunk using LLM (JSON only, no markdown)
        
        Args:
            json_chunk: This specific JSON chunk
            chunk_num: Current chunk number
            total_chunks: Total number of chunks
            
        Returns:
            Extracted data or None if failed
        """
        prompt = self._build_prompt(json_chunk, chunk_num, total_chunks)
        
        try:
            messages = [
                {"role": "system", "content": "You are a form extraction expert. Extract form fields with precise coordinates and metadata. Always respond with valid JSON."},
                {"role": "user", "content": prompt},
            ]
            content = await asyncio.to_thread(generate_response, self.llm, messages)
            
            # Clean markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 2:
                    content = parts[1].strip()
                    # Remove language identifier if present (e.g., "json\n{...")
                    if content.startswith(("json", "JSON")):
                        content = content[4:].strip()
            
            # Parse JSON
            result = json.loads(content)
            
            # Validate structure
            if not all(k in result for k in ["form_fields", "instructions", "special_areas"]):
                print(f"      ⚠️  Invalid structure in chunk {chunk_num}")
                return None
            
            return result
        
        except json.JSONDecodeError as e:
            print(f"      ❌ JSON parse error: {str(e)[:50]}")
            return None
        except Exception as e:
            print(f"      ❌ Error: {str(e)[:80]}")
            return None
    
    def _build_prompt(
        self,
        json_chunk: str,
        chunk_num: int,
        total_chunks: int
    ) -> str:
        """Build the extraction prompt (JSON only, no markdown)"""
        
        return f"""
You are analyzing a form to extract fillable fields.

**CHUNK {chunk_num} OF {total_chunks}**

**JSON METADATA CHUNK:**
{json_chunk}

**YOUR TASK:**
Extract all form fields from this chunk. For each field:

1. **Identify the field label** (e.g., "Student's Name", "Birth Date", "Address") — the exact text that appears on the form for this field.
2. **CRITICAL — coordinates must match this field**: The "coordinates" [left, top, right, bottom] MUST be the bounding box of **that field's label text only** (e.g. for "Student's Name" use the bbox of the text "Student's Name", not any other label). Wrong coordinates cause values to appear in the wrong box.
3. **Determine field type**:
   - text_input (single line text)
   - textarea (multi-line text)
   - date (date fields)
   - checkbox (checkboxes)
   - signature (signature areas)
   - dropdown (select/dropdown)
   - image_upload (photo/image upload areas)

4. **Extract coordinates from bbox**: [left, top, right, bottom] for **this field's label only**
   Example: {{"l": 59.74, "t": 952.25, "r": 124.59, "b": 938.32}} → [59.74, 952.25, 124.59, 938.32]

5. **Extract span from charspan**: {{"offset": start, "length": end - start}}
   Example: "charspan": [0, 11] → {{"offset": 0, "length": 11}}

6. **Get page_number from prov array**

7. **Determine if required** (usually true for form fields)

8. **Add validation rules** if obvious (e.g., "numeric" for ID numbers)

**ALSO EXTRACT:**
- Form instructions (text that tells user how to fill the form)
- Special areas (signature boxes, photo areas, etc.)

**RESPOND ONLY WITH VALID JSON** in this exact format:
{{
  "form_fields": [
    {{
      "field_name": "Name of Candidate",
      "field_key": "candidate_name",
      "field_type": "text_input",
      "required": true,
      "validation": null,
      "coordinates": [59.74, 952.25, 124.59, 938.32],
      "span": {{"offset": 0, "length": 11}},
      "page_number": 1
    }}
  ],
  "instructions": ["Fill all required fields", "Attach documents"],
  "special_areas": [
    {{
      "type": "image_upload",
      "label": "Paste Photograph",
      "requirements": "passport size",
      "coordinates": [100, 200, 150, 250]
    }}
  ]
}}

Extract ALL fields found in this chunk with complete information.
"""
    
    def _field_sort_key(self, field: Dict) -> tuple:
        """Order by position: page, then top (y), then left (x) for consistent reading order."""
        coords = field.get('coordinates') or [0, 0, 0, 0]
        if len(coords) < 4:
            return (field.get('page_number', 1), 0, 0)
        page = field.get('page_number', 1)
        top = min(coords[1], coords[3])
        left = min(coords[0], coords[2])
        return (page, top, left)

    def _merge_extractions(self, extractions: List[Dict]) -> Dict:
        """
        Merge multiple chunk extractions into one result.
        Removes duplicates based on field_key, then sorts by position (page, top, left)
        so field order matches the form layout and overlay mapping stays correct.
        """
        merged = {
            "form_fields": [],
            "instructions": [],
            "special_areas": []
        }
        
        seen_fields = set()
        seen_instructions = set()
        seen_areas = set()
        
        for extraction in extractions:
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
                area_label = area.get('label', '')
                if area_label and area_label not in seen_areas:
                    seen_areas.add(area_label)
                    merged['special_areas'].append(area)
        
        # Sort by position so overlay draws each value next to the correct label
        merged['form_fields'].sort(key=self._field_sort_key)
        return merged