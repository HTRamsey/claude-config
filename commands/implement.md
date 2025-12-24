---
description: Implement a feature with structured planning and approval gates
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
argument-hint: <feature-description>
---

# /implement

> **Note**: For complex multi-stage features, consider `/pipeline` instead.

## Feature
$ARGUMENTS

Implement a feature with a structured approach.

## Workflow

1. **Clarify requirements:**
   - What should it do?
   - Inputs, outputs, constraints
   - UI or backend or both?

2. **Plan the implementation:**
   - List files to create/modify (max 5)
   - Break into 3-6 small steps
   - Each step is independently testable
   - Identify dependencies between steps

3. **Propose architecture:**
   - New classes/modules needed?
   - Where in existing structure?
   - Integration points
   - Testing approach

4. **Wait for approval:**
   - "Proceed with step 1? (yes/no/modify)"

5. **Execute step by step:**
   - Implement one step
   - Show minimal diff
   - Verify (build/test)
   - Move to next step

## Rules
- Keep steps small and focused
- Build after each step
- Test before moving on
- Don't refactor unrelated code
- Document non-obvious decisions

## Example Steps
For "Add battery voltage to FlightDisplay":
1. Add voltage Fact to Vehicle class
2. Update MAVLink handler for SYS_STATUS
3. Add QML text field in FlightDisplay
4. Bind QML to Vehicle.batteryVoltage
5. Add unit test for voltage parsing
6. Test with simulator
