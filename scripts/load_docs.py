"""Load .docx files from a directory into ChromaDB.

Usage:
    uv run python scripts/load_docs.py --dir ./docs
    uv run python scripts/load_docs.py --dir ./docs --collection MY_COLLECTION

The directory structure determines topic metadata:
    docs/
    ├── hr/           <- topic="hr"
    │   └── policy.docx
    └── legal/        <- topic="legal"
        └── contract.docx
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env (local dev) or .env.prod
load_dotenv(Path(__file__).parent.parent / ".env")
load_dotenv(Path(__file__).parent.parent / ".env.prod", override=False)

# Add src/ to path for module imports when running as a standalone script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class _SimpleLogger:
    """Minimal logger shim — prints to stdout/stderr."""

    def info(self, msg):
        print(f"[INFO]  {msg}")

    def warning(self, msg):
        print(f"[WARN]  {msg}")

    def error(self, msg):
        print(f"[ERROR] {msg}", file=sys.stderr)

    def debug(self, msg):
        pass  # suppress debug output in scripts


def main():
    parser = argparse.ArgumentParser(
        description="Sync .docx files from a directory into a ChromaDB collection."
    )
    parser.add_argument("--dir", required=True, help="Root directory with .docx files")
    parser.add_argument(
        "--collection",
        default=os.getenv("COLLECTION_NAME", "PRODUCTION_COLLECTION"),
        help="ChromaDB collection name (default: $COLLECTION_NAME env var)",
    )
    args = parser.parse_args()

    try:
        from modules.chroma_ext.scripts.db_writer import sync_docx_directory_to_collection
    except ImportError as e:
        print(f"Import error: {e}", file=sys.stderr)
        print("Make sure 'uv sync' has been run and src/ is accessible.", file=sys.stderr)
        sys.exit(1)

    required = ["OPENAI_API_KEY", "OPENAI_FOLDER_ID"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    if not Path(args.dir).exists():
        print(f"Directory not found: {args.dir}", file=sys.stderr)
        sys.exit(1)

    logger = _SimpleLogger()
    logger.info(f"Source directory : {args.dir}")
    logger.info(f"Target collection: {args.collection}")
    logger.info(f"ChromaDB         : {os.getenv('CHROMA_HOST', '127.0.0.1')}:{os.getenv('CHROMA_PORT', '8000')}")

    sync_docx_directory_to_collection(
        logger=logger,
        root_dir=args.dir,
        collection_name=args.collection,
        api_key=os.environ["OPENAI_API_KEY"],
        folder_id=os.environ["OPENAI_FOLDER_ID"],
        api_url=os.getenv(
            "EMBEDDING_API",
            "https://llm.api.cloud.yandex.net:443/foundationModels/v1/textEmbedding",
        ),
        host=os.getenv("CHROMA_HOST", "127.0.0.1"),
        port=int(os.getenv("CHROMA_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
