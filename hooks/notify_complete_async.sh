#!/usr/bin/env bash
# Async notification hook - desktop notifications + optional TTS
# Runs asynchronously to avoid blocking Claude
#
# PostToolUse hook for Bash tool
#
# Environment variables:
#   CLAUDE_TTS_ENABLED=true         Enable TTS (default: false)
#   CLAUDE_TTS_PROVIDER=local       Options: local, elevenlabs, openai
#   ELEVENLABS_API_KEY=...          Required for elevenlabs provider
#   OPENAI_API_KEY=...              Required for openai provider

# Output async config FIRST - this tells Claude Code to not wait
echo '{"async":true,"asyncTimeout":15000}'

# Read context from stdin
ctx=$(cat)

# Extract tool name - only process Bash
tool_name=$(echo "$ctx" | jq -r '.tool_name // ""')
if [[ "$tool_name" != "Bash" ]]; then
    exit 0
fi

# Check duration (need > 30 seconds)
duration_ms=$(echo "$ctx" | jq -r '.duration_ms // 0')
duration_secs=$((duration_ms / 1000))

if [[ $duration_secs -lt 30 ]]; then
    exit 0
fi

# Extract command and exit code
command=$(echo "$ctx" | jq -r '.tool_input.command // ""' | head -c 50)
exit_code=$(echo "$ctx" | jq -r '.tool_result.exit_code // 0')

# Determine notification type
if [[ "$exit_code" == "0" ]]; then
    title="✓ Command Complete"
    urgency="normal"
    tts_message="Command completed successfully"
else
    title="✗ Command Failed"
    urgency="critical"
    tts_message="Command failed"
fi

message="${command}...
Duration: ${duration_secs}s"

# Send desktop notification (if notify-send available)
if command -v notify-send &>/dev/null; then
    notify-send \
        --urgency "$urgency" \
        --app-name "Claude Code" \
        --icon terminal \
        "$title" \
        "$message"
fi

# TTS audio feedback (if enabled)
speak_text() {
    local text="$1"
    local provider="${CLAUDE_TTS_PROVIDER:-local}"

    case "$provider" in
        elevenlabs)
            if [[ -z "$ELEVENLABS_API_KEY" ]]; then
                provider="local"
            else
                # ElevenLabs API
                curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM" \
                    -H "xi-api-key: $ELEVENLABS_API_KEY" \
                    -H "Content-Type: application/json" \
                    -d "{\"text\": \"$text\", \"model_id\": \"eleven_monolingual_v1\"}" \
                    --output /tmp/claude_tts.mp3 2>/dev/null
                if [[ -f /tmp/claude_tts.mp3 ]]; then
                    if command -v mpv &>/dev/null; then
                        mpv --really-quiet /tmp/claude_tts.mp3 2>/dev/null
                    elif command -v ffplay &>/dev/null; then
                        ffplay -nodisp -autoexit /tmp/claude_tts.mp3 2>/dev/null
                    fi
                    rm -f /tmp/claude_tts.mp3
                fi
                return
            fi
            ;;
        openai)
            if [[ -z "$OPENAI_API_KEY" ]]; then
                provider="local"
            else
                # OpenAI TTS API
                curl -s -X POST "https://api.openai.com/v1/audio/speech" \
                    -H "Authorization: Bearer $OPENAI_API_KEY" \
                    -H "Content-Type: application/json" \
                    -d "{\"model\": \"tts-1\", \"input\": \"$text\", \"voice\": \"alloy\"}" \
                    --output /tmp/claude_tts.mp3 2>/dev/null
                if [[ -f /tmp/claude_tts.mp3 ]]; then
                    if command -v mpv &>/dev/null; then
                        mpv --really-quiet /tmp/claude_tts.mp3 2>/dev/null
                    elif command -v ffplay &>/dev/null; then
                        ffplay -nodisp -autoexit /tmp/claude_tts.mp3 2>/dev/null
                    fi
                    rm -f /tmp/claude_tts.mp3
                fi
                return
            fi
            ;;
    esac

    # Local fallback (espeak or pyttsx3 via Python)
    if command -v espeak &>/dev/null; then
        espeak -v en -s 150 "$text" 2>/dev/null
    elif command -v espeak-ng &>/dev/null; then
        espeak-ng -v en -s 150 "$text" 2>/dev/null
    elif [[ -f "$HOME/.claude/data/venv/bin/python3" ]]; then
        "$HOME/.claude/data/venv/bin/python3" -c "
try:
    import pyttsx3
    engine = pyttsx3.init()
    engine.say('$text')
    engine.runAndWait()
except:
    pass
" 2>/dev/null
    fi
}

# Only speak if TTS is enabled
if [[ "${CLAUDE_TTS_ENABLED:-false}" == "true" ]]; then
    speak_text "$tts_message"
fi
