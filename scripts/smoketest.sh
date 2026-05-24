#!/bin/bash
set -e

# Smoke test for workflow-open-ai
# Starts server, tests endpoints, verifies responses
# Usage: ./scripts/smoketest.sh [--help]

HELP=0
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    HELP=1
fi

if [ $HELP -eq 1 ]; then
    cat <<EOF
Smoke test for workflow-open-ai

Starts the server, runs HTTP tests, stops server, exits with status.

Usage:
  ./scripts/smoketest.sh [options]

Options:
  --help, -h    Show this help

Environment:
  HOST          Server host (default: localhost)
  PORT          Server port (default: 8340)
  API_KEY       API key to use (default: from api_keys.yaml example)

Exits:
  0 - All tests passed
  1 - Test failed
  2 - Server failed to start
EOF
    exit 0
fi

HOST="${HOST:-localhost}"
PORT="${PORT:-8340}"
API_KEY="${API_KEY:-sk-your-caller-key-here}"
URL="http://$HOST:$PORT"
LOG_FILE="/tmp/smoketest-server.log"

echo "Starting server on $URL..."
rm -f "$LOG_FILE"

# Start server in background
uv run uvicorn workflow_open_ai.main:app --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# Wait for server to be ready (max 10 seconds)
echo "Waiting for server to be ready..."
for i in {1..50}; do
    if curl -s "$URL/health" > /dev/null 2>&1; then
        echo "Server ready"
        break
    fi
    if [ $i -eq 50 ]; then
        echo "FAIL: Server did not start within 10 seconds"
        cat "$LOG_FILE"
        kill $SERVER_PID 2>/dev/null || true
        exit 2
    fi
    sleep 0.2
done

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

TESTS_PASSED=0
TESTS_FAILED=0

test_case() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_status="$5"
    local check_pattern="$6"

    printf "%-50s " "Testing $name..."

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" \
            -H "Authorization: Bearer $API_KEY" \
            "$URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" \
            -X POST \
            -H "Authorization: Bearer $API_KEY" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$URL$endpoint")
    fi

    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$status_code" != "$expected_status" ]; then
        echo -e "${RED}FAIL${NC} (got $status_code, expected $expected_status)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi

    if [ -n "$check_pattern" ]; then
        if ! echo "$body" | grep -q "$check_pattern"; then
            echo -e "${RED}FAIL${NC} (response check failed)"
            echo "Response: $body"
            TESTS_FAILED=$((TESTS_FAILED + 1))
            return 1
        fi
    fi

    echo -e "${GREEN}PASS${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    return 0
}

# Run tests
test_case \
    "GET /health" \
    "GET" \
    "/health" \
    "" \
    "200" \
    "healthy"

test_case \
    "GET /v1/models (auth required)" \
    "GET" \
    "/v1/models" \
    "" \
    "200" \
    "object.*list"

test_case \
    "GET /v1/models (has default_workflow)" \
    "GET" \
    "/v1/models" \
    "" \
    "200" \
    "default_workflow"

test_case \
    "POST /v1/chat/completions (success)" \
    "POST" \
    "/v1/chat/completions" \
    '{"model":"default_workflow","messages":[{"role":"user","content":"hello"}]}' \
    "200" \
    "chat.completion"

test_case \
    "POST /v1/chat/completions (has id)" \
    "POST" \
    "/v1/chat/completions" \
    '{"model":"default_workflow","messages":[{"role":"user","content":"test"}]}' \
    "200" \
    "chatcmpl-"

test_case \
    "POST /v1/chat/completions (has choices)" \
    "POST" \
    "/v1/chat/completions" \
    '{"model":"default_workflow","messages":[{"role":"user","content":"test"}]}' \
    "200" \
    "choices"

test_case \
    "POST /v1/chat/completions (unknown model 400)" \
    "POST" \
    "/v1/chat/completions" \
    '{"model":"bad_model","messages":[{"role":"user","content":"test"}]}' \
    "400" \
    "model_not_found"

test_case \
    "POST /v1/chat/completions (missing model 400)" \
    "POST" \
    "/v1/chat/completions" \
    '{"messages":[{"role":"user","content":"test"}]}' \
    "400" \
    "invalid_request"

# No auth test (need to use curl without header)
printf "%-50s " "Testing GET /v1/models (no auth 401)..."
response=$(curl -s -w "\n%{http_code}" "$URL/v1/models")
status_code=$(echo "$response" | tail -n1)
if [ "$status_code" = "401" ]; then
    echo -e "${GREEN}PASS${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}FAIL${NC} (got $status_code, expected 401)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Stop server
echo ""
echo "Stopping server..."
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

# Summary
echo ""
echo "========================================"
echo "Tests passed: $TESTS_PASSED"
echo "Tests failed: $TESTS_FAILED"
echo "========================================"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed${NC}"
    exit 1
fi
