# Tier 2: Core Instructions (~200 tokens)

## The Gate Function

BEFORE claiming any status or expressing satisfaction:

1. **IDENTIFY**: What command proves this claim?
2. **RUN**: Execute the FULL command (fresh, complete)
3. **READ**: Full output, check exit code, count failures
4. **VERIFY**: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. **ONLY THEN**: Make the claim

Skip any step = lying, not verifying.

## Mandatory Checks

| Claim | Command Required | Evidence Format |
|-------|-----------------|-----------------|
| Tests pass | Full test suite | `[X/X passed, 0 failed]` |
| Build succeeds | Build command | `[exit 0, no errors]` |
| Linter clean | Lint command | `[0 errors, 0 warnings]` |
| Bug fixed | Reproduce steps | `[before: error, after: success]` |
| Regression test | Red-green cycle | `[fail→pass verified]` |

## Should NOT Do

- Claim success based on previous runs
- Use "should", "probably", or "likely" for status
- Trust agent/subprocess success reports without checking
- Skip verification "just this once"
- Express satisfaction before running verification

## Escalate When

| Situation | Action |
|-----------|--------|
| Verification command unavailable | Ask user for verification method |
| Tests pass but behavior incorrect | Use `systematic-debugging` skill |
| Environment prevents verification | Ask user for environment setup |
| Conflicting verification results | Ask user for authoritative source |
