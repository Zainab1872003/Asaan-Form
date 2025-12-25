from pathlib import Path
from docling.datamodel.pipeline_options import VlmPipelineOptions
from docling.document_converter import DocumentConverter, InputFormat, ImageFormatOption

# VLM pipeline options (different from PdfPipelineOptions)
vlm_options = VlmPipelineOptions(
    do_table_structure=True,
    generate_page_images=True,
)

converter = DocumentConverter(
    format_options={
        InputFormat.IMAGE: ImageFormatOption(
            pipeline_options=vlm_options,
        ),
    },
)

result = converter.convert("form1.png")
doc = result.document

# Save with layout visualization
viz = doc.get_visualization(show_label=True)
for page_num, img in viz.items():
    img.save(f"output/page_{page_num}_viz.png")
