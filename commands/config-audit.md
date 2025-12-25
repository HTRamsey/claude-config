---
description: Audit ~/.claude config for issues and improvements
allowed-tools: Task, Read, Grep, Glob, Edit
---

# /config-audit

Comprehensive review of ~/.claude config using parallel subagents for each section.

**Arguments**: `$ARGUMENTS` - optional section to audit (agents|commands|hooks|rules|scripts|skills|settings) or "all" (default)

## Workflow

1. **Launch parallel subagents** for each config section:
   - Each agent reviews its section independently
   - All agents run in background simultaneously
   - Use `context-optimizer` agent type for analysis

2. **Collect and synthesize results**:
   - Wait for all agents to complete
   - Combine findings into unified report
   - Prioritize by impact and complexity

3. **Update backlog**:
   - Append new findings to `~/.claude/backlog/improvements.md`
   - Avoid duplicating existing items

## Priority & Complexity Scales

**Priority:**
- P1 (Critical): Broken/invalid config, security risk, causes failures
- P2 (High): Performance issues, missing guardrails, wrong assignments
- P3 (Medium): Overlap, gaps, quality issues, organization
- P4 (Low): Style inconsistency, minor optimization

**Complexity:**
- S (Small): Fix value, <10 lines, single file
- M (Medium): Rewrite section, merge items, add tests
- L (Large): New component, significant restructure

## Subagent Prompts

### Agents Section (`~/.claude/agents/`)
```
Audit agent definitions in ~/.claude/agents/*.md

## CONTEXT (read in order)
1. ~/.claude/rules/reference.md - Get canonical agent list and triggers
2. ~/.claude/agents/*.md - All agent definitions
3. ~/.claude/settings.json - Check model preferences

## CRITERIA

1. **OVERLAP** - Agents with >50% similar triggers or overlapping functionality
   - Flag if two agents cover same use case
   - Check: same tools + similar description = candidate for merge

2. **GAPS** - Missing agents for common workflows
   - Compare actual agents to reference.md list
   - Check: any reference.md agents missing files?

3. **MODEL FIT** - Appropriate model assignment
   - haiku: Single-fact lookup, error explanation, summarization
   - sonnet: Multi-step analysis, code generation, research
   - opus: Architecture, security, complex debugging
   - Flag: haiku doing complex analysis, opus doing simple lookup

4. **TOOL FIT** - Tools are correct and minimal
   - Flag: Agent has tools it never needs
   - Flag: Agent missing tools it would need

5. **FRONTMATTER** - Required fields present and valid
   - Required: name, description, tools, model
   - description: Should include trigger phrases

6. **CONTENT QUALITY** - Instructions are clear and current
   - Flag: Outdated file paths, stale examples
   - Flag: Missing "Rules" or response format section
   - Flag: Instructions >500 lines (too complex)

## CROSS-REFERENCE
- Verify agent count matches reference.md
- Check tool lists match settings.json allowedTools patterns
- Verify model names valid: haiku, sonnet, opus

## OUTPUT FORMAT
| Priority | Issue Type | Agent(s) | Finding | Recommendation | Complexity |
|----------|-----------|----------|---------|----------------|------------|

## Example Row
| P3 | overlap | quick-lookup, error-explainer | Both handle "what does this error mean?" | Merge error-explainer into quick-lookup | M |
```

### Commands Section (`~/.claude/commands/`)
```
Audit command definitions in ~/.claude/commands/*.md

## CONTEXT (read in order)
1. ~/.claude/rules/reference.md - Get canonical command list
2. ~/.claude/commands/*.md - All command files
3. Sample 3 commands to understand expected structure

## CRITERIA

1. **OVERLAP** - Commands with similar workflows
   - Flag: Two commands doing same job differently
   - Flag: Command that duplicates built-in

2. **GAPS** - Missing commands for common workflows
   - Compare to reference.md list
   - Common missing: dependency update, security scan

3. **STRUCTURE** - Required sections present
   Required: Workflow, Output Format, Should NOT Do, When to Bail
   Flag: Missing any required section

4. **FRONTMATTER** - Valid YAML frontmatter
   - Required: description
   - Flag: Invalid YAML, missing description

5. **WORKFLOW QUALITY** - Steps are clear and actionable
   - Each step: action, command/tool, expected result
   - Flag: Vague steps, >15 steps (too complex)

6. **EXAMPLES** - Concrete examples present
   - Flag: No examples or sample output

## CROSS-REFERENCE
- Verify command count matches reference.md
- Check archive/ for deprecated commands

## OUTPUT FORMAT
| Priority | Issue Type | Command(s) | Finding | Recommendation | Complexity |
|----------|-----------|------------|---------|----------------|------------|

## Example Row
| P2 | missing-section | /ci-fix | No "When to Bail" section | Add bail conditions: max 3 iterations | S |
```

