# Guidelines

Style, security, and verification rules.

## Response Style

- Lead with the answer, explain after if needed
- No filler phrases ("I'll help you with...", "Sure!", "Great question!")
- No restating the question or echoing file contents just read
- Use "Done." not "I have successfully completed the task."
- Skip unnecessary caveats ("It's worth noting that...")
- One clear example beats three redundant ones
- Don't narrate self-documenting code

## Code Comments

**DEFAULT: No comments.** Only add when ALL apply:
1. Logic is genuinely non-obvious
2. Cannot be clarified by better naming
3. Explains WHY, not WHAT

**NEVER add:**
- Comments describing what code does
- Docstrings restating function signatures
- Comments on standard patterns (try/except, loops)
- Comments to code you didn't write

## Documentation & Naming

- Bullet points over paragraphs
- Tables for comparisons
- Code examples over prose explanations
- File:line references for code locations
- Follow existing project conventions
- Descriptive > short (within reason)
- No abbreviations unless domain-standard

## Commits/PRs

- Imperative mood ("Add feature" not "Added feature")
- Why over what in descriptions
- No emoji unless project uses them
- 1-2 sentence summary, details in bullets

## Verification Rules

**Always verify before claiming completion:**
1. **Code changes**: Run relevant tests, check for errors
2. **Bug fixes**: Reproduce → fix → verify fix → verify no regression
3. **New features**: Test happy path + edge cases
4. **Refactoring**: Run full test suite before and after

**Never claim "done" without evidence.** Show test output or verification steps.

| Language | Test Command |
|----------|--------------|
| Python | `pytest` |
| JavaScript/TypeScript | `npm test` |
| Rust | `cargo test` |
| Go | `go test ./...` |

## Security Coding

### Never Hardcode
- API keys, tokens, passwords → environment variables
- Connection strings → config files (not in repo)
- Private keys → secure storage

### Input Validation
- Validate at system boundaries (user input, API requests)
- Sanitize before database queries (prevent SQL injection)
- Escape output in HTML (prevent XSS)

### Safe Defaults
- Deny by default, allow explicitly
- Minimum required permissions
- Fail closed, not open

### Code Review Focus
- Authentication/authorization logic
- Data serialization/deserialization
- File path handling (prevent traversal)
- Command construction (prevent injection)

## Sensitive File Protection

**Never read** (configure in `settings.json` → `permissions.deny`):
- `.env`, `.env.*` - Environment secrets
- `./secrets/**`, `./config/credentials.*` - Credentials
- `~/.aws/**`, `~/.ssh/**` - Cloud/SSH keys
- `**/id_rsa`, `**/*.pem` - Private keys

## Permission Modes

| Mode | Behavior | Use When |
|------|----------|----------|
| Default | Prompt for each action | Normal operation |
| Accept Edits | Batch edits, prompt for commands | Trusted refactoring |
| Plan | Read-only exploration | Research, understanding |
| Bypass | Auto-approve all | Isolated containers only |

Toggle with **Shift+Tab** during session.

## Before You Start

1. **Read the file first** - Never edit without reading
2. **Use agents for exploration** - Don't grep inline, use `Task(Explore)`
3. **Compress output** - Always compress diffs, builds, test output
4. **Verify before done** - Run tests, show evidence
5. **Clear between tasks** - Use `/clear` to reset context
6. **Name sessions** - Use `/rename` for easy resumption

## Health Check

Run `~/.claude/scripts/diagnostics/health-check.sh` to verify setup.
