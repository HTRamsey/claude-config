---
description: Create conventional commit from staged changes
allowed-tools: Bash(git:*)
argument-hint: [message-hint]
---

# /commit

Create a meaningful conventional commit from staged changes.

## Workflow

1. **Check repository state:**
   ```bash
   git status --short
   git diff --cached --stat
   ```

2. **Analyze changes:**
   - Identify modified files and their purpose
   - Determine commit type: `feat|fix|docs|refactor|test|chore`
   - Determine scope (optional): component/module affected

3. **Generate commit message:**
   - Format: `type(scope): subject`
   - Subject: Clear, present-tense description (< 50 chars)
   - Body (if needed): Why the change was made

4. **Stage if needed:**
   ```bash
   git add -u  # Stage modified files only
   ```

5. **Commit:**
   ```bash
   git commit -m "type(scope): clear subject"
   ```

## Examples
```
feat(mavlink): add COMMAND_ACK timeout handling
fix(qml): resolve altitude display rounding error
docs(readme): update build instructions for Qt 6.8
refactor(vehicle): extract telemetry parsing logic
test(settings): add unit tests for AppSettings
chore(deps): update Qt to 6.8.1
```

## Rules
- Never add "Co-authored-by" or AI attribution
- Never use emojis
- Keep subject line under 50 characters
- Use present tense ("add" not "added")
- Focus on what and why, not how