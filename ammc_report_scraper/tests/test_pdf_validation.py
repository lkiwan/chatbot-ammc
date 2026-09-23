"""Tests for PDF validation and hashing utilities."""
import hashlib
import tempfile
from pathlib import Path

import pytest

from src.downloaders.pdf_downloader import PDFDownloader
from src.utils.hashing import sha256_file, sha256_bytes


_VALID_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type /Pages /Count 1 /Kids [3 0 R]>>endobj\n"
    b"3 0 obj<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n"
    b"trailer<</Size 4 /Root 1 0 R>>\n"
    b"startxref\n9\n%%EOF"
)


class TestPDFValidation:
    def test_invalid_magic_bytes(self):
        # File must be > MIN_FILE_SIZE (1024) to reach the magic bytes check
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"NOT A PDF - " + b"X" * 1100)
            path = Path(f.name)
        try:
            err = PDFDownloader._validate_pdf(path)
            assert err is not None
            assert "magic" in err.lower() or "invalid" in err.lower()
        finally:
            path.unlink(missing_ok=True)

    def test_nonexistent_file(self):
        err = PDFDownloader._validate_pdf(Path("/nonexistent/file.pdf"))
        assert err is not None

    def test_too_small_file(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF")
            path = Path(f.name)
        try:
            err = PDFDownloader._validate_pdf(path)
            assert err is not None
        finally:
            path.unlink(missing_ok=True)


class TestHashing:
    def test_sha256_bytes(self):
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        assert sha256_bytes(data) == expected

    def test_sha256_file_consistency(self):
        data = b"test content for hashing"
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            path = Path(f.name)
        try:
            file_hash = sha256_file(path)
            bytes_hash = sha256_bytes(data)
            assert file_hash == bytes_hash
        finally:
            path.unlink(missing_ok=True)

    def test_sha256_different_content(self):
        assert sha256_bytes(b"abc") != sha256_bytes(b"def")
