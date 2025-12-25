---
description: Generate or update documentation for code
allowed-tools: Read, Write, Edit, Grep, Glob
argument-hint: <file|function|class>
---

# /docs

## Target
$ARGUMENTS (file, function, or class to document)

Generate or update documentation.

## Use Cases
- Document new functions/classes
- Update README for new features
- Create API documentation
- Explain complex algorithms

## Workflow

1. **Identify target:**
   - Code to document (file/function/class)
   - Audience (developers, users, contributors)
   - Format (inline, README, wiki)

2. **Analyze code:**
   - Read function signatures and logic
   - Understand inputs, outputs, side effects
   - Note pre/post conditions

3. **Generate documentation:**
   - **C++ Doxygen style:**
     ```cpp
     /**
      * @brief Brief description
      * @param param1 Description of param1
      * @return Description of return value
      */
     ```
   
   - **README sections:**
     - What it does
     - How to use it
     - Examples
     - Common issues
   
   - **API docs:**
     - Endpoints/methods
     - Parameters and types
     - Return values
     - Error codes

4. **Keep it practical:**
   - Focus on *why*, not just *what*
   - Include examples
   - Document edge cases
   - Note threading/timing concerns

## Output Format
```
Updated documentation for: Vehicle::getBatteryVoltage()

Added:
- Function docstring with @brief, @param, @return
- Example usage in header comment

Files modified:
- src/Vehicle.h:142 (added Doxygen comment)
```

## Should NOT Do
- Document trivial getters/setters
- Add redundant comments restating code
- Create new doc files without asking
- Change existing doc style/format

## When to Bail
- **Code too complex**: Logic too intricate to document meaningfully without deep domain knowledge
- **No clear API surface**: No entry points, public interface, or exports to document
- **Missing standards**: No existing doc style/convention and no style guide in project
- **Target not found**: File, directory, function, or class doesn't exist
- **Generated code**: Auto-generated files (protocol buffers, parsers, bindings) that shouldn't be manually documented
- **Third-party code**: External libraries, vendored dependencies, or node_modules without local modifications
- **Trivial code**: Simple getters/setters, obvious one-liners that would be over-documented
- **Unstable code**: Prototype/experimental code marked for deletion or major refactoring

## Rules
- Match existing doc style
- Update docs when code changes
- Use code blocks for examples
- Keep it concise but complete
