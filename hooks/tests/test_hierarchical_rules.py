"""Tests for hierarchical_rules module."""
import sys
from pathlib import Path

import pytest

from hooks.handlers.hierarchical_rules import (
    parse_frontmatter,
)
from hooks.hook_sdk import Patterns


class TestParseFrontmatter:
    """Tests for YAML frontmatter parsing."""

    def test_parse_with_frontmatter(self):
        """Should parse frontmatter and content."""
        content = """---
paths: src/**/*.ts
---
# Rules
- Rule 1
- Rule 2
"""
        frontmatter, remaining = parse_frontmatter(content)
        assert frontmatter.get("paths") == "src/**/*.ts"
        assert "# Rules" in remaining

    def test_parse_without_frontmatter(self):
        """Should handle content without frontmatter."""
        content = """# Just content
- No frontmatter here
"""
        frontmatter, remaining = parse_frontmatter(content)
        assert frontmatter == {}
        assert "# Just content" in remaining

    def test_parse_empty_frontmatter(self):
        """Should handle empty frontmatter."""
        content = """---
---
# Content
"""
        frontmatter, remaining = parse_frontmatter(content)
        assert frontmatter == {}
        assert "# Content" in remaining


class TestMatchesPathPattern:
    """Tests for glob pattern matching."""

    def test_double_star_matches_deep(self):
        """** should match multiple directories."""
        assert Patterns.matches_path_pattern("src/a/b/c/file.ts", "**/*.ts") is True

    def test_single_star_no_slash(self):
        """* should not match slashes."""
        assert Patterns.matches_path_pattern("src/file.ts", "*.ts") is False
        assert Patterns.matches_path_pattern("file.ts", "*.ts") is True

    def test_specific_directory(self):
        """Should match specific directory patterns."""
        assert Patterns.matches_path_pattern("src/api/users.ts", "src/**/*.ts") is True
        assert Patterns.matches_path_pattern("lib/utils.ts", "src/**/*.ts") is False

    def test_brace_expansion(self):
        """Should expand {a,b} patterns."""
        assert Patterns.matches_path_pattern("src/file.ts", "{src,lib}/*.ts") is True
        assert Patterns.matches_path_pattern("lib/file.ts", "{src,lib}/*.ts") is True
        assert Patterns.matches_path_pattern("other/file.ts", "{src,lib}/*.ts") is False


class TestPatternCaching:
    """Tests for pattern compilation caching."""

    def test_cache_stores_patterns(self):
        """Cache should store compiled patterns."""
        # Clear cache
        Patterns.compile_pattern.cache_clear()

        # First call
        Patterns.compile_pattern("**/*.ts")
        info = Patterns.compile_pattern.cache_info()
        assert info.misses == 1

        # Second call - should hit cache
        Patterns.compile_pattern("**/*.ts")
        info = Patterns.compile_pattern.cache_info()
        assert info.hits == 1

    def test_different_patterns_cached_separately(self):
        """Different patterns should be cached separately."""
        Patterns.compile_pattern.cache_clear()

        Patterns.compile_pattern("**/*.ts")
        Patterns.compile_pattern("**/*.py")
        Patterns.compile_pattern("src/**/*")

        info = Patterns.compile_pattern.cache_info()
        assert info.misses == 3
        assert info.currsize == 3
