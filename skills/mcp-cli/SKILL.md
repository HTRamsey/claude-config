---
name: mcp-cli
description: On-demand MCP server access via CLI without adding to settings.json. Use when exploring MCP server capabilities before installing, making one-off calls, testing MCP servers during development, or avoiding context pollution from rarely-used servers. Discover tools, make calls, test servers.
compatibility: Requires mcp CLI. Install with npm install -g @anthropic/mcp-cli. Node.js required.
---

# MCP CLI: On-Demand MCP Server Access

**Persona:** MCP integration specialist - enables exploration and use of MCP servers without permanent configuration.

## When NOT to Use

- Frequently-used servers (add to settings.json instead)
- Servers requiring complex persistent state
- When MCP tool is already configured in Claude Code

## Discovery Commands

```bash
# List available tools
mcp tools npx -y @modelcontextprotocol/server-filesystem /tmp

# List resources
mcp resources npx -y @modelcontextprotocol/server-filesystem /tmp

# List prompts
mcp prompts npx -y @modelcontextprotocol/server-memory

# JSON output for parsing
mcp tools --format json npx -y @modelcontextprotocol/server-filesystem /tmp
```

## Tool Invocation

```bash
# Basic syntax
mcp call <tool_name> --params '<json>' <server-command>

# Examples
mcp call read_file --params '{"path": "/tmp/test.txt"}' \
  npx -y @modelcontextprotocol/server-filesystem /tmp

mcp call write_file --params '{"path": "/tmp/out.txt", "content": "hello"}' \
  npx -y @modelcontextprotocol/server-filesystem /tmp

mcp call list_directory --params '{"path": "/tmp"}' \
  npx -y @modelcontextprotocol/server-filesystem /tmp
```

## Common Servers

| Server | Command | Use For |
|--------|---------|---------|
| Filesystem | `npx -y @modelcontextprotocol/server-filesystem /path` | File operations |
| Memory | `npx -y @modelcontextprotocol/server-memory` | Knowledge graphs |
| GitHub | `npx -y @modelcontextprotocol/server-github` | Repo operations |
| Brave Search | `npx -y @anthropic/mcp-server-brave-search` | Web search |
| Playwright | `npx -y @anthropic/mcp-server-playwright` | Browser automation (Firefox, Chrome, WebKit) |
| Puppeteer | `npx -y @anthropic/mcp-server-puppeteer` | Browser automation (Chrome only) |

## Aliases (Session Shortcuts)

```bash
# Create alias for repeated use
mcp alias add fs npx -y @modelcontextprotocol/server-filesystem /home/user

# Use alias
mcp tools @fs
mcp call read_file --params '{"path": "file.txt"}' @fs

# Remove alias
mcp alias remove fs
```

## Authentication

```bash
# HTTP Basic Auth
mcp call tool --auth-user user:pass --params '{}' https://api.example.com

# Bearer token
mcp call tool --auth-header "Authorization: Bearer TOKEN" --params '{}' https://api.example.com

# Environment variables (for Docker)
mcp call tool --params '{}' docker run -e API_KEY=xxx server-image
```

## Transport Types

| Type | Auto-detected | Example |
|------|---------------|---------|
| stdio | `npx`, `docker run` | `npx -y @mcp/server` |
| HTTP | URLs | `https://api.example.com/mcp` |
| SSE | Explicit | `--transport sse https://...` |

## Workflow

```bash
# 1. Discover what's available
mcp tools npx -y @modelcontextprotocol/server-filesystem /tmp

# 2. Check tool schema
mcp tools --format json npx -y @modelcontextprotocol/server-filesystem /tmp | jq '.[] | select(.name == "read_file")'

# 3. Call the tool
mcp call read_file --params '{"path": "/tmp/test.txt"}' \
  npx -y @modelcontextprotocol/server-filesystem /tmp
```

## Should NOT Attempt

- Using mcp-cli for servers already in settings.json (redundant)
- Skipping discovery (always check tools first)
- Malformed JSON in --params (validate before calling)
- Calling without understanding parameter schema

## Failure Behavior

If mcp commands fail:
1. Check if mcp CLI is installed: `which mcp`
2. Verify server command works standalone: `npx -y @mcp/server --help`
3. Check JSON params syntax: `echo '{"key": "value"}' | jq .`
4. Use `--format json` to see detailed error responses

## Escalation

| Situation | Action |
|-----------|--------|
| mcp CLI not installed | `npm install -g @anthropic/mcp-cli` |
| Server frequently needed | Add to settings.json instead |
| Complex multi-call workflow | Consider writing a script |
| Auth issues | Check server docs for auth method |
