import argparse
import json
import os
import traceback
import logging
from src.parser import PDFParser
from src.analyzer import FormAnalyzer
from src.generator import FormGenerator

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Auto-Form Converter")
    parser.add_argument("input_pdf", help="Path to input non-fillable PDF")
    parser.add_argument(
        "--output", "-o", default="output_form.pdf", help="Path to output fillable PDF"
    )
    parser.add_argument(
        "--json", "-j", default="fields.json", help="Path to output JSON mapping"
    )
    args = parser.parse_args()

    try:
        if not os.path.exists(args.input_pdf):
            logger.error(f"File not found: {args.input_pdf}")
            return

        logger.info(f"Processing {args.input_pdf}...")

        pdf_parser = PDFParser(args.input_pdf)
        all_fields = []
        total_pages = len(pdf_parser.doc)
        logger.info(f"Total pages: {total_pages}")

        for page_num in range(total_pages):
            try:
                logger.info(f"Parsing page {page_num + 1} of {total_pages}...")

                text_elements, visual_elements = pdf_parser.parse_page(page_num)

                logger.info(
                    f"Text elements: {len(text_elements)} | "
                    f"Visual elements: {len(visual_elements)}"
                )

                if not text_elements:
                    logger.warning(
                        f"No text found on page {page_num + 1} — possibly scanned PDF"
                    )

                analyzer = FormAnalyzer(text_elements, visual_elements)
                analyzer.detect_candidates()  # runs deduplicate + filter + associate_labels internally
                fields = analyzer.get_fields()  # returns self.candidates
                all_fields.extend(fields)

                logger.info(f"Fields found on page {page_num + 1}: {len(fields)}")

                for f in fields:
                    logger.debug(
                        f"[FIELD] type={f.type} | "
                        f"label={getattr(f, 'label', None)} | "
                        f"option={getattr(f, 'option_label', None)} | "
                        f"bbox={f.bbox}"
                    )

            except Exception as page_error:
                logger.error(f"Error processing page {page_num + 1}: {page_error}")
                traceback.print_exc()
                # continue to next page
                continue

        pdf_parser.close()
        logger.info(f"Total detected fields: {len(all_fields)}")

        # ── Generate fillable PDF ──────────────────────────────────
        try:
            logger.info("Generating fillable PDF...")

            generator = FormGenerator()

            for f in all_fields:
                logger.debug(
                    f"Generating field → type={f.type} | "
                    f"label={getattr(f, 'label', None)}"
                )

            generator.generate(args.input_pdf, args.output, all_fields)
            logger.info(f"Saved fillable PDF to: {args.output}")

        except Exception as gen_error:
            logger.error(f"Error during PDF generation: {gen_error}")
            traceback.print_exc()

        # ── Save JSON mapping ──────────────────────────────────────
        try:
            output_data = []
            for f in all_fields:
                output_data.append(
                    {
                        "label": getattr(f, "label", None),
                        "option_label": getattr(f, "option_label", None),
                        "display_label": getattr(f, "display_label", None),
                        "type": f.type.value,
                        "page": f.page_num + 1,
                        "bbox": list(f.bbox),
                    }
                )

            with open(args.json, "w") as jf:
                json.dump(output_data, jf, indent=2)

            logger.info(f"Saved JSON mapping to {args.json}")

        except Exception as json_error:
            logger.error(f"Error saving JSON: {json_error}")
            traceback.print_exc()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
