from io import BytesIO
from math import isfinite
from threading import Lock

import pypdfium2 as pdfium


# PDFium requires all calls in a process to be serialized.
pdf_lock = Lock()


def is_readable_pdf(source):
    try:
        with pdf_lock, pdfium.PdfDocument(source) as document:
            return len(document) > 0
    except pdfium.PdfiumError:
        return False


def pdf_page_sizes(source):
    try:
        with pdf_lock, pdfium.PdfDocument(source) as document:
            sizes = []
            for index in range(len(document)):
                try:
                    width, height = document.get_page_size(index)
                except pdfium.PdfiumError:
                    width, height = 0, 0
                if not (isfinite(width) and isfinite(height) and min(width, height) > 0):
                    width, height = 595, 842
                sizes.append((width, height))
            return sizes
    except pdfium.PdfiumError:
        return []


def render_pdf_page(source, number):
    try:
        with pdf_lock, pdfium.PdfDocument(source) as document:
            count = len(document)
            if not 1 <= number <= count:
                return None
            page = document[number - 1]
            width, height = page.get_size()
            if not (isfinite(width) and isfinite(height) and min(width, height) > 0):
                return None
            bitmap = page.render(scale=min(3, 1600 / max(width, height)), rev_byteorder=True)
            try:
                image = bitmap.to_pil().copy()
            finally:
                bitmap.close()
    except pdfium.PdfiumError:
        return None

    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue(), count
