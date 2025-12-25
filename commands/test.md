---
description: Run tests and diagnose failures
allowed-tools: Bash, Read, Grep, Glob
argument-hint: [path|pattern]
---

# /test

Run tests and diagnose failures.

## Target
$ARGUMENTS (test file, pattern, or empty for all tests)

## Workflow

1. **Detect test framework:**
   ```bash
   # Auto-detect project type
   [ -f package.json ] && echo "node"
   [ -f pytest.ini ] || [ -f pyproject.toml ] || [ -f setup.py ] && echo "python"
   [ -f Cargo.toml ] && echo "rust"
   [ -f go.mod ] && echo "go"
   [ -f CMakeLists.txt ] || [ -f Makefile ] && echo "cpp"
   ```

2. **Run tests** based on framework:

   | Framework | Command |
   |-----------|---------|
   | Node.js | `npm test` or `npx jest` or `npx vitest` |
   | Python | `pytest` or `python -m pytest` |
   | Rust | `cargo test` |
   | Go | `go test ./...` |
   | C++/Qt | `ctest` or `./build/tests` |

3. **Parse results:**
   - If all pass: "✓ All tests passed (N tests)"
   - If failures: Show only failed test details

4. **Report failures:**
   ```
   ✗ TestClassName::test_method
     Expected: <value>
     Actual: <value>
     File: tests/test_file.py:45

   Likely cause: <analysis>
   Check: <file_to_inspect>
   ```

5. **Suggest fixes:**
   - Identify likely source of failure
   - Name files to inspect
   - Don't propose code unless asked

## Output Format
```
## Test Results

✓ 47 passed, ✗ 2 failed, ○ 1 skipped

### Failures

✗ test_battery_voltage_parsing
  Expected: 12.6
  Actual: 0.0
  File: tests/test_vehicle.py:89

  Likely cause: MAVLink message not being parsed
  Check: src/Vehicle.cpp:handleMessage()

Next: Fix test_battery_voltage_parsing? (yes/skip)
```

## When to Bail
- No test framework detected
- Tests require external services not available
- For flaky test diagnosis → use testing-debugger agent
- Test suite too slow (>10 min) → ask to narrow scope

## Should NOT Do
- Show full test output (compress it)
- Auto-fix failing tests without asking
- Run entire suite when specific test requested
- Rerun tests repeatedly without changes

## Rules
- Keep output concise (< 200 tokens)
- Only show failures, not full output
- Focus on first failure if multiple
- Don't rerun tests unless asked
- Use compression scripts for verbose output:
  ```bash
  ~/.claude/scripts/compress/compress.sh --type tests < test-output.log
  ```
