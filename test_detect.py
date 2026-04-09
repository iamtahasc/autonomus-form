import sys
from src.parser import PDFParser
from src.analyzer import FormAnalyzer

def main():
    p = PDFParser('dummy_form.pdf')
    t, v = p.parse_page(0)
    a = FormAnalyzer(t, v)
    
    # print line visual elements
    print("--- Lines in visual elements ---")
    for ve in v:
        if ve.type == 'line':
            print(f"Line: {ve.bbox}, width={ve.bbox[2]-ve.bbox[0]}, height={ve.bbox[3]-ve.bbox[1]}")
            
    a.detect_candidates()
    print("--- Detected Fields ---")
    for f in a.get_fields():
        print(f.type.value, f.bbox, f.label)

if __name__ == "__main__":
    main()
