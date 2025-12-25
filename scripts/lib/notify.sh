#!/usr/bin/env bash
set -euo pipefail
# notify.sh - Desktop notification when tasks complete
#
# Usage:
#   notify.sh "Build complete"
#   notify.sh -t "Title" "Body message"
#   long_command && notify.sh "Done" || notify.sh -u critical "Failed"
#   notify.sh --wrap long_command args...
#
# Options:
#   -t, --title <title>  Notification title
#   -u, --urgency <lvl>  low, normal, critical
#   -i, --icon <name>    Icon name or path
#   --wrap               Run command and notify on completion
#   --sound              Play sound (if available)

set -uo pipefail

# Defaults
TITLE="Claude Code"
URGENCY="normal"
ICON=""
SOUND=false
WRAP=false

show_help() {
    cat << 'EOF'
notify.sh - Desktop notification when tasks complete

Usage:
  notify.sh [options] <message>
  notify.sh --wrap <command...>

Options:
  -t, --title <title>   Notification title (default: "Claude Code")
  -u, --urgency <lvl>   Urgency: low, normal, critical
  -i, --icon <name>     Icon name or path
  --wrap                Run command and notify on completion
  --sound               Play sound (if available)

Examples:
  # Simple notification
  notify.sh "Build complete"

  # With title
  notify.sh -t "npm" "Install finished"

  # Critical notification
  notify.sh -u critical "Tests failed!"

  # Wrap a command
  notify.sh --wrap npm run build
  # Equivalent to: npm run build && notify.sh "Success" || notify.sh -u critical "Failed"

  # Chain with commands
  make build && notify.sh "Build done" || notify.sh -u critical "Build failed"

Supported notification systems:
  - notify-send (Linux)
  - osascript (macOS)
  - terminal-notifier (macOS, if installed)
  - powershell (Windows/WSL)

EOF
    exit 0
}

# Detect notification method
detect_notifier() {
    if command -v notify-send &>/dev/null; then
        echo "notify-send"
    elif command -v terminal-notifier &>/dev/null; then
        echo "terminal-notifier"
    elif command -v osascript &>/dev/null; then
        echo "osascript"
    elif command -v powershell.exe &>/dev/null; then
        echo "powershell"
    else
        echo "echo"
    fi
}

# Send notification
send_notification() {
    local title="$1"
    local message="$2"
    local urgency="$3"
    local icon="$4"

    local notifier=$(detect_notifier)

    case "$notifier" in
        notify-send)
            local args=(-u "$urgency")
            [[ -n "$icon" ]] && args+=(-i "$icon")
            notify-send "${args[@]}" "$title" "$message" 2>/dev/null || true
            ;;
        terminal-notifier)
            local args=(-title "$title" -message "$message")
            [[ "$urgency" == "critical" ]] && args+=(-sound "Basso")
            terminal-notifier "${args[@]}" 2>/dev/null || true
            ;;
        osascript)
            osascript -e "display notification \"$message\" with title \"$title\"" 2>/dev/null || true
            ;;
        powershell)
            powershell.exe -Command "
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                \$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
                \$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(\$template)
                \$text = \$xml.GetElementsByTagName('text')
                \$text[0].AppendChild(\$xml.CreateTextNode('$title')) | Out-Null
                \$text[1].AppendChild(\$xml.CreateTextNode('$message')) | Out-Null
                \$toast = [Windows.UI.Notifications.ToastNotification]::new(\$xml)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Claude Code').Show(\$toast)
            " 2>/dev/null || true
            ;;
        *)
            # Fallback to terminal bell and echo
            printf "\a"
            echo "[$title] $message"
            ;;
    esac

    # Play sound if requested
    if $SOUND; then
        play_sound "$urgency"
    fi
}

# Play notification sound
play_sound() {
    local urgency="$1"

    if command -v paplay &>/dev/null; then
        # PulseAudio (Linux)
        local sound="/usr/share/sounds/freedesktop/stereo/complete.oga"
        [[ "$urgency" == "critical" ]] && sound="/usr/share/sounds/freedesktop/stereo/dialog-error.oga"
        paplay "$sound" 2>/dev/null &
    elif command -v afplay &>/dev/null; then
        # macOS
        afplay /System/Library/Sounds/Glass.aiff 2>/dev/null &
    else
        # Terminal bell
        printf "\a"
    fi
}

# Parse arguments
MESSAGE=""
COMMAND=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            ;;
        -t|--title)
            TITLE="$2"
            shift 2
            ;;
        -u|--urgency)
            URGENCY="$2"
            shift 2
            ;;
        -i|--icon)
            ICON="$2"
            shift 2
            ;;
        --sound)
            SOUND=true
            shift
            ;;
        --wrap)
            WRAP=true
            shift
            COMMAND=("$@")
            break
            ;;
        *)
            MESSAGE="$1"
            shift
            ;;
    esac
done

# Wrap mode: run command and notify
if $WRAP; then
    if [[ ${#COMMAND[@]} -eq 0 ]]; then
        echo "Error: No command specified for --wrap" >&2
        exit 1
    fi

    start_time=$(date +%s)
    cmd_str="${COMMAND[*]}"

    if "${COMMAND[@]}"; then
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        send_notification "$TITLE" "✓ Command succeeded (${duration}s): $cmd_str" "normal" "$ICON"
        exit 0
    else
        exit_code=$?
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        send_notification "$TITLE" "✗ Command failed (exit $exit_code, ${duration}s): $cmd_str" "critical" "$ICON"
        exit $exit_code
    fi
fi

# Simple notification mode
if [[ -z "$MESSAGE" ]]; then
    echo "Error: No message specified" >&2
    echo "Usage: notify.sh <message>" >&2
    exit 1
fi

send_notification "$TITLE" "$MESSAGE" "$URGENCY" "$ICON"
