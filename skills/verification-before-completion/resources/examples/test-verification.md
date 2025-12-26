# Test Verification Examples

## Good: Evidence-Based Claim

```
$ pytest tests/
====== test session starts ======
collected 34 items

tests/test_auth.py ........ [ 23%]
tests/test_api.py ......... [ 50%]
tests/test_utils.py ....... [100%]

====== 34 passed in 2.41s ======

All tests pass (34/34 passed, 0 failed).
```

## Bad: Claim Without Evidence

```
"The tests should pass now"
"I'm confident the tests will work"
"Based on the changes, tests are passing"
```

## Regression Test: Red-Green Verification

```
1. Write test (expects new behavior)
2. Run: FAIL ✓ (confirms test detects issue)
3. Implement fix
4. Run: PASS ✓ (confirms fix works)
5. Revert fix
6. Run: FAIL ✓ (confirms test catches regression)
7. Restore fix
8. Run: PASS ✓ (final confirmation)

Evidence: Red-green cycle verified, regression test works.
```
