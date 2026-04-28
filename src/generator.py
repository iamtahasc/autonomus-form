import re
import fitz
from collections import defaultdict
from src.analyzer import FieldType, FieldCandidate
from typing import List


class FormGenerator:
    def __init__(self):
        pass

    def _is_char_box(self, field) -> bool:
        """Returns True if this is a single-character input box."""
        w = field.bbox[2] - field.bbox[0]
        h = field.bbox[3] - field.bbox[1]
        return field.type == FieldType.TEXT and 6 < w < 45 and 6 < h < 45

    def _make_base_name(self, field) -> str:
        """Generate label-based unique name for the field."""
        # Try to get a meaningful name from label
        label = field.label or field.option_label or field.display_label or ""
        
        if label:
            # Clean the label to make it snake_case
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', label.strip())
            clean_name = re.sub(r'_+', '_', clean_name)
            base_name = clean_name.strip('_').lower()
            if not base_name:
                base_name = 'field'
        else:
            # Fallback to coordinate-based name if no label
            base_name = (
                f"field"
                f"_p{field.page_num}"
                f"_x{int(field.bbox[0])}"
                f"_y{int(field.bbox[1])}"
            )
        
        return base_name

    def generate(self, input_path: str, output_path: str, fields: List[FieldCandidate]):
        doc = fitz.open(input_path)

        # ── Step 1: Assign unique names to ALL fields first ────────────
        used_names: set = set()
        field_names: dict = {}  # id(field) → unique_name

        for field in fields:
            base = self._make_base_name(field)
            unique = base
            counter = 2
            while unique in used_names:
                unique = f"{base}_{counter}"
                counter += 1
            used_names.add(unique)
            field_names[id(field)] = unique

        # ── Step 2: Group char boxes into rows for auto-advance ────────
        # Key: (page_num, rounded_y_center) — groups boxes on same row
        # IMPORTANT: use field.page_num which must be the real page index
        rows: dict = defaultdict(list)

        for field in fields:
            if not self._is_char_box(field):
                continue
            # round y-center to nearest 5px to group same-row boxes
            y_center = (field.bbox[1] + field.bbox[3]) / 2
            row_key = (field.page_num, round(y_center / 5) * 5)
            rows[row_key].append(field)

        # sort each row left to right by x position
        for key in rows:
            rows[key].sort(key=lambda f: f.bbox[0])

        # map each char field → name of the NEXT field in its row
        next_name_map: dict = {}  # id(field) → next_unique_name
        for row_fields in rows.values():
            if len(row_fields) < 2:
                # single box in row — no auto-advance needed
                continue
            for i, field in enumerate(row_fields):
                if i + 1 < len(row_fields):
                    next_field = row_fields[i + 1]
                    next_name_map[id(field)] = field_names[id(next_field)]

        # ── Step 3: Create widgets ─────────────────────────────────────
        for field in fields:
            try:
                page = doc[field.page_num]
                rect = fitz.Rect(*field.bbox)

                if rect.is_empty or rect.is_infinite:
                    continue

                widget = fitz.Widget()
                widget.rect = rect
                widget.field_name = field_names[id(field)]

                # human readable label as tooltip
                display = field.display_label or field.label or field.option_label or ""
                if display:
                    widget.field_label = display

                if field.type == FieldType.TEXT:
                    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                    widget.text_fontsize = 10
                    widget.field_value = ""

                    if self._is_char_box(field):
                        # ── Single char box ────────────────────────────
                        widget.text_maxlen = 1

                        next_name = next_name_map.get(id(field))

                        if next_name:
                            # auto-advance to next box after typing 1 char
                            widget.script_stroke = "\n".join(
                                [
                                    "var ch = event.change;",
                                    "if (ch && ch.length > 0) {",
                                    "  event.rc = true;",
                                    f' var nf = this.getField("{next_name}");',
                                    "  if (nf) { nf.setFocus(); }",
                                    "}",
                                ]
                            )
                        else:
                            # last box in sequence — just block extra chars
                            widget.script_stroke = "\n".join(
                                [
                                    "if (event.value.length >= 1) {",
                                    "  event.rc = false;",
                                    "}",
                                ]
                            )

                elif field.type in (FieldType.CHECKBOX, FieldType.RADIO):
                    widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
                    widget.field_value = "Off"

                elif field.type == FieldType.SIGNATURE:
                    widget.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE

                elif field.type == FieldType.IMAGE:
                    widget.field_type = fitz.PDF_WIDGET_TYPE_BUTTON
                    widget.field_flags = fitz.PDF_BTN_FIELD_IS_PUSHBUTTON
                    widget.text_caption = "Click to Insert Image"

                else:
                    continue
                print(
                    f"Field: name={widget.field_name} | type={field.type} | page={field.page_num} | bbox={field.bbox}"
                )

                page.add_widget(widget)

            except Exception as field_error:
                print(
                    f"Skipping field '{getattr(field, 'label', None)}' "
                    f"on page {field.page_num}: {field_error}"
                )
                continue

        doc.save(output_path)
        doc.close()