### Hooks Section (`~/.claude/hooks/`)
```
Audit hook implementations in ~/.claude/hooks/*.py

## CONTEXT (read in order)
1. ~/.claude/settings.json - hooks section (registered hooks by event)
2. ~/.claude/hooks/*.py - All hook files
3. ~/.claude/hooks/hook_utils.py - Shared utilities
4. ~/.claude/hooks/pre_tool_dispatcher.py - PreToolUse consolidation
5. ~/.claude/hooks/post_tool_dispatcher.py - PostToolUse consolidation
6. ~/.claude/rules/architecture.md - Hook documentation

## CRITERIA

1. **REGISTRATION** - Hooks registered vs files present
   - List hooks in settings.json by event
   - List .py files in hooks/
   - Flag: File exists but not registered
   - Flag: Registered but file missing

2. **DISPATCHER INTEGRATION** - Hooks use dispatchers correctly
   - PreToolUse hooks via pre_tool_dispatcher.py
   - PostToolUse hooks via post_tool_dispatcher.py
   - Flag: Hook registered directly instead of via dispatcher

3. **PERFORMANCE** - Hooks complete within timeout
   - Flag: I/O operations with timeout < 2s
   - Flag: Network calls without caching
   - Flag: Synchronous file reads > 10 files

4. **CODE QUALITY** - Error handling and logging
   - Flag: No try/except at top level
   - Flag: Not using hook_utils.py
   - Flag: Printing to stdout instead of hook protocol

5. **STATE MANAGEMENT** - State files organized
   - Expected in ~/.claude/data/
   - Flag: State files in /tmp or hooks/
   - Flag: No cleanup/rotation for growing files

6. **UNUSED/LOW-VALUE** - Hooks that don't trigger
   - Flag: Hook for rare event with high overhead
   - Flag: Hook that only logs without action

## CROSS-REFERENCE
- Verify architecture.md hook count matches reality
- Check dispatcher imports match registered hooks
- Verify data/ files referenced by hooks exist

## OUTPUT FORMAT
| Priority | Issue Type | Hook(s) | Finding | Recommendation | Complexity |
|----------|-----------|---------|---------|----------------|------------|

## Example Row
| P2 | performance | file_access_tracker | No caching, reads files on every trigger | Add LRU cache with 60s TTL | M |
```

### Rules Section (`~/.claude/rules/`)
```
Audit rules files in ~/.claude/rules/*.md

## CONTEXT (read in order)
1. ~/.claude/CLAUDE.md - Entry point, should reference all rules
2. ~/.claude/rules/guidelines.md - Style, security, verification
3. ~/.claude/rules/tooling.md - Tools, scripts, context management
4. ~/.claude/rules/reference.md - Skills, agents, commands
5. ~/.claude/rules/architecture.md - Full configuration map

## CRITERIA

1. **ACCURACY** - Counts and paths are correct
   - Check agent/command/skill/hook counts vs actual files
   - Check script paths exist
   - Flag: Any count mismatch, broken path

2. **REDUNDANCY** - Duplicate content across files
   - reference.md and architecture.md both list agents/skills?
   - Flag: Same information in multiple files
   - Flag: Conflicting versions of same info

3. **COMPLETENESS** - All features documented
   - Flag: Hook in settings.json not in architecture.md
   - Flag: Agent file exists but not in reference.md
   - Flag: Script exists but not in tooling.md

4. **ORGANIZATION** - Information in correct file
   | File | Should Contain |
   |------|----------------|
   | guidelines.md | Style, security, verification |
   | tooling.md | Tools, scripts, context |
   | reference.md | Quick lookup skills/agents/commands |
   | architecture.md | Directory structure, data flow |

5. **CONSISTENCY** - Format and terminology
   - Table formats should match
   - Terminology consistent
   - Path format consistent

6. **CROSS-REFERENCES** - Links between files work
   - Flag: Reference to file that doesn't exist

## CROSS-REFERENCE
- Count actual files in agents/, commands/, skills/, hooks/
- Compare to counts claimed in rules files
- Verify CLAUDE.md references all rules files

## OUTPUT FORMAT
| Priority | Issue Type | File(s) | Finding | Recommendation | Complexity |
|----------|-----------|---------|---------|----------------|------------|

## Example Row
| P1 | accuracy | reference.md | Claims 14 commands but only 12 exist | Update count or add missing files | S |
```

