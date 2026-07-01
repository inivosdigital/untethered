#!/usr/bin/env python3
"""Unit tests for resume ingestion + canonical cleaning."""
import io
import os
import tempfile
import unittest

from reframe import ingest


class CleanText(unittest.TestCase):
    def test_normalizes_newlines(self):
        self.assertEqual(ingest.clean_text("a\r\nb\rc"), "a\nb\nc")

    def test_strips_bom_and_zero_width(self):
        # BOM + zero-width space embedded in a token must vanish
        self.assertEqual(ingest.clean_text("\ufeffAR\u200banalyst"), "ARanalyst")

    def test_folds_nbsp_to_space(self):
        # non-breaking and narrow NBSP both fold to a space
        self.assertEqual(ingest.clean_text("30\u00a0/\u202fhr"), "30 / hr")

    def test_rstrips_lines_preserving_count(self):
        cleaned = ingest.clean_text("a   \nb\t\n\n")
        self.assertEqual(cleaned, "a\nb\n\n")
        self.assertEqual(cleaned.count("\n"), 3)

    def test_none_is_empty(self):
        self.assertEqual(ingest.clean_text(None), "")


class LoadResume(unittest.TestCase):
    def test_from_path(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("Title\r\nSummary line")
            path = f.name
        try:
            self.assertEqual(ingest.load_resume(path), "Title\nSummary line")
        finally:
            os.unlink(path)

    def test_from_handle(self):
        self.assertEqual(ingest.load_resume(io.StringIO("x\r\ny")), "x\ny")

    def test_from_stdin(self):
        import sys
        saved = sys.stdin
        sys.stdin = io.StringIO("piped\r\nresume")
        try:
            self.assertEqual(ingest.load_resume("-"), "piped\nresume")
        finally:
            sys.stdin = saved


class LazyFormats(unittest.TestCase):
    def test_pdf_without_lib_or_bad_file_raises_ingest_error(self):
        # pypdf is not installed under system python; either the missing-lib or
        # the bad-file branch must raise IngestError with a hint and no content.
        with self.assertRaises(ingest.IngestError) as cm:
            ingest.load_resume("/nonexistent/whatever.pdf")
        self.assertEqual(cm.exception.fmt, "pdf")
        self.assertIn("pdf", str(cm.exception))

    def test_docx_error_carries_no_resume_content(self):
        with self.assertRaises(ingest.IngestError) as cm:
            ingest.load_resume("/nonexistent/whatever.docx")
        self.assertEqual(cm.exception.fmt, "docx")


class ReviewRegressions(unittest.TestCase):
    def test_directory_path_raises_ingest_error_without_path(self):
        # finding #6: an OS error (directory) must be wrapped, not escape raw,
        # and the message must not leak the (name-bearing) path.
        with tempfile.TemporaryDirectory() as d:
            named = os.path.join(d, "Jane_Doe_Resume")
            os.mkdir(named)
            with self.assertRaises(ingest.IngestError) as cm:
                ingest.load_resume(named)
        self.assertEqual(cm.exception.fmt, "text")
        self.assertNotIn("Jane_Doe", str(cm.exception))

    def test_bytes_handle_is_decoded(self):
        # finding #7: a binary handle must not blow up clean_text with a TypeError.
        self.assertEqual(ingest.load_resume(io.BytesIO(b"a\r\nb")), "a\nb")


if __name__ == "__main__":
    unittest.main()
