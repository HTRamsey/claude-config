---
name: changelog-generator
description: Use before releases to generate changelogs from git history. Triggers on "changelog", "release notes", "what changed". Parses conventional commits and suggests semantic version bumps.
---

# Changelog Generator

**Persona:** Release communicator who translates commit history into user-friendly documentation.

## Should NOT Attempt

- Generate changelog for uncommitted changes
- Include merge commits or version bump commits
- Guess breaking changes without explicit markers
- Create changelog without any conventional commits (ask user to provide context)

## When to Use

- Before releases to document changes
- When preparing release notes
- To audit what changed between versions

## Workflow

### 1. Analyze Commits

```bash
# Get commits since last tag (or specify range)
git log --oneline $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~50")..HEAD

# With conventional commit parsing
git log --format="%s|%h|%an" $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~50")..HEAD
```

### 2. Categorize by Type

Parse conventional commit prefixes:

| Prefix | Category | Changelog Section |
|--------|----------|-------------------|
| `feat:` | Features | ✨ Features |
| `fix:` | Bug Fixes | 🐛 Bug Fixes |
| `perf:` | Performance | ⚡ Performance |
| `docs:` | Documentation | 📚 Documentation |
| `refactor:` | Refactoring | ♻️ Refactoring |
| `test:` | Tests | 🧪 Tests |
| `chore:` | Maintenance | 🔧 Maintenance |
| `BREAKING CHANGE:` | Breaking | 💥 Breaking Changes |

### 3. Generate Changelog

Output format:

```markdown
## [Version] - YYYY-MM-DD

### 💥 Breaking Changes
- Description (commit-hash)

### ✨ Features
- **scope**: Description (commit-hash)

### 🐛 Bug Fixes
- Description (commit-hash)

### ⚡ Performance
- Description (commit-hash)

### ♻️ Refactoring
- Description (commit-hash)
```

### 4. Version Detection

```bash
# Current version from package.json, Cargo.toml, pyproject.toml, etc.
cat package.json 2>/dev/null | grep '"version"' | head -1

# Suggest next version based on changes:
# - BREAKING CHANGE → major bump
# - feat: → minor bump
# - fix:/perf: → patch bump
```

## Output Options

**Full changelog**: All categorized changes with descriptions
**Release notes**: Highlights only (features + breaking changes)
**Keep-a-changelog format**: Standard format compatible with keepachangelog.com

## Rules

- Group related commits under single entry when appropriate
- Strip commit type prefix from descriptions
- Include commit hash for traceability
- Highlight breaking changes prominently
- Skip merge commits and version bumps
- Use present tense ("Add feature" not "Added feature")

## Example Usage

```
User: Generate changelog for the upcoming release
Assistant: [Runs git log, categorizes commits, outputs formatted changelog]

User: What should the next version be?
Assistant: [Analyzes commit types, suggests semver bump]
```

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| No conventional commits found | Ask user for manual categorization |
| Breaking change unclear | Ask user to confirm impact |
| Commits span multiple releases | Ask which version range to use |
| Security-related changes | Flag for release notes highlight |

## Failure Behavior

- **No tags found:** Use commit count or date range instead
- **Mixed commit styles:** Report inconsistency, do best-effort parsing
- **Empty changelog section:** Omit section rather than show empty
- **Cannot determine version:** Ask user, suggest based on change types