### Scripts Section (`~/.claude/scripts/`)
```
Audit shell scripts in ~/.claude/scripts/**/*.sh

## CONTEXT (read in order)
1. ~/.claude/rules/tooling.md - Script documentation
2. ~/.claude/rules/architecture.md - Script directory structure
3. ~/.claude/scripts/lib/common.sh - Shared utilities
4. ~/.claude/scripts/**/*.sh - All script files

## CRITERIA

1. **ORGANIZATION** - Scripts in correct subdirectory
   | Directory | Purpose |
   |-----------|---------|
   | compress/ | Output compression |
   | smart/ | Intelligent viewing |
   | search/ | Offloaded search |
   | analysis/ | Code analysis |
   | git/ | Git workflows |
   | queue/ | Task queue |
   | diagnostics/ | Health checks |
   | automation/ | Batch ops |
   | lib/ | Shared functions |
   Flag: Script in wrong directory

2. **LIBRARY USAGE** - Scripts use lib/ utilities
   - Flag: Script reimplements lib/ functionality
   - Flag: Script sources non-existent lib file

3. **UNUSED SCRIPTS** - Scripts not referenced anywhere
   - Search hooks/*.py, commands/*.md, agents/*.md
   - Flag: Script not referenced anywhere

4. **DUPLICATED LOGIC** - Similar code across scripts
   - Common: tool detection, language detection
   - Flag: Same function in multiple scripts

5. **QUALITY** - Script robustness
   - Flag: No shebang or wrong shebang
   - Flag: No set -e (continues on error)
   - Flag: Hardcoded paths
   - Flag: No usage/help with -h

6. **WRAPPER ELIMINATION** - Thin wrappers
   - Flag: Script <10 lines calling another tool

## CROSS-REFERENCE
- Verify architecture.md script count matches reality
- Verify all scripts in tooling.md tables exist

## OUTPUT FORMAT
| Priority | Issue Type | Script(s) | Finding | Recommendation | Complexity |
|----------|-----------|-----------|---------|----------------|------------|

## Example Row
| P3 | duplication | compress/*.sh, smart/*.sh | All scripts implement detect_language() | Extract to lib/common.sh | M |
```

### Skills Section (`~/.claude/skills/`)
```
Audit skill definitions in ~/.claude/skills/*/SKILL.md

## CONTEXT (read in order)
1. ~/.claude/rules/reference.md - Canonical skill list with triggers
2. ~/.claude/skills/*/SKILL.md - All skill files
3. Sample 2-3 skills to understand expected structure

## CRITERIA

1. **GAPS** - Missing skills for common workflows
   - Compare to reference.md list
   - Flag: Skill in reference.md but no directory
   - Flag: Directory exists but no SKILL.md

2. **OVERLAP** - Skills with similar triggers
   - Check description fields for similar triggers
   - Flag: Two skills triggered by same situation
   - Flag: Skills with >50% content overlap

3. **FRONTMATTER** - Valid YAML frontmatter
   - Required: name, description
   - Flag: Missing or invalid frontmatter

4. **STRUCTURE** - Required sections present
   - Overview, Workflow/Steps, Should NOT Do, Related Skills
   - Flag: Missing key sections

5. **TRIGGER COVERAGE** - Clear triggers in description
   - Description answers: "When should I use this?"
   - Flag: Vague description without triggers

6. **CONTENT QUALITY** - Instructions actionable
   - Flag: Too abstract (no concrete steps)
   - Flag: Missing examples
   - Flag: Skill >300 lines (too complex)

7. **SCRIPTS** - Check skills/*/scripts/
   - Flag: Script referenced but doesn't exist
   - Flag: Script exists but not referenced

## CROSS-REFERENCE
- Verify skill count matches reference.md
- Check skill names match directory names
- Verify "Related Skills" references exist

## OUTPUT FORMAT
| Priority | Issue Type | Skill(s) | Finding | Recommendation | Complexity |
|----------|-----------|----------|---------|----------------|------------|

## Example Row
| P2 | triggers | code-smell, receiving-code-review | Both triggered by "code quality" | Add distinct triggers | S |
```

