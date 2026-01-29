#!/usr/bin/env bash
if [[ -z "${BASH_VERSION:-}" ]]; then
  exec /usr/bin/env bash "$0" "$@"
fi
set -Eeuo pipefail

# --- resolve repo root ---
p="$(dirname "$(dirname "$(realpath "$0")")")"
cd "$p"

# --- env & dirs ---
source "$p/.env"
mkdir -p "${DATA_PATH}" "${LOGS_PATH}"

# Default fetcher behavior (interactive or dry-run)
FETCHER_DEFAULT_MODE="${FETCHER_DEFAULT_MODE:-interactive}"
case "${FETCHER_DEFAULT_MODE}" in
  interactive) FETCHER_DEFAULT_FLAG="--interactive" ;;
  dry-run) FETCHER_DEFAULT_FLAG="--dry-run" ;;
  *)
    echo "Warning: unknown FETCHER_DEFAULT_MODE='${FETCHER_DEFAULT_MODE}', defaulting to interactive"
    FETCHER_DEFAULT_FLAG="--interactive"
    ;;
esac

# Optional downstream project filter (single project by exact name)
PIPELINE_PROJECT="${PIPELINE_PROJECT:-}"
PROJECT_FILTER_ARGS=()
if [[ -n "${PIPELINE_PROJECT}" ]]; then
  PROJECT_FILTER_ARGS=(--project "${PIPELINE_PROJECT}")
fi
# Cross-platform ISO 8601 timestamp (UTC) — works on macOS & Linux
iso_ts() {
  if command -v gdate >/dev/null 2>&1; then
    gdate -Is
  else
    # BSD date: YYYY-MM-DDTHH:MM:SS+HHMM -> insert colon in offset
    date -u +"%Y-%m-%dT%H:%M:%S%z" | sed -E 's/([+-][0-9]{2})([0-9]{2})$/\1:\2/'
  fi
}

# --- pipeline logging setup ---
RUN_ID="$(date '+%Y%m%d-%H%M%S')"
PIPELINE_LOG="${LOGS_PATH}/pipeline_${RUN_ID}.log"
ln -sf "$(basename "$PIPELINE_LOG")" "${LOGS_PATH}/pipeline_latest.log"

# redirect *everything* from this script to the pipeline log (and stdout)
exec > >(stdbuf -oL -eL tee -a "$PIPELINE_LOG") 2>&1

START_TS="$(iso_ts)"
STATUS="started"
PROJECTS_SELECTED=""
DOWNLOADED_FILES=0
HAD_CHANGES=false

record_status() {
  local final_status="$1"
  local reason="${2:-}"
  local end_ts
  end_ts="$(iso_ts)"
  # append one JSON object per run (easy to grep/parse later)
  printf '{"run_id":"%s","start":"%s","end":"%s","status":"%s","reason":"%s","projects_selected":"%s","downloaded_files":%s,"had_changes":%s}\n' \
    "$RUN_ID" "$START_TS" "$end_ts" "$final_status" "$reason" \
    "${PROJECTS_SELECTED//\"/\\\"}" "${DOWNLOADED_FILES}" "${HAD_CHANGES}" \
    >> "${LOGS_PATH}/runs.jsonl"
}

on_err() {
  echo "!! $(iso_ts) pipeline failed (line $BASH_LINENO)"
  record_status "failed" "error"
}
trap on_err ERR

on_exit() {
  # if not already recorded as failed/ok/skipped, mark as failed (unexpected exit)
  # shellcheck disable=SC2154
  if [[ "${STATUS}" == "started" ]]; then
    record_status "failed" "unexpected_exit"
  fi
}
trap on_exit EXIT

echo "=== $(iso_ts) :: pipeline start (RUN_ID=${RUN_ID}) ==="
echo "Repo: $p"
echo "DATA_PATH: ${DATA_PATH}"
echo "LOGS_PATH: ${LOGS_PATH}"

