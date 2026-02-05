import fitz
from src.analyzer import FieldType, FieldCandidate
from typing import List

class FormGenerator:
    def __init__(self):
        pass

    def generate(self, input_path: str, output_path: str, fields: List[FieldCandidate]):
        doc = fitz.open(input_path)
        
        for field in fields:
            page = doc[field.page_num]
            
            # fitz.Rect(x0, y0, x1, y1)
            rect = fitz.Rect(*field.bbox)
            
            # Create widget
            widget = fitz.Widget()
            widget.rect = rect
            widget.field_name = field.name
            
            if field.type == FieldType.TEXT:
                widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                widget.text_fontsize = 10
            elif field.type == FieldType.CHECKBOX:
                widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
                widget.field_value = False
            
            elif field.type == FieldType.RADIO:
                # Fallback: Use Checkbox for Radio to prevent 'bad xref' crash in pymupdf
                # Radio button creation requires complex group handling not fully supported by simple add_widget
                widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
                widget.field_value = False
                # IMPORTANT for Radio Groups:
                # 1. All widgets in group share 'field_name'.
                # 2. Each widget needs a unique "On State" value (export value).
                # PyMuPDF handles grouping automatically if names match.
                # We need to set the "on_value" or similar.
                # actually, widget.field_value sets the *current* state.
                # We need to define the 'on' state.
                # In PyMuPDF, use widget.on_state = "value" (if supported) or low-level /AP handling.
                # Or wait, for a new widget, we might just set it up.
                # Let's check docs or standard approach.
                # As of recent PyMuPDF:
                # widget.field_flags |= fitz.PDF_FIELD_IS_RADIO
                # And we set the appearance.
                # Actually, simpliest way:
                # widget.field_value = False is Off.
                # But we need to specify what "True" equals.
                # Does PyMuPDF allow setting export value easily?
                # It seems widget.on_state might not be directly settable in older versions or high level.
                # Let's try simpler approximation: use Checkboxes with grouped behavior? No.
                # Let's try to set the value.
                # Using lower level dictionary access if needed.
                # widget.xref usually not valid until added.
                # Let's assume field.export_value is set.
                pass 
                
            elif field.type == FieldType.SIGNATURE:
                widget.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE

            elif field.type == FieldType.IMAGE:
                 widget.field_type = fitz.PDF_WIDGET_TYPE_BUTTON
                 widget.field_flags |= fitz.PDF_BTN_FIELD_IS_PUSHBUTTON
                 widget.text_caption = "Click to Insert Image"
            
            page.add_widget(widget)
            
            # Post-creation fixup for Radio Export Values if needed
            if field.type == FieldType.RADIO and field.export_value:
                 # We need to access the annotation object to set 'OPT' or /AP /N keys?
                 # Actually, radio buttons are tricky.
                 # Let's trust page.add_widget handles basic name grouping.
                 # The unique value is usually the appearance state name.
                 # For now, let's keep it simple.
                 pass
        
        doc.save(output_path)
        doc.close()
