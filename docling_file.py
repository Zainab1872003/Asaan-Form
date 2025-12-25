import os
import json
from pathlib import Path
from huggingface_hub import snapshot_download
import cv2
import numpy as np

from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import (
    ConversionResult,
    DocumentConverter,
    InputFormat,
    PdfFormatOption,
)

def process_pdf_with_rapidocr_v5(pdf_path, output_dir="output"):
    """
    Process PDF with RapidOCR using PP-OCRv5 models and export to Markdown and JSON
    
    Args:
        pdf_path: Path to input PDF file
        output_dir: Directory to save outputs
    """
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("Docling PDF Processing with RapidOCR (PP-OCRv5)")
    print("=" * 60)
    
    # Step 1: Download RapidOCR PP-OCRv5 models from HuggingFace
    print("\n[1/5] Downloading PP-OCRv5 models from HuggingFace...")
    download_path = snapshot_download(repo_id="SWHL/RapidOCR")
    print(f"✓ Models downloaded to: {download_path}")
    
    # Step 2: Configure RapidOCR with PP-OCRv5 model paths
    print("\n[2/5] Configuring RapidOCR with PP-OCRv5...")
    
    # PP-OCRv4 server models (PP-OCRv5 path doesn't exist in this repo)
    det_model_path = os.path.join(download_path, "PP-OCRv4", "ch_PP-OCRv4_det_server_infer.onnx")
    rec_model_path = os.path.join(download_path, "PP-OCRv4", "ch_PP-OCRv4_rec_server_infer.onnx")
    cls_model_path = os.path.join(download_path, "PP-OCRv3", "ch_ppocr_mobile_v2.0_cls_train.onnx")
    
    print(f"   Detection: {os.path.basename(det_model_path)}")
    print(f"   Recognition: {os.path.basename(rec_model_path)}")
    
    # Configure OCR options
    ocr_options = RapidOcrOptions(
        det_model_path=det_model_path,
        rec_model_path=rec_model_path,
        cls_model_path=cls_model_path,
    )
    
    # Configure pipeline with OCR and table structure recognition
    pipeline_options = PdfPipelineOptions(
        ocr_options=ocr_options,
        do_ocr=True,
        do_table_structure=True,
        generate_page_images=True,  # Enable page images for visualization
    )
    print("✓ RapidOCR configured")
    
    # Step 3: Initialize DocumentConverter
    print("\n[3/5] Converting document...")
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            ),
        },
    )
    
    # Convert the document
    conversion_result: ConversionResult = converter.convert(source=pdf_path)
    doc = conversion_result.document
    print(f"✓ Document converted successfully")
    print(f"  Pages: {len(doc.pages)}")
    
    # Step 4: Export to Markdown and JSON
    print("\n[4/5] Exporting results...")
    
    # Get base filename
    input_filename = os.path.basename(pdf_path)
    base_name = os.path.splitext(input_filename)[0]
    
    # Export to Markdown
    markdown_path = output_path / f"{base_name}.md"
    with open(markdown_path, 'w', encoding='utf-8') as f:
        f.write(doc.export_to_markdown())
    print(f"✓ Markdown saved: {markdown_path}")
    
    # Export to JSON (complete structure)
    json_path = output_path / f"{base_name}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(doc.export_to_dict(), f, indent=2, ensure_ascii=False)
    print(f"✓ JSON saved: {json_path}")
    
    
    # Step 5: Generate bounding box visualizations
    print("\n[5/5] Generating bounding box visualizations...")
    
    # Use built-in visualization
    try:
        viz_images = doc.get_visualization(
            show_label=True,
            show_branch_numbering=False,
            viz_mode='reading_order'
        )
        
        for page_num, viz_img in viz_images.items():
            viz_path = output_path / f"{base_name}_page_{page_num}_bbox.png"
            viz_img.save(viz_path)
            print(f"✓ Visualization saved: {viz_path}")
    except Exception as e:
        print(f"⚠️  Built-in visualization failed: {e}")
    
    # Extract and save bounding box data
    bbox_data = []
    for page_num, page in doc.pages.items():
        for item, level in doc.iterate_items():
            if hasattr(item, 'prov') and item.prov:
                for prov in item.prov:
                    if hasattr(prov, 'bbox') and prov.bbox:
                        bbox = prov.bbox
                        bbox_data.append({
                            'page': page_num,
                            'label': str(item.label) if hasattr(item, 'label') else 'unknown',
                            'text': str(item.text)[:100] if hasattr(item, 'text') else '',
                            'bbox': [bbox.l, bbox.t, bbox.r, bbox.b]
                        })
    
    bbox_json_path = output_path / f"{base_name}_bboxes.json"
    with open(bbox_json_path, 'w', encoding='utf-8') as f:
        json.dump(bbox_data, f, indent=2, ensure_ascii=False)
    print(f"✓ Bounding boxes saved: {bbox_json_path}")
    print(f"  Total bounding boxes: {len(bbox_data)}")
    
    print("\n" + "=" * 60)
    print("✅ Processing Complete!")
    print("=" * 60)
    
    return {
        'markdown': str(markdown_path),
        'json': str(json_path),
        # 'structure': str(structure_path),
        'bbox_json': str(bbox_json_path),
        'total_bboxes': len(bbox_data),
        'doc': doc
    }

if __name__ == "__main__":
    # Example usage
    pdf_file = "form.pdf"  # Works with both PDF and images
    
    if not Path(pdf_file).exists():
        print(f"❌ Error: File '{pdf_file}' not found!")
        exit(1)
    
    result = process_pdf_with_rapidocr_v5(pdf_file, output_dir="output")
    
    print(f"\n📄 Outputs:")
    print(f"  Markdown: {result['markdown']}")
    print(f"  JSON: {result['json']}")
    print(f"  Structure: {result['structure']}")
    print(f"  Bounding Boxes: {result['bbox_json']}")
    print(f"  Total Bboxes: {result['total_bboxes']}")
