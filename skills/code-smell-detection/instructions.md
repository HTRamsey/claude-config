# Tier 2: Core Instructions (~200 tokens)

## Workflow

1. **Categorize Smells**
   - Bloaters: Long Method (>20 lines), Large Class (>300 lines), Long Parameter List (>3 params)
   - Change Preventers: Divergent Change, Shotgun Surgery
   - Couplers: Feature Envy, Message Chains
   - Dispensables: Dead Code, Duplicate Code, Explanatory Comments

2. **Prioritize by Severity**
   - High: Duplicate code, Feature envy, God class → Fix immediately
   - Medium: Long methods, Long params, Data clumps → Fix when touching file
   - Low: Comments, Lazy class → Fix during cleanup

3. **Provide Refactoring Recipe**
   - Each smell maps to specific refactoring (Extract Method, Extract Class, etc.)

4. **Report Format**
   - Table with File:Line | Smell | Evidence | Refactoring

## Mandatory Checks

- ✓ Report includes file:line references
- ✓ Each smell has refactoring recipe
- ✓ Prioritization by severity
- ✓ Objective metrics (lines, params), not style preferences

## Should NOT Do

- Refactor while detecting (separate concerns)
- Flag style preferences as smells
- Report smells without refactoring recipes
- Detect in generated/vendored code

## Escalate When

- >10 High severity smells → `orchestrator` agent
- God class (>1000 lines) → `batch-editor` agent
- Circular dependencies → Architecture review
- No test coverage → STOP, add tests first
