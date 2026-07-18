#!/usr/bin/env bash
echo "=== 1. Initializing and Enqueuing Test Jobs ==="
python3 queuectl.py enqueue '{"id":"good-job", "command":"echo '\''Task Succeeded'\''"}'
python3 queuectl.py enqueue '{"id":"bad-job", "command":"exit 42", "max_retries":2}'

echo -e "\n=== 2. Checking Starting Status ==="
python3 queuectl.py status

echo -e "\n=== 3. Starting Workers for 5 seconds to process items ==="
python3 queuectl.py worker start --count 2 &
WORKER_PID=$!

sleep 6
kill -INT $WORKER_PID
wait $WORKER_PID 2>/dev/null

echo -e "\n=== 4. System Status Post Worker Run (Checking DLQ transition) ==="
python3 queuectl.py status

echo -e "\n=== 5. Listing Dead Letter Queue ==="
python3 queuectl.py dlq list

echo -e "\n=== 6. Re-enqueuing Dead Job for Recovery ==="
python3 queuectl.py dlq retry bad-job

echo -e "\n=== 7. Final Verification of Status ==="
python3 queuectl.py status