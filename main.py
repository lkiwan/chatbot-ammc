import argparse
import itertools
import os
import sys
import threading
import time

from dotenv import load_dotenv

from build_index import build_index
from chat import answer_stream, warm_cache


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Chatbot RAG multi-rapports (Groq).")
    parser.add_argument(
        "command", nargs="?", default="chat",
        choices=["ingest", "index", "chat", "serve", "all"],
        help="chat (defaut) | ingest: extrait+indexe les nouveaux PDF de data/pdfs | index: reconstruit tout | serve: plateforme web | all: index puis chat",
    )
    parser.add_argument("--force", action="store_true", help="Reconstruit l'index existant")
    parser.add_argument("--host", default="127.0.0.1", help="Hote pour serve")
    parser.add_argument("--port", type=int, default=8000, help="Port pour serve")
    args = parser.parse_args()

    if args.command == "serve":
        serve(host=args.host, port=args.port)
        return

    if args.command in ("ingest", "index", "all"):
        build_index(force=args.force)
    if args.command in ("chat", "all"):
        threading.Thread(target=warm_cache, daemon=True).start()
        run_chat()


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import subprocess

    import uvicorn

    frontend = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
    print("Compilation du frontend pour servir la derniere version ...")
    subprocess.check_call(["npm", "run", "build"], cwd=frontend, shell=os.name == "nt")
    print(f"Plateforme web sur http://{host}:{port}")
    threading.Thread(target=warm_cache, daemon=True).start()
    uvicorn.run("api.main:app", host=host, port=port, log_level="info")


def run_chat() -> None:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        sys.exit(
            "GROQ_API_KEY manquante. Copiez .env.example vers .env et renseignez la cle "
            "(https://console.groq.com/keys)."
        )

    print("Chat RAG - pose tes questions sur le rapport (Ctrl+C pour quitter).\n")
    history: list[dict] = []
    while True:
        try:
            question = input("Vous : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAu revoir.")
            return
        if not question:
            continue
        if question.lower() in ("quit", "exit", "bye"):
            return

        print("Assistant : ", end="", flush=True)
        reply, sources = "", []
        stop = threading.Event()

        def spinner() -> None:
            for c in itertools.cycle([".", "..", "..."]):
                if stop.is_set():
                    break
                print("\rReponse en cours" + c + "      ", end="", flush=True)
                time.sleep(0.4)

        spin = threading.Thread(target=spinner, daemon=True)
        spin.start()
        try:
            for chunk, src in answer_stream(question, history):
                if src:
                    sources = src
                reply += chunk
        except Exception as exc:
            stop.set()
            print("\r" + " " * 40 + "\r", end="", flush=True)
            print(f"\n[Erreur API : {type(exc).__name__}] Reposez la question ou reessayez.")
            continue
        stop.set()
        print("\r" + " " * 40 + "\r", end="", flush=True)
        print(reply)
        print(f"Sources : pages {', '.join(sources)}")
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()