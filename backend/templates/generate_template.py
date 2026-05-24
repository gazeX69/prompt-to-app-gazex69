from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_TEMPLATE = PROJECT_ROOT / "templates" / "react-vite-ts"


def main() -> None:
    if not CANONICAL_TEMPLATE.exists():
        raise SystemExit(f"Canonical template missing: {CANONICAL_TEMPLATE}")

    print(f"Canonical react-vite-ts template: {CANONICAL_TEMPLATE}")
    print("No template generation performed; this project uses a single canonical template source.")


if __name__ == "__main__":
    main()
