"""Show the database a backend launch will use without opening or changing it."""

from .config import Settings


def main() -> None:
    settings = Settings()
    path = settings.storage_path.expanduser().resolve()
    print(f"Portfolio storage: {path} ({settings.storage_path_source})")
    print(f"Existing file: {'yes' if path.is_file() else 'no'}")


if __name__ == "__main__":
    main()
