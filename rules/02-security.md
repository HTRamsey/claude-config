# Security & Verification

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

## Docker Permissions

| Setting | Value | Effect |
|---------|-------|--------|
| Sandbox exclusion | `docker` in `excludedCommands` | Runs outside sandbox |
| Pre-approved | `build`, `run`, `compose`, `ps`, `logs`, `images`, `exec` | No prompt needed |
| Blocked reads | `~/.docker/config.json` | Protects auth tokens |

**Note:** Docker commands run unsandboxed for full functionality. Use caution with `docker run` flags that mount host paths.

## Permission Modes

| Mode | Behavior | Use When |
|------|----------|----------|
| Default | Prompt for each action | Normal operation |
| Accept Edits | Batch edits, prompt for commands | Trusted refactoring |
| Plan | Read-only exploration | Research, understanding |
| Bypass | Auto-approve all | Isolated containers only |

Toggle with **Shift+Tab** during session.
