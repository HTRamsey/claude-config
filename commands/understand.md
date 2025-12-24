---
description: Explain code architecture, flow, and patterns
allowed-tools: Read, Grep, Glob, Task
argument-hint: <file|function|subsystem>
---

# /understand

## Target
$ARGUMENTS (file, function, subsystem, or question about the code)

Explain how code works - architecture, flow, patterns.

## Use Cases
- Understand unfamiliar codebase
- Trace data/control flow
- Learn design patterns in use
- Debug complex interactions

## Workflow

1. **Clarify scope:**
   - Specific file/function?
   - Feature/subsystem?
   - Data flow for a use case?

2. **Map the structure:**
   - Entry points (main, message handlers, UI events)
   - Key classes and their roles
   - Data structures and ownership
   - Threading and synchronization

3. **Explain flow:**
   - Start from trigger (user action, message, timer)
   - Trace through call chain
   - Note state changes
   - Show end result

4. **Format:**
   ```
   ## Overview
   Brief 2-3 sentence summary
   
   ## Key Components
   - ClassName: Role and responsibilities
   
   ## Data Flow
   1. Entry point → calls what
   2. Processing → state changes
   3. Result → where it goes
   
   ## Important Notes
   - Threading concerns
   - Performance considerations
   - Edge cases
   ```

## Tips
- Use diagrams (ASCII art) for complex flows
- Quote key code snippets
- Note design patterns (Factory, Observer, etc.)
- Mention related files to explore
- Keep explanations high-level first, drill down on request

## Example
"Explain how MAVLink COMMAND_LONG is handled"
→ Trace from LinkInterface → MAVLinkProtocol → Vehicle → command execution
