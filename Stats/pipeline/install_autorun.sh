#!/bin/bash
# =============================================================================
# install_autorun.sh
# Installs a macOS LaunchAgent that runs recompile.sh every day at 6:00 AM.
#
# Run ONCE from your terminal:
#   bash /path/to/Stats/pipeline/install_autorun.sh
#
# To change the run time, re-run this script — it replaces the existing agent.
# To uninstall: bash /path/to/Stats/pipeline/install_autorun.sh --uninstall
# =============================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
STATS_DIR="$( dirname "$SCRIPT_DIR" )"
RECOMPILE_SH="$SCRIPT_DIR/recompile.sh"
PLIST_NAME="com.alamedallstats.recompile"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
LOG_OUT="$SCRIPT_DIR/launchd_stdout.log"
LOG_ERR="$SCRIPT_DIR/launchd_stderr.log"
PYTHON="$(which python3)"

# ── Uninstall mode ────────────────────────────────────────────────────────────
if [ "$1" = "--uninstall" ]; then
    echo "Uninstalling daily recompile..."
    launchctl unload "$PLIST_PATH" 2>/dev/null
    rm -f "$PLIST_PATH"
    echo "Done. Daily recompile has been removed."
    exit 0
fi

# ── Make recompile.sh executable ──────────────────────────────────────────────
chmod +x "$RECOMPILE_SH"

# ── Unload existing agent if present ──────────────────────────────────────────
if [ -f "$PLIST_PATH" ]; then
    echo "Replacing existing LaunchAgent..."
    launchctl unload "$PLIST_PATH" 2>/dev/null
fi

# ── Write the plist ───────────────────────────────────────────────────────────
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${RECOMPILE_SH}</string>
    </array>

    <!-- Run every day at 11:45 AM PT -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>11</integer>
        <key>Minute</key>
        <integer>45</integer>
    </dict>

    <!-- Also run immediately on load if the last scheduled run was missed -->
    <key>RunAtLoad</key>
    <false/>

    <key>StandardOutPath</key>
    <string>${LOG_OUT}</string>

    <key>StandardErrorPath</key>
    <string>${LOG_ERR}</string>

    <!-- Working directory -->
    <key>WorkingDirectory</key>
    <string>${STATS_DIR}</string>

    <!-- Environment — ensure python3 is found even in GUI context -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
PLIST

# ── Load the agent ────────────────────────────────────────────────────────────
launchctl load "$PLIST_PATH"
LOAD_EXIT=$?

if [ $LOAD_EXIT -eq 0 ]; then
    echo ""
    echo "✅  Daily recompile installed successfully!"
    echo ""
    echo "    Schedule:   Every day at 11:45 AM PT"
    echo "    Script:     $RECOMPILE_SH"
    echo "    Log file:   $SCRIPT_DIR/recompile.log"
    echo "    Plist:      $PLIST_PATH"
    echo ""
    echo "To run it right now (test it):"
    echo "    bash $RECOMPILE_SH"
    echo ""
    echo "To uninstall:"
    echo "    bash $SCRIPT_DIR/install_autorun.sh --uninstall"
else
    echo "ERROR: LaunchAgent failed to load (exit $LOAD_EXIT)."
    echo "Check that the plist is valid: plutil -lint $PLIST_PATH"
    exit 1
fi