### Settings Section (`~/.claude/settings.json`)
```
Audit settings.json configuration

## CONTEXT (read in order)
1. ~/.claude/settings.json - Full settings file
2. ~/.claude/hooks/*.py - List all hook files
3. ~/.claude/rules/architecture.md - Expected structure

## CRITERIA

1. **HOOK REGISTRATION** - Registered hooks match files
   - List registered hooks by event
   - List .py files in hooks/
   - Flag: Hook registered but file missing
   - Flag: Hook file exists but not registered
   - Flag: Wrong event type

2. **HOOK CONFIGURATION** - Timeouts and matchers valid
   - Typical: 1-5s simple, 10s for I/O
   - Flag: Timeout < 1s for I/O hook
   - Flag: Timeout > 10s
   - Flag: Matcher regex invalid

3. **PERMISSIONS** - Allow/deny patterns valid
   - Flag: Allows dangerous operation
   - Flag: Denies needed tool
   - Flag: Redundant patterns

4. **MCP SERVERS** - Configured vs used
   - Flag: Server allowed but never used
   - Flag: Useful server denied
   - Flag: Configured but not installed

5. **ENVIRONMENT** - env section valid
   - Flag: Unknown variable
   - Flag: Conflicting variables

6. **PLUGINS** - enabledPlugins valid
   - Flag: Plugin enabled but not installed
   - Flag: Plugin path invalid

7. **MODEL/OUTPUT** - Preferences valid
   - model: haiku, sonnet, opus
   - Flag: Invalid value

## CROSS-REFERENCE
- Hook files vs hooks registered
- Dispatcher imports vs dispatched hooks
- Permission patterns vs actual usage

## OUTPUT FORMAT
| Priority | Issue Type | Section | Finding | Recommendation | Complexity |
|----------|-----------|---------|---------|----------------|------------|

## Example Row
| P2 | registration | hooks.PreToolUse | file_access_tracker.py not in dispatcher | Add import to pre_tool_dispatcher.py | S |
```

## Execution

```python
# Launch all agents in parallel
sections = ["agents", "commands", "hooks", "rules", "scripts", "skills", "settings"]

for section in sections:
    Task(
        subagent_type="context-optimizer",
        prompt=PROMPTS[section],
        run_in_background=True,
        description=f"Audit {section}"
    )

# Wait for all, then synthesize
```

## Output Format

```markdown
# Config Audit Report

Generated: {date}

## Summary
- Total findings: X
- P1 (Critical): X | P2 (High): X | P3 (Medium): X | P4 (Low): X

## Agents (X findings)
| Priority | Issue Type | Agent(s) | Finding | Recommendation | Complexity |
|----------|-----------|----------|---------|----------------|------------|

## Commands (X findings)
...

## New Backlog Items
{Items to add to backlog/improvements.md}
```

## Example Output

```markdown
# Config Audit Report

Generated: 2025-12-25

## Summary
- Total findings: 12
- P1 (Critical): 1 | P2 (High): 3 | P3 (Medium): 6 | P4 (Low): 2

## Agents (3 findings)
| Priority | Issue Type | Agent(s) | Finding | Recommendation | Complexity |
|----------|-----------|----------|---------|----------------|------------|
| P2 | model-fit | quick-lookup | Opus assigned but handles simple lookups | Downgrade to Haiku | S |
| P3 | overlap | code-reviewer, code-reviewer | Both review code quality | Clarify triggers (security vs general) | M |
| P4 | description | test-generator | Missing trigger phrase for "add tests" | Update description with triggers | S |

## Commands (4 findings)
| Priority | Issue Type | Command(s) | Finding | Recommendation | Complexity |
|----------|-----------|------------|---------|----------------|------------|
| P2 | missing-section | status.md, config-audit.md | No "Example Output" section | Add realistic examples (8-15 lines) | S |
| P3 | structure | refactor.md | "When to Bail" section vague | Add concrete bailout conditions | S |

## Rules (2 findings)
| Priority | Issue Type | File(s) | Finding | Recommendation | Complexity |
|----------|-----------|---------|---------|----------------|------------|
| P1 | accuracy | reference.md | Lists 27 agents but only 24 exist | Update counts to match actual files | S |

## New Backlog Items
- [S] Add Example Output to 2 commands (status.md, config-audit.md)
- [M] Clarify overlapping code-reviewer vs code-reviewer triggers
- [S] Update reference.md agent counts (27 claimed vs 24 actual)
```

## Should NOT Do
- Make changes automatically (audit only)
- Delete or modify any config files
- Skip sections without explicit request

## When to Bail
- Config directory structure unexpected
- Permission issues reading files

## Rules
- Run all sections in parallel for speed
- Deduplicate findings across sections
- Prioritize by impact × ease
- Reference existing backlog to avoid duplicates
