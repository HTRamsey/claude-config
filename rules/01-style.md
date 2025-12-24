# Communication & Code Style

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

## Documentation
- Bullet points over paragraphs
- Tables for comparisons
- Code examples over prose explanations
- No redundant type annotations in docstrings (Python)
- File:line references for code locations

## Naming
- Follow existing project conventions first
- Descriptive > short (within reason)
- No abbreviations unless domain-standard
- Match surrounding code style

## Commits/PRs
- Imperative mood ("Add feature" not "Added feature")
- Why over what in descriptions
- No emoji unless project uses them
- 1-2 sentence summary, details in bullets

## Error Messages
- Include what failed and why
- Suggest fix when obvious
- No stack traces in user-facing messages

## Logging
- ERROR: Requires immediate attention
- WARN: Unexpected but handled
- INFO: Key operations only
- DEBUG: Diagnostic details
