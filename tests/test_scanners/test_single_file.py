"""Tests for single-file scanning via iter_files()."""
import os

import pytest

from ai_bom.scanners.code_scanner import CodeScanner


@pytest.fixture
def scanner():
    return CodeScanner()


class TestSingleFileScanning:
    """Test that iter_files and scan work correctly on individual files."""

    def test_single_python_file_yields(self, scanner, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("import openai\n")
        files = list(scanner.iter_files(f, extensions={".py"}))
        assert len(files) == 1
        assert files[0].name == "app.py"

    def test_single_dependency_file_yields(self, scanner, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("openai>=1.0.0\n")
        files = list(scanner.iter_files(f, filenames={"requirements.txt"}))
        assert len(files) == 1

    def test_single_file_wrong_extension_skipped(self, scanner, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n1,2,3\n")
        files = list(scanner.iter_files(f, extensions={".py"}))
        assert len(files) == 0

    def test_single_file_over_1mb_rejected(self, scanner, tmp_path):
        f = tmp_path / "huge.py"
        # Write just over 1MB
        f.write_bytes(b"# padding\n" * 120_000)
        assert os.path.getsize(f) > 1_048_576
        files = list(scanner.iter_files(f, extensions={".py"}))
        assert len(files) == 0

    def test_single_file_under_1mb_accepted(self, scanner, tmp_path):
        f = tmp_path / "small.py"
        f.write_text("x = 1\n")
        files = list(scanner.iter_files(f, extensions={".py"}))
        assert len(files) == 1

    def test_scan_single_python_file(self, scanner, tmp_path):
        f = tmp_path / "app.py"
        f.write_text('from openai import OpenAI\nclient = OpenAI()\n')
        components = scanner.scan(f)
        names = [c.name.lower() for c in components]
        assert "openai" in names

    def test_scan_single_requirements_file(self, scanner, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("openai>=1.0.0\nlangchain>=0.1.0\n")
        components = scanner.scan(f)
        names = [c.name for c in components]
        assert "openai" in names

    def test_single_file_no_filter_yields(self, scanner, tmp_path):
        """When no extensions/filenames filter is set, any file should yield."""
        f = tmp_path / "something.txt"
        f.write_text("hello\n")
        files = list(scanner.iter_files(f))
        assert len(files) == 1
