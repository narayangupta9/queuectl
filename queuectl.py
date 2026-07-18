import argparse
import json
import sys
import uuid
from datetime import datetime, UTC
import multiprocessing
import sqlite3
from db import init_db, get_db, get_config, set_config
from worker import QueueWorker

# 1. Top-level helper function so Windows multiprocessing can pickle it safely
def run_worker_process(worker_id):
    worker = QueueWorker(worker_id)
    worker.start()

def cmd_enqueue(args):
    try:
        data = json.loads(args.json_data)
    except json.JSONDecodeError:
        print("Error: Invalid JSON payload provided.")
        sys.exit(1)

    job_id = data.get("id", str(uuid.uuid4()))
    command = data.get("command")
    if not command:
        print("Error: Missing required field 'command' in JSON.")
        sys.exit(1)
        
    max_retries = int(data.get("max_retries", get_config("max_retries", 3)))
    # Fixed the Python 3.13 deprecation warning by using UTC timezone-aware objects
    now = datetime.now(UTC).isoformat()

    conn = get_db()
    try:
        with conn:
            conn.execute(
                """INSERT INTO jobs (id, command, state, attempts, max_retries, run_at, created_at, updated_at)
                   VALUES (?, ?, 'pending', 0, ?, ?, ?, ?)""",
                (job_id, command, max_retries, now, now, now)
            )
        print(f"Successfully enqueued job '{job_id}'")
    except sqlite3.IntegrityError:
        print(f"Error: A job with ID '{job_id}' already exists.")
    finally:
        conn.close()

def cmd_worker_start(args):
    print(f"Spawning {args.count} worker process(es)... Press Ctrl+C to terminate gracefully.")
    processes = []
    for i in range(args.count):
        # We pass the top-level named function here instead of a lambda
        p = multiprocessing.Process(target=run_worker_process, args=(i,))
        p.start()
        processes.append(p)
        
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\nOrchestrator shutting down workers...")

def cmd_status(args):
    conn = get_db()
    cursor = conn.execute("SELECT state, COUNT(*) as count FROM jobs GROUP BY state")
    rows = cursor.fetchall()
    conn.close()
    
    stats = {state: 0 for state in ['pending', 'processing', 'completed', 'failed', 'dead']}
    for row in rows:
        stats[row['state']] = row['count']
        
    print("=" * 30)
    print(" QUEUECTL ENGINE SYSTEM STATUS ")
    print("=" * 30)
    for state, count in stats.items():
        print(f" {state.upper().ljust(12)} : {count}")
    print("=" * 30)

def cmd_list(args):
    conn = get_db()
    cursor = conn.execute("SELECT id, command, state, attempts, run_at FROM jobs WHERE state = ?", (args.state,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print(f"No jobs found with state '{args.state}'")
        return

    print(f"{'JOB ID':<15} {'ATTEMPTS':<10} {'COMMAND'}")
    print("-" * 50)
    for row in rows:
        print(f"{row['id']:<15} {row['attempts']:<10} {row['command']}")

def cmd_dlq_list(args):
    args.state = 'dead'
    cmd_list(args)

def cmd_dlq_retry(args):
    now = datetime.now(UTC).isoformat()
    conn = get_db()
    with conn:
        cursor = conn.execute("UPDATE jobs SET state = 'pending', attempts = 0, run_at = ?, updated_at = ? WHERE id = ? AND state = 'dead'", (now, now, args.job_id))
        changes = cursor.rowcount
    conn.close()
    
    if changes > 0:
        print(f"Job '{args.job_id}' successfully recycled from DLQ to 'pending'.")
    else:
        print(f"Error: Job '{args.job_id}' not found in DLQ (dead) status.")

def cmd_config_set(args):
    if args.key not in ['max-retries', 'backoff-base']:
        print("Error: Key must be 'max-retries' or 'backoff-base'")
        sys.exit(1)
    
    db_key = args.key.replace('-', '_')
    set_config(db_key, args.value)
    print(f"Configuration globally updated: {args.key} = {args.value}")

def main():
    init_db()
    parser = argparse.ArgumentParser(description="QueueCTL CLI Client Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Enqueue
    p_enq = subparsers.add_parser("enqueue", help="Add a new job payload to the system queue")
    p_enq.add_argument("json_data", help="JSON string representing job specification")
    p_enq.set_defaults(func=cmd_enqueue)

    # Worker Orchestration
    p_work = subparsers.add_parser("worker", help="Manage background parallel execution engines")
    w_sub = p_work.add_subparsers(dest="subcommand", required=True)
    w_start = w_sub.add_parser("start", help="Spin up continuous worker engines")
    w_start.add_argument("--count", type=int, default=1, help="Number of worker instances to parallel spawn")
    w_start.set_defaults(func=cmd_worker_start)

    # Status Evaluation
    p_stat = subparsers.add_parser("status", help="Get summary aggregation of all engine metrics")
    p_stat.set_defaults(func=cmd_status)

    # State Selective Listing
    p_list = subparsers.add_parser("list", help="Print structured list details filtering by state status")
    p_list.add_argument("--state", required=True, choices=['pending', 'processing', 'completed', 'failed', 'dead'])
    p_list.set_defaults(func=cmd_list)

    # Dead Letter Queue Handling
    p_dlq = subparsers.add_parser("dlq", help="Inspect and interact with Dead Letter Queue items")
    dlq_sub = p_dlq.add_subparsers(dest="subcommand", required=True)
    dlq_list = dlq_sub.add_parser("list", help="View dead items")
    dlq_list.set_defaults(func=cmd_dlq_list)
    dlq_retry = dlq_sub.add_parser("retry", help="Re-queue a dead item back to ready pool")
    dlq_retry.add_argument("job_id", help="Target unique string tracking ID to recover")
    dlq_retry.set_defaults(func=cmd_dlq_retry)

    # System Variables Alteration
    p_conf = subparsers.add_parser("config", help="Manage global properties")
    conf_sub = p_conf.add_subparsers(dest="subcommand", required=True)
    conf_set = conf_sub.add_parser("set", help="Change a default value globally")
    conf_set.add_argument("key", choices=['max-retries', 'backoff-base'])
    conf_set.add_argument("value", help="Assigned property parameter configuration metric target value")
    conf_set.set_defaults(func=cmd_config_set)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
