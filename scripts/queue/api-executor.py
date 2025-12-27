#!/usr/bin/env python3
"""API executor for queue tasks using Anthropic SDK."""

import argparse
import json
import os
import sys

try:
    import anthropic
except ImportError:
    print(json.dumps({
        "success": False,
        "error": "anthropic package not installed",
        "output": "",
        "tokens": {"input": 0, "output": 0}
    }))
    sys.exit(1)

MODEL_MAP = {
    "haiku": "claude-3-5-haiku-latest",
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
}

DEFAULT_SYSTEM = "You are a helpful assistant. Be concise."


def run_completion(prompt: str, model: str = "sonnet", system: str = DEFAULT_SYSTEM) -> dict:
    """Run a completion via Anthropic API."""
    model_id = MODEL_MAP.get(model, MODEL_MAP["sonnet"])

    try:
        client = anthropic.Anthropic()

        message = client.messages.create(
            model=model_id,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": prompt}]
        )

        output = message.content[0].text if message.content else ""

        return {
            "success": True,
            "output": output,
            "tokens": {
                "input": message.usage.input_tokens,
                "output": message.usage.output_tokens
            },
            "model": model_id,
            "stop_reason": message.stop_reason
        }

    except anthropic.APIConnectionError as e:
        return {"success": False, "error": f"Connection error: {e}", "output": "", "tokens": {"input": 0, "output": 0}}
    except anthropic.RateLimitError as e:
        return {"success": False, "error": f"Rate limit: {e}", "output": "", "tokens": {"input": 0, "output": 0}}
    except anthropic.APIStatusError as e:
        return {"success": False, "error": f"API error ({e.status_code}): {e.message}", "output": "", "tokens": {"input": 0, "output": 0}}
    except Exception as e:
        return {"success": False, "error": str(e), "output": "", "tokens": {"input": 0, "output": 0}}


def main():
    parser = argparse.ArgumentParser(description="Execute prompt via Anthropic API")
    parser.add_argument("prompt", help="The prompt to send")
    parser.add_argument("--model", choices=["haiku", "sonnet", "opus"], default="sonnet", help="Model tier")
    parser.add_argument("--system", default=DEFAULT_SYSTEM, help="System prompt")
    parser.add_argument("--raw", action="store_true", help="Output raw text instead of JSON")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        result = {"success": False, "error": "ANTHROPIC_API_KEY not set", "output": "", "tokens": {"input": 0, "output": 0}}
    else:
        result = run_completion(args.prompt, args.model, args.system)

    if args.raw:
        if result["success"]:
            print(result["output"])
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
    else:
        print(json.dumps(result))
        if not result["success"]:
            sys.exit(1)


if __name__ == "__main__":
    main()
