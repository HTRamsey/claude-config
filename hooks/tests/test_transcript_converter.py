"""Tests for handlers/transcript_converter.py"""
import os
import tempfile
from pathlib import Path

import pytest


class TestTranscriptConverter:
    """Tests for transcript converter handler."""

    def test_parse_jsonl_empty(self):
        from hooks.handlers.transcript_converter import parse_jsonl
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write("")
            f.flush()
            result = parse_jsonl(Path(f.name))
            assert result == []
            os.unlink(f.name)

    def test_parse_jsonl_valid(self):
        from hooks.handlers.transcript_converter import parse_jsonl
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type": "user", "content": "hello"}\n')
            f.write('{"type": "assistant", "content": "hi"}\n')
            f.flush()
            result = parse_jsonl(Path(f.name))
            assert len(result) == 2
            os.unlink(f.name)

    def test_extract_messages_empty(self):
        from hooks.handlers.transcript_converter import extract_messages
        result = extract_messages([])
        assert result == []

    def test_extract_messages_user(self):
        from hooks.handlers.transcript_converter import extract_messages
        entries = [{"type": "user", "content": "hello", "timestamp": "2024-01-01"}]
        result = extract_messages(entries)
        assert len(result) == 1
        assert result[0]["role"] == "user"
