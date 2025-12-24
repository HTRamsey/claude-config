# /lint

Run linters on current changes or specified files.

**Arguments**: `$ARGUMENTS` - optional file paths or patterns (defaults to changed files)

## Workflow

1. **Detect scope:**
   ```bash
   # If no arguments, get changed files
   git diff --name-only HEAD
   git diff --name-only --cached
   ```

2. **Identify file types and linters:**
   | Extension | Linter |
   |-----------|--------|
   | `.py` | `ruff check` (or `black --check`, `mypy`) |
   | `.ts`, `.tsx`, `.js`, `.jsx` | `eslint` (or `prettier --check`) |
   | `.cpp`, `.c`, `.h`, `.hpp` | `clang-tidy` (or `cppcheck`) |
   | `.rs` | `cargo clippy` |
   | `.go` | `go vet`, `golangci-lint` |
   | `.sh` | `shellcheck` |

3. **Run linters:**
   ```bash
   # Python
   ruff check path/to/file.py

   # TypeScript/JavaScript
   npx eslint path/to/file.ts

   # C++
   clang-tidy path/to/file.cpp

   # Rust
   cargo clippy

   # Shell
   shellcheck path/to/script.sh
   ```

4. **Report findings:**
   | Severity | File:Line | Issue |
   |----------|-----------|-------|
   | error | src/foo.py:42 | Undefined variable |
   | warning | src/bar.ts:10 | Unused import |

## Examples

```
/lint
→ Lints all changed files

/lint src/auth/
→ Lints all files in src/auth/

/lint *.py
→ Lints all Python files
```

Example output:
```
## Lint Results

Checked 5 files (3 Python, 2 TypeScript)

| Severity | File:Line | Issue |
|----------|-----------|-------|
| error | auth.py:42 | `user` is undefined |
| warning | api.ts:15 | Unused import `axios` |

2 issues found (1 error, 1 warning)
```

## Should NOT Do
- Auto-fix issues without asking (use `--fix` variants only if requested)
- Install missing linters automatically
- Modify linter configurations
- Lint files not in scope (entire codebase unless asked)

## When to Bail
- No linter available for file type (suggest installation)
- Linter config is missing and required
- Too many files to lint (>100, ask to narrow scope)

## Escalation
- For complex lint errors suggesting design issues → `code-reviewer` agent
- For security-related lint findings → `security-reviewer` agent

## Rules
- Use project's existing linter config if present
- Prefer fast linters (ruff over pylint, eslint over tsc)
- Group output by file for readability
- Show command used so user can re-run
