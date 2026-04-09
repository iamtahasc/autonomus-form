import sys
import glob
from src.parser import PDFParser
from src.analyzer import FormAnalyzer

def examine():
    # Pick a sample PDF
    pdf_files = glob.glob('uploads/*Sample.pdf')
    if not pdf_files:
        print("No Sample.pdf found")
        return
        
    f_path = pdf_files[0]
    print(f"Examining {f_path}")
    p = PDFParser(f_path)
    t, v = p.parse_page(0)
    
    a = FormAnalyzer(t, v)
    a.detect_candidates()
    
    fields = a.get_fields()
    
    with open('out7.txt', 'w', encoding='utf-8') as f:
        f.write("Detected Text Fields:\n")
        for field in fields:
            if field.type.value == "text":
                f.write(f"  Field: bbox={field.bbox}, label={field.label}\n")

if __name__ == '__main__':
    examine()
