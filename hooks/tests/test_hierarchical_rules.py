"""Tests for hierarchical_rules module."""
import sys
from pathlib import Path

import pytest

from hierarchical_rules import (
    parse_frontmatter,
    matches_path_pattern,
    _compile_glob_pattern,
)


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
        assert matches_path_pattern("src/a/b/c/file.ts", "**/*.ts") is True

    def test_single_star_no_slash(self):
        """* should not match slashes."""
        assert matches_path_pattern("src/file.ts", "*.ts") is False
        assert matches_path_pattern("file.ts", "*.ts") is True

    def test_specific_directory(self):
        """Should match specific directory patterns."""
        assert matches_path_pattern("src/api/users.ts", "src/**/*.ts") is True
        assert matches_path_pattern("lib/utils.ts", "src/**/*.ts") is False

    def test_brace_expansion(self):
        """Should expand {a,b} patterns."""
        assert matches_path_pattern("src/file.ts", "{src,lib}/*.ts") is True
        assert matches_path_pattern("lib/file.ts", "{src,lib}/*.ts") is True
        assert matches_path_pattern("other/file.ts", "{src,lib}/*.ts") is False


class TestPatternCaching:
    """Tests for pattern compilation caching."""

    def test_cache_stores_patterns(self):
        """Cache should store compiled patterns."""
        # Clear cache
        _compile_glob_pattern.cache_clear()
        
        # First call
        _compile_glob_pattern("**/*.ts")
        info = _compile_glob_pattern.cache_info()
        assert info.misses == 1
        
        # Second call - should hit cache
        _compile_glob_pattern("**/*.ts")
        info = _compile_glob_pattern.cache_info()
        assert info.hits == 1

    def test_different_patterns_cached_separately(self):
        """Different patterns should be cached separately."""
        _compile_glob_pattern.cache_clear()
        
        _compile_glob_pattern("**/*.ts")
        _compile_glob_pattern("**/*.py")
        _compile_glob_pattern("src/**/*")
        
        info = _compile_glob_pattern.cache_info()
        assert info.misses == 3
        assert info.currsize == 3
