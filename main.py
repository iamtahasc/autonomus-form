import argparse
import json
import os
from src.parser import PDFParser
from src.analyzer import FormAnalyzer
from src.generator import FormGenerator

def main():
    parser = argparse.ArgumentParser(description="Auto-Form Converter")
    parser.add_argument("input_pdf", help="Path to input non-fillable PDF")
    parser.add_argument("--output", "-o", default="output_form.pdf", help="Path to output fillable PDF")
    parser.add_argument("--json", "-j", default="fields.json", help="Path to output JSON mapping")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_pdf):
        print(f"Error: File {args.input_pdf} not found.")
        return

    print(f"Processing {args.input_pdf}...")
    
    # 1. Parse
    pdf_parser = PDFParser(args.input_pdf)
    all_fields = []
    
    # Iterate pages (assuming single page for dummy, but loop for robustness)
    for page_num in range(len(pdf_parser.doc)):
        print(f"Parsing page {page_num + 1}...")
        text_elements, visual_elements = pdf_parser.parse_page(page_num)
        
        if not text_elements:
            print("  [WARNING] No text found on this page! This might be a scanned PDF or image-only.")
            print("            This tool requires text-based PDFs to function correctly.")
        
        # 2. Analyze
        analyzer = FormAnalyzer(text_elements, visual_elements)
        analyzer.detect_candidates()
        analyzer.associate_labels()
        
        fields = analyzer.get_fields()
        all_fields.extend(fields)
        print(f"  Found {len(fields)} fields.")

    pdf_parser.close()
    
    # 3. Generate content
    print("Generating fillable PDF...")
    generator = FormGenerator()
    generator.generate(args.input_pdf, args.output, all_fields)
    print(f"Saved PDF to {args.output}")
    
    # 4. Save JSON
    output_data = []
    for f in all_fields:
        output_data.append({
            "field_name": f.name,
            "label": f.associated_label,
            "type": f.type.value,
            "page": f.page_num + 1,
            "bbox": f.bbox
        })
        
    with open(args.json, "w") as jf:
        json.dump(output_data, jf, indent=2)
    print(f"Saved JSON mapping to {args.json}")

if __name__ == "__main__":
    main()
