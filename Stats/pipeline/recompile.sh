#!/bin/bash
# =============================================================================
# recompile.sh
# 2026 Alameda Little League Majors — Full Stats Recompile
#
# Validates all game files, rebuilds the Excel backup, then pushes live data
# to Google Sheets. Safe to run any time; will fail loudly if validation
# finds errors so you never push bad data silently.
#
# Usage (manual):
#   bash /path/to/Stats/pipeline/recompile.sh
#
# Automated daily runs are handled by the macOS LaunchAgent installed via
#   bash /path/to/Stats/pipeline/install_autorun.sh
# =============================================================================

# Resolve the Stats directory from this script's own location
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
STATS_DIR="$( dirname "$SCRIPT_DIR" )"

LOG_FILE="$STATS_DIR/pipeline/recompile.log"
PYTHON="$(which python3)"

# Write timestamped log entries
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "======================================================"
log "Starting recompile — Stats dir: $STATS_DIR"

# ── Step 1: Install dependencies if needed ────────────────────────────────────
"$PYTHON" -c "import gspread, google.auth" 2>/dev/null || {
    log "Installing gspread and google-auth..."
    "$PYTHON" -m pip install --quiet gspread google-auth
}

# ── Step 2: Validate game files ───────────────────────────────────────────────
log "Running validate.py..."
cd "$STATS_DIR" || { log "ERROR: Cannot cd to $STATS_DIR"; exit 1; }

"$PYTHON" pipeline/validate.py >> "$LOG_FILE" 2>&1
VALIDATE_EXIT=$?

if [ $VALIDATE_EXIT -ne 0 ]; then
    log "ERROR: Validation failed — aborting. Check pipeline/recompile.log for details."
    exit 1
fi

log "Validation passed."

# ── Step 3: Build Excel backup ────────────────────────────────────────────────
log "Running compile.py (Excel backup)..."
"$PYTHON" pipeline/compile.py >> "$LOG_FILE" 2>&1 || {
    log "WARNING: Excel compile failed (continuing to Sheets push)"
}

# ── Step 4: Push to Google Sheets ─────────────────────────────────────────────
log "Running compile_sheets.py (Google Sheets push)..."
"$PYTHON" pipeline/compile_sheets.py >> "$LOG_FILE" 2>&1
SHEETS_EXIT=$?

if [ $SHEETS_EXIT -eq 0 ]; then
    log "SUCCESS — Google Sheet updated."
else
    log "ERROR: Google Sheets push failed. Check pipeline/recompile.log for details."
    exit 1
fi

# ── Step 5: Data quality audit ────────────────────────────────────────────────
log "Running audit.py (data quality check)..."
"$PYTHON" pipeline/audit.py >> "$LOG_FILE" 2>&1
AUDIT_EXIT=$?

if [ $AUDIT_EXIT -eq 0 ]; then
    log "Audit passed — stats look clean."
else
    log "AUDIT: Errors found in compiled stats. Review pipeline/recompile.log."
    # Send a notification email via macOS
    osascript -e "display notification \"Stats audit found errors — check recompile.log\" with title \"⚠️ ALL MAJORS STATS\" sound name \"Basso\"" 2>/dev/null || true
fi

log "Done."
