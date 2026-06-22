#!/bin/bash
# send_report_email.sh <to> <subject> <body_file>
# Sends an email via the macOS Mail.app (uses the default account / iCloud).
# Env-var passing avoids AppleScript string-injection from the subject/body.
set -eu
TO="$1"; SUBJ="$2"; BODYFILE="$3"
export TO SUBJ BODYFILE
osascript <<'APPLE'
set theTo to system attribute "TO"
set theSubject to system attribute "SUBJ"
set theBodyFile to system attribute "BODYFILE"
set theBody to (do shell script "cat " & quoted form of theBodyFile)
tell application "Mail"
    set m to make new outgoing message with properties {subject:theSubject, content:theBody, visible:false}
    tell m to make new to recipient at end of to recipients with properties {address:theTo}
    send m
end tell
APPLE
echo "sent: $SUBJ -> $TO"
