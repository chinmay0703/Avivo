# starts all 4 services - embedding, rag, vision, and the telegram bot

import subprocess, sys, os, signal, time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
processes = []


def start_service(name, module, port=None, script=None):
    env = os.environ.copy()
    if port:
        cmd = [sys.executable, "-m", "uvicorn", module, "--host", "0.0.0.0", "--port", str(port)]
    elif script:
        cmd = [sys.executable, script]
    else:
        cmd = [sys.executable, "-m", module]

    print(f"starting {name}...")
    proc = subprocess.Popen(cmd, cwd=BASE_DIR, env=env)
    processes.append((name, proc))
    return proc


def shutdown(signum=None, frame=None):
    print("\nshutting down...")
    for name, proc in processes:
        try:
            proc.terminate()
        except:
            pass
    for name, proc in processes:
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()
    print("done")
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)


def main():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))

    # start the api services
    start_service("embedding", "services.embedding.app:app", port=8001)
    time.sleep(2)  # give it time to load model and ingest docs

    start_service("rag", "services.rag.app:app", port=8002)
    start_service("vision", "services.vision.app:app", port=8003)
    time.sleep(1)

    # start telegram bot
    start_service("bot", module=None, script=os.path.join(BASE_DIR, "services", "bot_gateway", "app.py"))

    print("\nall services running!")
    print("  embedding: http://localhost:8001")
    print("  rag:       http://localhost:8002")
    print("  vision:    http://localhost:8003")
    print("  bot:       telegram polling\n")
    print("ctrl+c to stop\n")

    # keep checking if anything crashed
    try:
        while True:
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"WARNING: {name} exited with code {proc.poll()}")
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