# --- housekeeping: prune logs if > 100 MB ---
SIZE_LIMIT_MB=100
FOLDER_SIZE_MB=$(du -sm "${LOGS_PATH}" | awk '{print $1}')
if (( FOLDER_SIZE_MB > SIZE_LIMIT_MB )); then
  echo "Logs folder ${FOLDER_SIZE_MB} MB > ${SIZE_LIMIT_MB} MB — pruning older logs"
  # delete only old pipeline_* logs; keep runs.jsonl
  find "${LOGS_PATH}" -maxdepth 1 -type f -name 'pipeline_*.log' -mtime +14 -print -delete || true
fi

scripts_folder="${p}/qfieldcloud_fetcher"

# --- helper to run a python script with per-script log + pipeline echo ---
run_script() {
  local script_basename="$1"; shift
  local logfile="$LOGS_PATH/${script_basename}.log"
  echo "--- $(iso_ts) :: running ${script_basename}.py $* ---"
  if ! { ${POETRY_PATH} run python3 "${scripts_folder}/${script_basename}.py" "$@" 2>&1 | tee -a "$logfile"; }; then
    echo "!!! ${script_basename} failed — see $logfile"
    STATUS="failed"
    record_status "failed" "script_failed:${script_basename}"
    exit 1
  fi
  echo "--- $(iso_ts) :: finished ${script_basename}.py ---"
}

# --- 1) Fetcher FIRST (improved) ---
run_script fetcher "${FETCHER_DEFAULT_FLAG}"

# read fetcher summary (if jq is available)
SUMMARY_JSON="${DATA_PATH}/last_fetch_summary.json"
if command -v jq >/dev/null 2>&1 && [[ -f "$SUMMARY_JSON" ]]; then
  PROJECTS_SELECTED=$(jq -r '.projects_selected | join(",")' "$SUMMARY_JSON")
  DOWNLOADED_FILES=$(jq -r '.downloaded_files' "$SUMMARY_JSON")
  HAD_CHANGES=$(jq -r '.had_changes' "$SUMMARY_JSON")
else
  # fallbacks if jq missing
  PROJECTS_SELECTED=""
  DOWNLOADED_FILES=0
  HAD_CHANGES=false
fi
echo "Fetcher summary: projects_selected='${PROJECTS_SELECTED}', downloaded_files=${DOWNLOADED_FILES}, had_changes=${HAD_CHANGES}"

MARKER="${DATA_PATH}/.qfc_changed"
if [[ ! -f "$MARKER" ]]; then
  echo "No QFieldCloud changes — stopping pipeline."
  STATUS="skipped"
  record_status "skipped" "no_changes"
  exit 0
fi

# --- 2) Clean CSV staging dirs (inputs already cleaned by fetcher) ---
rm -rf "${DATA_PATH}/raw_csv" "${DATA_PATH}/formatted_csv"

# --- 3) Downstream steps (only if changes) ---
# after you confirmed HAD_CHANGES and before renamer/resizer:
run_script "stage_to_nextcloud_raw" "${PROJECT_FILTER_ARGS[@]}"

# ... your existing steps ...
run_script "csv_generator" "${PROJECT_FILTER_ARGS[@]}"
run_script "csv_formatter" "${PROJECT_FILTER_ARGS[@]}"
run_script "fields_creator" "${PROJECT_FILTER_ARGS[@]}"
run_script "db_updater" "${PROJECT_FILTER_ARGS[@]}"
run_script "directus_link_maker" "${PROJECT_FILTER_ARGS[@]}"
run_script "pictures_renamer" "${PROJECT_FILTER_ARGS[@]}"
run_script "pictures_resizer" "${PROJECT_FILTER_ARGS[@]}"
run_script "pictures_metadata_editor" "${PROJECT_FILTER_ARGS[@]}"

# NEW: safe cleanup (remove DCIM + raw only for fully processed photos)
run_script "pictures_finalizer" "${PROJECT_FILTER_ARGS[@]}"

STATUS="ok"
record_status "ok" "completed"
echo "=== $(iso_ts) :: pipeline completed successfully (RUN_ID=${RUN_ID}) ==="
