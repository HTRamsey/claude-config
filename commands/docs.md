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

## Rules
- Match existing doc style
- Don't doc trivial getters/setters
- Update docs when code changes
- Use code blocks for examples
- Keep it concise but complete
