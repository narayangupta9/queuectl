import time
import subprocess
import sys
import os
import signal
from datetime import datetime, timedelta, UTC
from db import get_db, get_config

class QueueWorker:
    def __init__(self, worker_id):
        self.worker_id = worker_id
        self.running = True
        
    def stop_gracefully(self, signum, frame):
        print(f"[Worker-{self.worker_id}] Stop signal received. Finishing current job...")
        self.running = False

    def start(self):
        print(f"[Worker-{self.worker_id}] Started successfully.")

        while self.running:
            job = self._fetch_and_lock_job()
            if not job:
                time.sleep(1)
                continue
            
            self._execute_job(job)

        print(f"[Worker-{self.worker_id}] Shutdown complete.")

    def _fetch_and_lock_job(self):
        conn = get_db()
        try:
            # We use an EXCLUSIVE transaction here to lock the DB during the check-and-update window
            conn.execute("BEGIN EXCLUSIVE TRANSACTION;")
            now = datetime.now(UTC).isoformat()
            
            cursor = conn.execute(
                """SELECT * FROM jobs 
                   WHERE state IN ('pending', 'failed') 
                   AND run_at <= ? 
                   LIMIT 1""", (now,)
            )
            row = cursor.fetchone()
            
            if row:
                job = dict(row)
                conn.execute(
                    "UPDATE jobs SET state = 'processing', updated_at = ? WHERE id = ?",
                    (now, job['id'])
                )
                conn.commit()  # Lock released safely after state modification
                return job
            else:
                conn.rollback()
        except sqlite3.OperationalError:
            # If the DB is locked by another worker, roll back and try again next loop cycle
            try:
                conn.rollback()
            except:
                pass
            return None
        finally:
            conn.close()
        return None

    def _execute_job(self, job):
        print(f"[Worker-{self.worker_id}] Processing Job: {job['id']} -> Running: `{job['command']}`")
        
        try:
            result = subprocess.run(job['command'], shell=True, capture_output=True, text=True)
            exit_code = result.returncode
        except Exception as e:
            exit_code = -1

        now = datetime.now(UTC).isoformat()
        conn = get_db()
        
        if exit_code == 0:
            print(f"[Worker-{self.worker_id}] Job {job['id']} COMPLETED.")
            with conn:
                conn.execute(
                    "UPDATE jobs SET state = 'completed', updated_at = ? WHERE id = ?",
                    (now, job['id'])
                )
        else:
            new_attempts = job['attempts'] + 1
            max_retries = job['max_retries']
            
            if new_attempts > max_retries:
                print(f"[Worker-{self.worker_id}] Job {job['id']} FAILED permanently. Moving to DLQ.")
                with conn:
                    conn.execute(
                        "UPDATE jobs SET state = 'dead', attempts = ?, updated_at = ? WHERE id = ?",
                        (new_attempts, now, job['id'])
                    )
            else:
                backoff_base = float(get_config('backoff_base', 2))
                delay_seconds = int(backoff_base ** new_attempts)
                run_at = (datetime.now(UTC) + timedelta(seconds=delay_seconds)).isoformat()
                
                print(f"[Worker-{self.worker_id}] Job {job['id']} FAILED. Retrying in {delay_seconds}s (Attempt {new_attempts}/{max_retries}).")
                with conn:
                    conn.execute(
                        "UPDATE jobs SET state = 'failed', attempts = ?, run_at = ?, updated_at = ? WHERE id = ?",
                        (new_attempts, run_at, now, job['id'])
                    )
        conn.close()
