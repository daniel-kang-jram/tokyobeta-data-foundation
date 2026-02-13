#!/usr/bin/env bash
set -euo pipefail

APP_URL="${APP_URL:-https://evidence.jram.jp}"

# After auth is enabled, unauthenticated requests should redirect to Cognito.
# We don't assume a specific Cognito domain prefix here.

check() {
  local path="$1"
  local url="$APP_URL$path"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" -L --max-redirs 0 "$url" || true)
  echo "$url -> $code"
}

echo "Smoke testing Evidence hosting"
echo "APP_URL=$APP_URL"

check "/"
check "/occupancy"
check "/moveins"
check "/moveouts"
check "/geography"

echo "If all requests return 302, auth redirect is active."
