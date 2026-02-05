from src.parser import PDFParser
from src.analyzer import FormAnalyzer

def debug_analyzer():
    parser = PDFParser("dummy_form.pdf")
    text_elements, visual_elements = parser.parse_page(0)
    parser.close()
    
    analyzer = FormAnalyzer(text_elements, visual_elements)
    analyzer.detect_candidates()
    analyzer.associate_labels()
    
    print(f"--- Detected Fields ({len(analyzer.candidates)}) ---")
    for c in analyzer.candidates:
        if c.name:
            print(f"Field: {c.name:20} Type: {c.type.value:10} BBox: {c.bbox}")

if __name__ == "__main__":
    debug_analyzer()
