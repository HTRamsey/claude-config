---
name: large-file-handling
description: Efficiently work with large files without consuming excessive context. Use for files over 200 lines, large logs, or understanding big codebases.
---

# Large File Handling

**Persona:** Surgical reader - large files are minefields of context waste, extract precisely what's needed.

## Should NOT Attempt

- Read files >200 lines without using limit/offset
- Load entire logs into context
- Skip summarization scripts for large code files
- Ignore file size before reading

## Decision Tree

| Need | Approach | Savings |
|------|----------|---------|
| API/Interface only | `extract-signatures.sh file.py` | 96% |
| Structure overview | `summarize-file.sh file.cpp` | 98% |
| Head + tail preview | `smart-preview.sh file.cc` | 99% |
| Specific section | `Read(file, offset=100, limit=50)` | - |
| Search within file | `Grep(pattern, path, -C=3)` | - |

## By File Type

**Source Code (>500 lines):**
1. `extract-signatures.sh` for API surface
2. `smart-ast.sh` for specific patterns
3. Read specific functions with offset/limit

**Logs (>1000 lines):**
```bash
compress-logs.sh < app.log          # Errors/warnings only
compress-stacktrace.sh < error.log  # App frames only
dedup-errors.sh < errors.log        # Group duplicates
```

**JSON/Config (>500 lines):**
```bash
compress-json.sh '<json>' 'field1,field2'
smart-json.sh file.json '.data.items[:5]'
```

**Diffs (>100 lines):** `compress-diff.sh HEAD~3`

## Editing Large Files

1. Find target: `Grep(pattern, path, -A=20)`
2. Read section: `Read(file, offset=245, limit=30)`
3. Edit with unique context in `old_string`

## Quick Reference

| Size | Approach |
|------|----------|
| <200 lines | Read normally |
| 200-500 | Use limit or extract-signatures |
| 500-2000 | smart-preview + targeted reads |
| >2000 | Summarize first, surgical reads only |

## Anti-Patterns

- Reading entire file "to understand it" - use summarize-file.sh
- Multiple full-file reads - cache what you learn
- Displaying large outputs - always compress/truncate
- Reading before knowing what you need
- Ignoring offset/limit parameters

## Escalation Triggers

Use `Task(file-summarizer)` when:
- File >1000 lines and need overall understanding
- Multiple large files to comprehend
- Building mental model of unfamiliar code

Fall back to manual approach when:
- Scripts fail or produce unhelpful output
- Need byte-level precision
- File has unusual encoding/format

## Failure Behavior

If script fails (e.g., `extract-signatures.sh` errors):
1. Report the error briefly
2. Fall back to next approach in decision tree
3. If all scripts fail: use `Read(limit=100)` + `Grep` combination

If file too large even for surgical reads:
1. Explain the size constraint
2. Ask user which section/function is relevant
3. Suggest breaking task into smaller parts

If edit fails due to non-unique old_string:
1. Use `Grep(pattern, path, -n)` to find all occurrences
2. Add more surrounding context to make unique
3. Report line numbers if user needs to specify which occurrence
