import argparse
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

OLD_PREFIX = "globex" + "_"
NEW_PREFIX = "chroma_"
SKIP_DIRS = {".git", "node_modules"}
SYMBOL_PATTERN = re.compile(r"\b" + re.escape(OLD_PREFIX))


def rename_tree(root: Path, check: bool = False) -> int:
    plans = []
    skipped = 0

    def raise_walk_error(error: OSError) -> None:
        raise error

    for directory, directories, filenames in os.walk(
        root, onerror=raise_walk_error, followlinks=False
    ):
        parent = Path(directory)
        directories[:] = [
            name
            for name in directories
            if name not in SKIP_DIRS
            and not (parent / name).is_symlink()
            and not (parent / name).is_junction()
        ]

        for name in filenames:
            path = parent / name
            if path.is_symlink():
                skipped += 1
                continue

            destination = (
                path.with_name(NEW_PREFIX + name[len(OLD_PREFIX):])
                if name.startswith(OLD_PREFIX)
                else path
            )

            original = path.read_bytes()
            updated = None

            if b"\0" in original:
                logger.debug(f"Skipping binary contents: {path}")
                skipped += 1
            else:
                try:
                    text = original.decode("utf-8")
                except UnicodeDecodeError:
                    logger.debug(f"Skipping non-UTF-8 contents: {path}")
                    skipped += 1
                else:
                    replacement = SYMBOL_PATTERN.sub(NEW_PREFIX, text)
                    if replacement != text:
                        updated = replacement.encode("utf-8")

            plans.append((path, destination, updated))

    # Check every destination before modifying any files.
    for source, destination, _ in plans:
        if source != destination and (
            destination.exists() or destination.is_symlink()
        ):
            raise FileExistsError(
                f"Cannot rename {source}: destination exists: {destination}"
            )

    if check:
        pending = sum(1 for _, _, updated in plans if updated is not None) + sum(
            1 for source, destination, _ in plans if source != destination
        )
        return 1 if pending > 0 else 0

    rewritten = 0
    renamed = 0

    for source, destination, updated in plans:
        if updated is not None:
            source.write_bytes(updated)
            rewritten += 1
            logger.info(f"Updated contents: {source}")

        if source != destination:
            source.rename(destination)
            renamed += 1
            logger.info(f"Renamed: {source} -> {destination}")

    logger.info(
        f"Summary: {len(plans)} files scanned, "
        f"{rewritten} contents updated, {renamed} files renamed, "
        f"{skipped} contents/files skipped."
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recursively rename prefixed files and symbols."
    )
    parser.add_argument("--path", type=Path, default=Path("."))
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry-run mode: check for pending changes without modifying files.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level (default: INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    root = args.path.resolve()
    if not root.is_dir():
        parser.error(f"Not a directory: {root}")

    if args.check:
        logger.info("Running in check mode (dry-run, no modifications)")

    exit_code = rename_tree(root, check=args.check)
    exit(exit_code)


if __name__ == "__main__":
    main()