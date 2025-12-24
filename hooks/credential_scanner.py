#!/home/jonglaser/.claude/venv/bin/python3
"""Detect potential credentials/API keys before git commit.

PreToolUse hook for Bash tool - triggers on git commit commands.
Scans staged content for patterns that look like API keys, passwords, tokens, etc.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
try:
    from hook_utils import graceful_main, log_event
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    def graceful_main(name):
        def decorator(func):
            return func
        return decorator
    def log_event(*args, **kwargs):
        pass

# Patterns that suggest sensitive data
# Note: Some patterns split to avoid self-triggering
SENSITIVE_PATTERNS = [
    # API keys and tokens
    (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[a-zA-Z0-9_-]{20,}', "API key"),
    (r'(?i)(secret[_-]?key|secretkey)\s*[=:]\s*["\']?[a-zA-Z0-9_-]{20,}', "Secret key"),
    (r'(?i)(access[_-]?token|accesstoken)\s*[=:]\s*["\']?[a-zA-Z0-9_-]{20,}', "Access token"),
    (r'(?i)(auth[_-]?token|authtoken)\s*[=:]\s*["\']?[a-zA-Z0-9_-]{20,}', "Auth token"),

    # AWS
    (r'AKIA[0-9A-Z]{16}', "AWS Access Key ID"),
    (r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*["\']?[A-Za-z0-9/+=]{40}', "AWS Secret Key"),

    # Private keys (pattern split to avoid self-trigger)
    ("-----BEGIN " + "(RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----", "Private key"),
    ("-----BEGIN " + "CERTIFICATE-----", "Certificate"),

    # Common service tokens
    (r'sk-[a-zA-Z0-9]{48}', "OpenAI API key"),
    (r'sk-ant-[a-zA-Z0-9\-_]{90,}', "Anthropic API key"),
    (r'AIza[0-9A-Za-z\-_]{35}', "Google API key"),
    (r'ghp_[a-zA-Z0-9]{36}', "GitHub PAT"),
    (r'gho_[a-zA-Z0-9]{36}', "GitHub OAuth token"),
    (r'ghs_[a-zA-Z0-9]{36}', "GitHub App token"),
    (r'ghu_[a-zA-Z0-9]{36}', "GitHub user-to-server token"),
    (r'glpat-[a-zA-Z0-9\-_]{20,}', "GitLab PAT"),
    (r'xox[baprs]-[a-zA-Z0-9-]+', "Slack token"),

    # Payment processors
    (r'sk_live_[a-zA-Z0-9]{24,}', "Stripe secret key"),
    (r'rk_live_[a-zA-Z0-9]{24,}', "Stripe restricted key"),
    (r'sq0csp-[a-zA-Z0-9\-_]{43}', "Square access token"),
    (r'sq0atp-[a-zA-Z0-9\-_]{22}', "Square OAuth token"),

    # Communication platforms
    (r'[MN][a-zA-Z0-9]{23,26}\.[a-zA-Z0-9]{6}\.[a-zA-Z0-9_-]{27}', "Discord bot token"),
    (r'\d{17,19}:[a-zA-Z0-9_-]{35}', "Telegram bot token"),
    (r'SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}', "SendGrid API key"),
    (r'key-[a-zA-Z0-9]{32}', "Mailgun API key"),

    # Package managers
    (r'npm_[a-zA-Z0-9]{36}', "npm access token"),
    (r'pypi-[a-zA-Z0-9_-]{80,}', "PyPI API token"),
    (r'rubygems_[a-zA-Z0-9]{48}', "RubyGems API key"),

    # CI/CD
    (r'travis-[a-zA-Z0-9]{22}', "Travis CI token"),
    (r'circle-token-[a-zA-Z0-9]{40}', "CircleCI token"),

    # Other cloud services
    (r'dop_v1_[a-zA-Z0-9]{64}', "DigitalOcean PAT"),
    (r'hf_[a-zA-Z0-9]{34,}', "HuggingFace token"),
    (r'FLWSECK_TEST-[a-zA-Z0-9]{32}', "Flutterwave secret key"),
    (r'whsec_[a-zA-Z0-9]{32,}', "Webhook secret"),

    # Cloud provider credentials
    (r'DefaultEndpointsProtocol=https.*AccountKey=[A-Za-z0-9+/=]+', "Azure connection string"),
    (r'(?i)azure[_-]?storage[_-]?key\s*[=:]\s*["\']?[A-Za-z0-9+/=]{80,}', "Azure storage key"),

    # Database connection strings
    (r'(?i)(postgres|mysql|mongodb)://[^:]+:[^@]+@', "Database connection string with password"),

    # Generic password patterns
    (r'(?i)password\s*[=:]\s*["\'][^"\']{8,}["\']', "Hardcoded password"),
    (r'(?i)passwd\s*[=:]\s*["\'][^"\']{8,}["\']', "Hardcoded password"),

    # JWT tokens (only flag if looks like real token)
    (r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*', "JWT token"),
]

# Pre-compile patterns for performance
SENSITIVE_COMPILED = [(re.compile(p), n) for p, n in SENSITIVE_PATTERNS]

# Files that legitimately contain sensitive-like patterns
ALLOWLIST_PATTERNS = [
    ".example",
    ".sample",
    ".template",
    "test",
    "mock",
    "fake",
    "dummy",
]


def is_allowlisted(file_path: str) -> bool:
    """Check if file is in allowlist (test files, examples, etc.)"""
    path_lower = file_path.lower()
    return any(pattern in path_lower for pattern in ALLOWLIST_PATTERNS)


def scan_for_sensitive(content: str) -> list:
    """Scan content for potential sensitive data, return list of (pattern_name, match)"""
    findings = []
    for compiled, name in SENSITIVE_COMPILED:
        matches = compiled.findall(content)
        if matches:
            for match in matches[:3]:  # Limit to 3 per pattern
                if isinstance(match, tuple):
                    match = match[0]
                truncated = match[:20] + "..." if len(match) > 20 else match
                findings.append((name, truncated))
    return findings


def get_staged_diff() -> tuple[str, list[str]]:
    """Get staged diff content and list of staged files."""
    try:
        # Get staged diff
        result = subprocess.run(
            ["git", "diff", "--cached", "--no-color"],
            capture_output=True,
            text=True,
            timeout=5
        )
        diff_content = result.stdout

        # Get list of staged files
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=5
        )
        staged_files = [f for f in result.stdout.strip().split("\n") if f]

        return diff_content, staged_files
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return "", []


@graceful_main("credential_scanner")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = ctx.get("tool_input", {})
    command = tool_input.get("command", "")

    # Only trigger on git commit commands
    if not command.strip().startswith("git commit"):
        sys.exit(0)

    # Get staged content
    diff_content, staged_files = get_staged_diff()

    if not diff_content:
        sys.exit(0)

    # Filter out allowlisted files from consideration
    non_allowlisted = [f for f in staged_files if not is_allowlisted(f)]
    if not non_allowlisted:
        sys.exit(0)

    # Scan for sensitive data
    findings = scan_for_sensitive(diff_content)

    if findings:
        unique_types = list(set(name for name, _ in findings))[:5]
        log_event("credential_scanner", "blocked", {
            "types": unique_types,
            "files": non_allowlisted[:3]
        }, "warning")

        reason = (
            f"Potential credentials detected in staged changes: {', '.join(unique_types)}. "
            f"Files: {', '.join(non_allowlisted[:3])}. "
            "Use environment variables or a secrets manager instead. "
            "Review with: git diff --cached"
        )
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason
            }
        }
        print(json.dumps(result))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
