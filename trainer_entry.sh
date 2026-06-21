#!/bin/sh
# Root entrypoint: make a mounted Railway volume (root-owned by default) writable
# by ftuser, then drop privileges and run the retrainer as ftuser (freqtrade is
# installed under ftuser's home, so it must run as ftuser).
set -e
if [ -d /data ]; then
  chown -R ftuser:ftuser /data 2>/dev/null || true
fi
exec runuser -u ftuser -- python3 /app/freqtrade_retrain.py
