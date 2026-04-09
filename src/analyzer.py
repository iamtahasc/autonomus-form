from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
import math
import re
from src.parser import TextElement, VisualElement


class FieldType(Enum):
    TEXT = "text"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SIGNATURE = "signature"
    IMAGE = "image"


@dataclass
class FieldCandidate:
    type: FieldType
    bbox: tuple
    page_num: int
    label: str | None = None
    option_label: str | None = None
    display_label: str | None = None
    name: str | None = None


class FormAnalyzer:
    def __init__(
        self, text_elements: List[TextElement], visual_elements: List[VisualElement]
    ):
        self.text_elements = text_elements
        self.visual_elements = visual_elements
        self.candidates: List[FieldCandidate] = []

    def detect_candidates(self):
        """Detect potential fields based on visual primitives with improved heuristics."""

        sequence_boxes = self._find_sequence_boxes()

        for v in self.visual_elements:
            width = v.bbox[2] - v.bbox[0]
            height = v.bbox[3] - v.bbox[1]

            # ─────────────────────────────
            # 1. Lines → Text fields
            # ─────────────────────────────
            if width > 20 and height < 8:
                field_height = 20
                field_bbox = (
                    v.bbox[0],
                    v.bbox[1] - field_height,
                    v.bbox[2],
                    v.bbox[3] + 2,
                )

                group_lbl, _ = self._find_label(
                    field_bbox, v.page_num, field_type=FieldType.TEXT
                )

                self.candidates.append(
                    FieldCandidate(
                        FieldType.TEXT, field_bbox, v.page_num, label=group_lbl
                    )
                )

            # ─────────────────────────────
            # 2. Rectangles / Boxes
            # ─────────────────────────────
            elif v.type in ["rect", "path", "curve"]:

                ratio = width / (height + 0.001)

                # 2.1 Large boxes → IMAGE
                if width > 60 and height > 60:
                    if width < 550 and height < 750 and 0.2 < ratio < 5.0:
                        if self._has_text_over(v.bbox, v.page_num):
                            continue

                        group_lbl, _ = self._find_label(
                            v.bbox, v.page_num, field_type=FieldType.IMAGE
                        )

                        self.candidates.append(
                            FieldCandidate(
                                FieldType.IMAGE, v.bbox, v.page_num, label=group_lbl
                            )
                        )

                # 2.2 Wide boxes → TEXT
                elif 20 < width < 500 and 10 < height < 60:
                    if self._has_text_over(v.bbox, v.page_num):
                        continue

                    group_lbl, _ = self._find_label(
                        v.bbox, v.page_num, field_type=FieldType.TEXT
                    )

                    self.candidates.append(
                        FieldCandidate(
                            FieldType.TEXT, v.bbox, v.page_num, label=group_lbl
                        )
                    )

                # 2.3 Small square → CHECKBOX / RADIO / TEXT sequence
                elif 6 < width < 45 and 6 < height < 45:

                    # square-ish
                    if 0.6 < ratio < 1.4:

                        # 🔥 sequence detection (OTP / char boxes)
                        if id(v) in sequence_boxes:
                            if self._has_text_over(v.bbox, v.page_num):
                                continue

                            group_lbl, _ = self._find_label(
                                v.bbox, v.page_num, field_type=FieldType.TEXT
                            )

                            self.candidates.append(
                                FieldCandidate(
                                    FieldType.TEXT, v.bbox, v.page_num, label=group_lbl
                                )
                            )

                        else:
                            # real checkbox / radio
                            f_type = (
                                FieldType.RADIO
                                if v.type == "curve"
                                else FieldType.CHECKBOX
                            )

                            if self._has_text_over(v.bbox, v.page_num):
                                continue

                            group_lbl, opt_lbl = self._find_label(
                                v.bbox, v.page_num, field_type=f_type
                            )

                            self.candidates.append(
                                FieldCandidate(
                                    f_type,
                                    v.bbox,
                                    v.page_num,
                                    label=group_lbl,
                                    option_label=opt_lbl,
                                )
                            )

                    # 2.4 small rectangle → TEXT (initials etc.)
                    elif ratio > 1.5:
                        if self._has_text_over(v.bbox, v.page_num):
                            continue

                        group_lbl, _ = self._find_label(
                            v.bbox, v.page_num, field_type=FieldType.TEXT
                        )

                        self.candidates.append(
                            FieldCandidate(
                                FieldType.TEXT, v.bbox, v.page_num, label=group_lbl
                            )
                        )

        # ─────────────────────────────
        # Post processing
        # ─────────────────────────────
        if hasattr(self, "_detect_line_clusters"):
            self._detect_line_clusters()

        if hasattr(self, "_detect_curve_clusters"):
            self._detect_curve_clusters()

        self._detect_dotted_lines()

        if hasattr(self, "_detect_large_boxes"):
            self._detect_large_boxes()

        if self._detect_form_style() == "underline":
            self._merge_line_segments()

        self._deduplicate_candidates()
        self._filter_text_overlaps()
        self.associate_labels()

    def _find_sequence_boxes(self) -> set:
        """
        A box is part of a TEXT sequence only if:
        - It has at least one direct neighbour box within 35px gap
        - No meaningful text sits between them
        - They are on the same vertical band (center diff < 5px)

        A single isolated box = CHECKBOX (never a text sequence).
        """
        sequence_ids = set()

        small_boxes = [
            v
            for v in self.visual_elements
            if v.type in ["rect", "path", "curve"]
            and 6 < (v.bbox[2] - v.bbox[0]) < 45
            and 6 < (v.bbox[3] - v.bbox[1]) < 45
            and (v.bbox[2] - v.bbox[0]) / ((v.bbox[3] - v.bbox[1]) + 0.001) > 0.6
        ]

        # Build adjacency: for each box, find all valid right-neighbours
        adjacency: dict[int, list] = {id(v): [] for v in small_boxes}

        for v in small_boxes:
            for other in small_boxes:
                if other is v or other.page_num != v.page_num:
                    continue

                ow = other.bbox[2] - other.bbox[0]
                oh = other.bbox[3] - other.bbox[1]
                oratio = ow / (oh + 0.001)

                if not (6 < ow < 45 and 6 < oh < 45 and 0.6 < oratio < 1.4):
                    continue

                right_gap = other.bbox[0] - v.bbox[2]
                v_center = (v.bbox[1] + v.bbox[3]) / 2
                o_center = (other.bbox[1] + other.bbox[3]) / 2

                # must be to the right and on same row
                if not (0 < right_gap < 35 and abs(v_center - o_center) < 5):
                    continue

                # no real text between them
                text_between = any(
                    t.page_num == v.page_num
                    and t.bbox[0] > v.bbox[2]
                    and t.bbox[2] < other.bbox[0]
                    and len(t.text.strip()) > 2
                    and not t.text.strip().isdigit()
                    for t in self.text_elements
                )

                if not text_between:
                    adjacency[id(v)].append(id(other))

        # ── Key fix: a box is a sequence member ONLY if it has ──────────
        # at least one neighbour AND that neighbour also has it as neighbour
        # i.e. both sides of a pair must agree — prevents single boxes
        # from being pulled into a sequence by a distant unrelated box
        for v in small_boxes:
            neighbours = adjacency[id(v)]
            if not neighbours:
                # isolated box — always a checkbox, never text sequence
                continue

            for other in small_boxes:
                if id(other) not in neighbours:
                    continue
                # other must also see v as a neighbour (mutual adjacency)
                if id(v) in adjacency[id(other)] or id(other) in adjacency[id(v)]:
                    sequence_ids.add(id(v))
                    sequence_ids.add(id(other))

        # ── Final check: sequence must have 2+ boxes ────────────────────
        # Remove any box that ended up alone (shouldn't happen but safety net)
        # Count how many sequence members share the same row on the same page
        from collections import defaultdict

        row_groups: dict = defaultdict(set)

        for v in small_boxes:
            if id(v) not in sequence_ids:
                continue
            # group by page + rounded y-center (same row = within 5px)
            v_center = round((v.bbox[1] + v.bbox[3]) / 2 / 5) * 5
            key = (v.page_num, v_center)
            row_groups[key].add(id(v))

        # only keep boxes that are in a group of 2 or more
        valid_sequence_ids = set()
        for key, group in row_groups.items():
            if len(group) >= 2:
                valid_sequence_ids.update(group)

        return valid_sequence_ids

    def _has_text_over(self, bbox, page_num) -> bool:
        """
        BUG FIX 2: Returns True if any text element significantly overlaps
        the given bbox (meaning content is already rendered inside the box —
        don't place a label on top of it).
        """
        x1, y1, x2, y2 = bbox
        for t in self.text_elements:
            if t.page_num != page_num:
                continue
            tx1, ty1, tx2, ty2 = t.bbox
            # Check for meaningful overlap (>50% of text width inside box)
            overlap_x = max(0, min(tx2, x2) - max(tx1, x1))
            text_width = tx2 - tx1 + 0.001
            if overlap_x / text_width > 0.5 and ty1 >= y1 and ty2 <= y2 + 4:
                return True
        return False

    def _detect_form_style(self) -> str:
        """
        Detect whether this page uses:
        - 'underline'
        - 'box'
        Returns 'underline' or 'box'
        """
        line_count = sum(
            1
            for v in self.visual_elements
            if (v.bbox[2] - v.bbox[0]) > 20
            and (v.bbox[3] - v.bbox[1]) < 8
        )
        box_count = sum(
            1
            for v in self.visual_elements
            if v.type in ["rect", "path"]
            and 6 < (v.bbox[2] - v.bbox[0]) < 500
            and 6 < (v.bbox[3] - v.bbox[1]) < 60
        )
        return "underline" if line_count > box_count else "box"

    # Working for Boxes Only fields
    # def _find_label(
    #     self, bbox, page_num, field_type=None
    # ) -> tuple[str | None, str | None]:
    #     x1, y1, x2, y2 = bbox
    #     is_checkbox = field_type in (FieldType.CHECKBOX, FieldType.RADIO)

    #     ABOVE_GAP = 40
    #     LEFT_MAX = 250 if is_checkbox else 80
    #     RIGHT_MAX = 100
    #     FALLBACK_LEFT = 300

    #     group_label: str | None = None
    #     option_label: str | None = None
    #     best_group_dist = float("inf")
    #     best_option_dist = float("inf")

    #     field_cy = (y1 + y2) / 2

    #     # ── Main pass: above, left, right ─────────────────────────────
    #     for t in self.text_elements:
    #         if t.page_num != page_num:
    #             continue
    #         tx1, ty1, tx2, ty2 = t.bbox
    #         text = t.text.strip()
    #         if not text:
    #             continue

    #         if tx1 < x2 and tx2 > x1 and ty1 < y2 and ty2 > y1:
    #             continue

    #         text_cy = (ty1 + ty2) / 2

    #         # 1. ABOVE
    #         if ty2 <= y1 and (y1 - ty2) <= ABOVE_GAP:
    #             if tx1 < x2 + 10 and tx2 > x1 - 10:
    #                 dist = y1 - ty2
    #                 if dist < best_group_dist:
    #                     best_group_dist = dist
    #                     group_label = text

    #         # 2. LEFT
    #         if tx2 <= x1 and (x1 - tx2) <= LEFT_MAX:
    #             if abs(field_cy - text_cy) <= 8:
    #                 dist = x1 - tx2
    #                 if is_checkbox:
    #                     looks_like_label = (
    #                         text.endswith(":")
    #                         or len(text) > 15
    #                         or bool(
    #                             re.search(
    #                                 r"(belongs|tick|please|applicant|type|mode|"
    #                                 r"holding|income|status|occupation|proof|copy|"
    #                                 r"nominee|compliant|relationship|payment|account)",
    #                                 text,
    #                                 re.I,
    #                             )
    #                         )
    #                     )
    #                     if looks_like_label and dist < best_group_dist:
    #                         best_group_dist = dist
    #                         group_label = text
    #                 else:
    #                     if dist < best_group_dist:
    #                         best_group_dist = dist
    #                         group_label = text

    #         # 3. RIGHT (option label for checkboxes)
    #         if is_checkbox and tx1 >= x2 and (tx1 - x2) <= RIGHT_MAX:
    #             if abs(field_cy - text_cy) <= 8:
    #                 dist = tx1 - x2
    #                 if dist < best_option_dist:
    #                     best_option_dist = dist
    #                     option_label = text

    #     # ── 4. FALLBACK wide left scan ─────────────────────────────────
    #     # !! MUST be outside the for loop above — was nested inside, causing the crash
    #     if group_label is None and is_checkbox:
    #         for t in self.text_elements:
    #             if t.page_num != page_num:
    #                 continue
    #             tx1, ty1, tx2, ty2 = t.bbox
    #             text = t.text.strip()
    #             if not text:
    #                 continue
    #             text_cy = (ty1 + ty2) / 2

    #             if tx2 <= x1 and (x1 - tx2) <= FALLBACK_LEFT:
    #                 if abs(field_cy - text_cy) <= 8:
    #                     is_label = text.endswith(":") or bool(
    #                         re.search(
    #                             r"(belongs|tick|please|option|specify|type|mode|"
    #                             r"holding|income|status|occupation|proof|copy|"
    #                             r"compliant|nominee|relationship)",
    #                             text,
    #                             re.I,
    #                         )
    #                     )
    #                     if is_label:
    #                         dist = x1 - tx2
    #                         if dist < best_group_dist:
    #                             best_group_dist = dist
    #                             group_label = text

    #     return group_label, option_label

    def _find_label(
        self, bbox, page_num, field_type=None
    ) -> tuple[str | None, str | None]:
        x1, y1, x2, y2 = bbox
        is_checkbox = field_type in (FieldType.CHECKBOX, FieldType.RADIO)

        # ── Adaptive thresholds based on form style ────────────────────
        form_style = self._detect_form_style()

        if form_style == "underline":
            # KYC style — labels inline left, closer to field
            ABOVE_GAP = 40
            LEFT_MAX = 300 if is_checkbox else 150
            RIGHT_MAX = 120
            FALLBACK_LEFT = 400
            VERTICAL_BAND = 10
        else:
            # Box style — JM Financial, labels above or far left
            ABOVE_GAP = 40
            LEFT_MAX = 250 if is_checkbox else 80
            RIGHT_MAX = 100
            FALLBACK_LEFT = 300
            VERTICAL_BAND = 8
        # ──────────────────────────────────────────────────────────────

        group_label: str | None = None
        option_label: str | None = None
        best_group_dist = float("inf")
        best_option_dist = float("inf")
        field_cy = (y1 + y2) / 2

        for t in self.text_elements:
            if t.page_num != page_num:
                continue
            tx1, ty1, tx2, ty2 = t.bbox
            text = t.text.strip()
            if not text:
                continue
            if tx1 < x2 and tx2 > x1 and ty1 < y2 and ty2 > y1:
                continue

            text_cy = (ty1 + ty2) / 2

            # 1. ABOVE
            if ty2 <= y1 and (y1 - ty2) <= ABOVE_GAP:
                if tx1 < x2 + 10 and tx2 > x1 - 10:
                    dist = (y1 - ty2) + 20  # Add penalty so inline left labels win if present
                    if dist < best_group_dist:
                        best_group_dist = dist
                        group_label = text

            # 2. LEFT
            if tx2 <= x1 and (x1 - tx2) <= LEFT_MAX:
                if abs(field_cy - text_cy) <= VERTICAL_BAND:
                    dist = x1 - tx2
                    if is_checkbox:
                        looks_like_label = (
                            text.endswith(":")
                            or len(text) > 15
                            or bool(
                                re.search(
                                    r"(belongs|tick|please|applicant|type|mode|"
                                    r"holding|income|status|occupation|proof|copy|"
                                    r"nominee|compliant|relationship|payment|account|"
                                    r"gender|marital|nationality|residential|address|"
                                    r"kyc|identity)",
                                    text,
                                    re.I,
                                )
                            )
                        )
                        if looks_like_label and dist < best_group_dist:
                            best_group_dist = dist
                            group_label = text
                    else:
                        adjusted_dist = dist
                        if text.endswith(":"):
                            adjusted_dist -= 40
                        if adjusted_dist < best_group_dist:
                            best_group_dist = adjusted_dist
                            group_label = text

            # 3. RIGHT (option label for checkboxes)
            if is_checkbox and tx1 >= x2 and (tx1 - x2) <= RIGHT_MAX:
                if abs(field_cy - text_cy) <= VERTICAL_BAND:
                    dist = tx1 - x2
                    if dist < best_option_dist:
                        best_option_dist = dist
                        option_label = text

        # 4. FALLBACK wide left scan — outside main loop
        if group_label is None and is_checkbox:
            for t in self.text_elements:
                if t.page_num != page_num:
                    continue
                tx1, ty1, tx2, ty2 = t.bbox
                text = t.text.strip()
                if not text:
                    continue
                text_cy = (ty1 + ty2) / 2

                if tx2 <= x1 and (x1 - tx2) <= FALLBACK_LEFT:
                    if abs(field_cy - text_cy) <= VERTICAL_BAND:
                        is_label = text.endswith(":") or bool(
                            re.search(
                                r"(belongs|tick|please|option|specify|type|mode|"
                                r"holding|income|status|occupation|proof|copy|"
                                r"compliant|nominee|relationship|gender|marital|"
                                r"nationality|residential|kyc|identity)",
                                text,
                                re.I,
                            )
                        )
                        if is_label:
                            dist = x1 - tx2
                            if dist < best_group_dist:
                                best_group_dist = dist
                                group_label = text

        return group_label, option_label

    def associate_labels(self):
        """
        Associate text labels with detected field candidates.
        Builds a human-readable display_label from group + option.
        """
        for candidate in self.candidates:
            if candidate.label or candidate.option_label:
                parts = []
                if candidate.label:
                    parts.append(candidate.label.strip())
                if candidate.option_label:
                    parts.append(candidate.option_label.strip())
                candidate.display_label = " — ".join(parts)
                continue

            group_lbl, opt_lbl = self._find_label(
                candidate.bbox, candidate.page_num, field_type=candidate.type
            )

            candidate.label = group_lbl
            candidate.option_label = opt_lbl

            parts = []
            if group_lbl:
                parts.append(group_lbl.strip())
            if opt_lbl:
                parts.append(opt_lbl.strip())
            candidate.display_label = " — ".join(parts) if parts else None

    def _merge_line_segments(self):
        """
        Merges multiple underline segments on the same row into one field.

        KYC forms have patterns like:
        Name*: _______  ___________  ___________  ___________
        These are 4 separate lines but should be ONE text field.

        Rule: if 2+ line-based TEXT candidates are on the same row
        (within 5px vertical), with gaps < 40px between them,
        merge them into a single wider candidate spanning all segments.
        """
        # separate line-based candidates from others
        line_candidates = []
        other_candidates = []

        for c in self.candidates:
            # line-based = tall enough to be a field but thin (underline style)
            h = c.bbox[3] - c.bbox[1]
            w = c.bbox[2] - c.bbox[0]
            is_line_field = (
                c.type == FieldType.TEXT
                and h < 30  # thin = likely from underline
                and w > 20
            )
            if is_line_field:
                line_candidates.append(c)
            else:
                other_candidates.append(c)

        if not line_candidates:
            return

        # group by page + row (y-center within 5px)
        from collections import defaultdict

        rows = defaultdict(list)
        for c in line_candidates:
            y_center = round((c.bbox[1] + c.bbox[3]) / 2 / 5) * 5
            rows[(c.page_num, y_center)].append(c)

        merged = []
        for (page_num, _), group in rows.items():
            if len(group) == 1:
                merged.append(group[0])
                continue

            # sort left to right
            group.sort(key=lambda c: c.bbox[0])

            # check if segments are close enough to merge (gap < 40px)
            # and whether they belong to the same logical field
            current_group = [group[0]]

            for i in range(1, len(group)):
                prev = current_group[-1]
                curr = group[i]
                gap = curr.bbox[0] - prev.bbox[2]

                # check if there is ANY text between prev and curr
                # that looks like a NEW label (not a separator/hint)
                text_label_between = False
                for t in self.text_elements:
                    if t.page_num != page_num:
                        continue
                    tx1, ty1, tx2, ty2 = t.bbox
                    text = t.text.strip()
                    if not text or len(text) < 2:
                        continue
                    # text is between the two segments horizontally
                    if tx1 >= prev.bbox[2] and tx2 <= curr.bbox[0]:
                        y_center_field = (prev.bbox[1] + prev.bbox[3]) / 2
                        text_cy = (ty1 + ty2) / 2
                        if abs(y_center_field - text_cy) < 10:
                            # looks like a label word between segments
                            # e.g. "District" between city and district fields
                            if len(text) > 3 and not re.match(r"^[X\s\(\)]+$", text):
                                text_label_between = True
                                break

                if gap < 40 and not text_label_between:
                    # merge into current group
                    current_group.append(curr)
                else:
                    # finalize current group and start new one
                    merged.append(self._merge_group(current_group))
                    current_group = [curr]

            merged.append(self._merge_group(current_group))

        self.candidates = other_candidates + merged

    # def _merge_group(self, group: list) -> "FieldCandidate":
    #     """Merge a list of FieldCandidates into one spanning bbox."""
    #     if len(group) == 1:
    #         return group[0]

    #     # spanning bbox: leftmost x0, topmost y0, rightmost x1, bottommost y1
    #     x0 = min(c.bbox[0] for c in group)
    #     y0 = min(c.bbox[1] for c in group)
    #     x1 = max(c.bbox[2] for c in group)
    #     y1 = max(c.bbox[3] for c in group)

    #     # use label from first candidate that has one
    #     label = next((c.label for c in group if c.label), None)
    #     option_label = next((c.option_label for c in group if c.option_label), None)
    #     display_label = next((c.display_label for c in group if c.display_label), None)

    #     return FieldCandidate(
    #         type=FieldType.TEXT,
    #         bbox=(x0, y0, x1, y1),
    #         page_num=group[0].page_num,
    #         label=label,
    #         option_label=option_label,
    #         display_label=display_label,
    #     )

    def _merge_group(self, group: list) -> "FieldCandidate":
        if len(group) == 1:
            return group[0]

        x0 = min(c.bbox[0] for c in group)
        y0 = min(c.bbox[1] for c in group)
        x1 = max(c.bbox[2] for c in group)
        y1 = max(c.bbox[3] for c in group)

        # use label from the FIRST segment (leftmost) — it's closest to the label
        first = sorted(group, key=lambda c: c.bbox[0])[0]
        label = first.label
        option_label = first.option_label
        display_label = first.display_label

        # if first segment has no label, try finding one using the merged bbox
        # but search from the leftmost edge only
        if not label:
            label, _ = self._find_label(
                (x0, y0, x1, y1), first.page_num, field_type=FieldType.TEXT
            )

        return FieldCandidate(
            type=FieldType.TEXT,
            bbox=(x0, y0, x1, y1),
            page_num=first.page_num,
            label=label,
            option_label=option_label,
            display_label=display_label,
        )

    def get_fields(self) -> list:
        return self.candidates

    def _detect_dotted_lines(self):
        # Merge small line segments horizontally into one single line candidate,
        # as well as sequences of periods or underscores from text elements.
        small_lines = [
            v for v in self.visual_elements 
            if (v.bbox[2] - v.bbox[0]) <= 20 and (v.bbox[3] - v.bbox[1]) < 8
        ]
        
        # group small lines by page and row (y within 3px)
        from collections import defaultdict
        rows = defaultdict(list)
        for v in small_lines:
            y_center = round((v.bbox[1] + v.bbox[3]) / 2 / 3) * 3
            rows[(v.page_num, y_center)].append(v)
            
        for (page_num, _), group in rows.items():
            if len(group) < 3: # need at least 3 dots to form a line
                continue
                
            group.sort(key=lambda v: v.bbox[0])
            
            # merge segments that are close to each other
            current_cluster = [group[0]]
            for i in range(1, len(group)):
                prev = current_cluster[-1]
                curr = group[i]
                gap = curr.bbox[0] - prev.bbox[2]
                
                # Check for small gaps
                if gap < 15:
                    current_cluster.append(curr)
                else:
                    self._add_dotted_cluster(current_cluster)
                    current_cluster = [curr]
                    
            self._add_dotted_cluster(current_cluster)
            
        # Also detect dotted lines formed by text "......" or "_____"
        for t in self.text_elements:
            text = t.text.strip()
            if len(text) > 4 and set(text).issubset({'.', '_', '-'}):
                # Ignore if it's already covered by a field
                covered = False
                for c in self.candidates:
                    if c.page_num == t.page_num:
                        if (max(c.bbox[0], t.bbox[0]) < min(c.bbox[2], t.bbox[2]) and
                            max(c.bbox[1], t.bbox[1]) < min(c.bbox[3], t.bbox[3])):
                            covered = True
                            break
                if not covered:
                    field_height = 20
                    field_bbox = (
                        t.bbox[0],
                        t.bbox[1] - field_height + (t.bbox[3] - t.bbox[1]),
                        t.bbox[2],
                        t.bbox[3] + 2,
                    )
                    group_lbl, _ = self._find_label(
                        field_bbox, t.page_num, field_type=FieldType.TEXT
                    )
                    self.candidates.append(
                        FieldCandidate(
                            FieldType.TEXT, field_bbox, t.page_num, label=group_lbl
                        )
                    )

    def _add_dotted_cluster(self, cluster):
        if len(cluster) < 3:
            return
            
        x0 = min(v.bbox[0] for v in cluster)
        y0 = min(v.bbox[1] for v in cluster)
        x1 = max(v.bbox[2] for v in cluster)
        y1 = max(v.bbox[3] for v in cluster)
        
        # total width should be > 20
        if x1 - x0 > 20:
            field_height = 20
            field_bbox = (
                x0,
                y0 - field_height,
                x1,
                y1 + 2,
            )
            page_num = cluster[0].page_num
            group_lbl, _ = self._find_label(
                field_bbox, page_num, field_type=FieldType.TEXT
            )
            self.candidates.append(
                FieldCandidate(
                    FieldType.TEXT, field_bbox, page_num, label=group_lbl
                )
            )

    def _deduplicate_candidates(self):
        """
        Remove duplicate candidates that overlap significantly.
        Keeps the one with the more specific type (CHECKBOX > TEXT > IMAGE).
        """
        TYPE_PRIORITY = {
            FieldType.CHECKBOX: 0,
            FieldType.RADIO: 1,
            FieldType.TEXT: 2,
            FieldType.IMAGE: 3,
        }

        def overlap_ratio(a, b):
            ax1, ay1, ax2, ay2 = a.bbox
            bx1, by1, bx2, by2 = b.bbox
            ix1 = max(ax1, bx1)
            iy1 = max(ay1, by1)
            ix2 = min(ax2, bx2)
            iy2 = min(ay2, by2)
            if ix2 <= ix1 or iy2 <= iy1:
                return 0.0
            intersection = (ix2 - ix1) * (iy2 - iy1)
            area_a = max((ax2 - ax1) * (ay2 - ay1), 0.001)
            area_b = max((bx2 - bx1) * (by2 - by1), 0.001)
            return intersection / min(area_a, area_b)

        kept = []
        removed = set()

        for i, a in enumerate(self.candidates):
            if i in removed:
                continue
            for j, b in enumerate(self.candidates):
                if j <= i or j in removed:
                    continue
                if a.page_num != b.page_num:
                    continue
                if overlap_ratio(a, b) > 0.5:
                    # keep the higher-priority (more specific) type
                    pri_a = TYPE_PRIORITY.get(a.type, 99)
                    pri_b = TYPE_PRIORITY.get(b.type, 99)
                    if pri_a <= pri_b:
                        removed.add(j)
                    else:
                        removed.add(i)
                        break
            if i not in removed:
                kept.append(a)

        self.candidates = kept

    def _filter_text_overlaps(self):
        """
        Remove candidates whose bbox is mostly covered by a text element
        (i.e. the box already has static printed content — not a fillable field).
        Also adjust TEXT field bounding boxes so they don't overlap text labels.
        """
        kept_candidates = []
        for candidate in self.candidates:
            x1, y1, x2, y2 = candidate.bbox
            is_covered = False
            
            for t in self.text_elements:
                if t.page_num != candidate.page_num:
                    continue
                tx1, ty1, tx2, ty2 = t.bbox

                # Check vertical overlap
                vertical_overlap = max(0, min(ty2, y2) - max(ty1, y1))
                text_height = ty2 - ty1 + 0.001
                
                # If text does not overlap vertically by at least 30%, ignore it
                if vertical_overlap / text_height < 0.3:
                    continue

                # Check horizontal overlap
                if tx1 < x2 and tx2 > x1:
                    overlap_x = max(0, min(tx2, x2) - max(tx1, x1))
                    text_width = tx2 - tx1 + 0.001

                    # If >40% of the text width overlaps the box horizontally
                    if overlap_x / text_width > 0.4:
                        if candidate.type in (FieldType.CHECKBOX, FieldType.RADIO, FieldType.IMAGE):
                            is_covered = True
                            break
                            
                        # Shrink the box if it's a TEXT field
                        if candidate.type == FieldType.TEXT:
                            center_text = (tx1 + tx2) / 2
                            center_box = (x1 + x2) / 2
                            
                            if center_text < center_box:
                                # Text is on the left, move the left edge of box to right of text
                                x1 = max(x1, tx2 + 2)
                            else:
                                # Text is on the right, move the right edge of box to left of text
                                x2 = min(x2, tx1 - 2)
                                
                            # If remaining width is too small, drop the candidate
                            if x2 - x1 < 15:
                                is_covered = True
                                break

            if not is_covered:
                candidate.bbox = (x1, y1, x2, y2)
                kept_candidates.append(candidate)

        self.candidates = kept_candidates
