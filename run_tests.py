import os
import subprocess
import time
import sys

def run_cmd(cmd_str):
    print(f"\n> Running: {cmd_str}")
    full_cmd = f'"{sys.executable}" {cmd_str}'
    return subprocess.run(full_cmd, shell=True, text=True)

def main():
    print("=== 1. Enqueuing Test Jobs ===")
    # Using clean single/double quote separation to avoid escaping issues
    run_cmd("queuectl.py enqueue \"{\\\"id\\\":\\\"good-job\\\", \\\"command\\\":\\\"echo Task Succeeded\\\"}\"")
    run_cmd("queuectl.py enqueue \"{\\\"id\\\":\\\"bad-job\\\", \\\"command\\\":\\\"cmd /c exit 42\\\", \\\"max_retries\\\":2}\"")
    
    print("\n=== 2. System Status ===")
    run_cmd("queuectl.py status")
    
    print("\n=== 3. Spawning Workers Background Processes ===")
    worker_proc = subprocess.Popen(f'"{sys.executable}" queuectl.py worker start --count 2', shell=True)
    
    print("Waiting 8 seconds for processing...")
    time.sleep(8)
    
    print("Terminating background workers...")
    worker_proc.terminate()
    worker_proc.wait()
    
    print("\n=== 4. Post-Worker Run Status ===")
    run_cmd("queuectl.py status")

if __name__ == "__main__":
    main()
