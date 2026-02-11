"""Base scanner class with auto-registration for AI-BOM scanner framework."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ai_bom.config import EXCLUDED_DIRS
from ai_bom.models import AIComponent

logger = logging.getLogger(__name__)

# Global registry populated via __init_subclass__
_scanner_registry: list[type[BaseScanner]] = []

# Cached .ai-bomignore spec (module-level singleton)
_ignore_spec: Any = None
_ignore_spec_loaded: bool = False


def _load_ignore_spec(root: Path) -> Any:
    """Load .ai-bomignore from root directory using pathspec (gitignore syntax).

    Caches the spec in a module-level variable so it is only loaded once per
    process.  Returns None if pathspec is not installed or the file does not
    exist.

    Args:
        root: Root directory that may contain an ``.ai-bomignore`` file.

    Returns:
        A ``pathspec.PathSpec`` object, or None.
    """
    global _ignore_spec, _ignore_spec_loaded

    if _ignore_spec_loaded:
        return _ignore_spec

    _ignore_spec_loaded = True

    ignore_file = root / ".ai-bomignore"
    if not ignore_file.is_file():
        logger.debug(".ai-bomignore not found in %s", root)
        return None

    try:
        import pathspec
    except ImportError:
        logger.debug("pathspec library not installed; .ai-bomignore will be ignored")
        return None

    try:
        text = ignore_file.read_text(encoding="utf-8")
        _ignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", text.splitlines())
        logger.debug("Loaded .ai-bomignore with %d patterns", len(_ignore_spec.patterns))
    except Exception as exc:
        logger.warning("Failed to load .ai-bomignore: %s", exc)
        _ignore_spec = None

    return _ignore_spec


def _reset_ignore_spec() -> None:
    """Reset the cached ignore spec (for testing only)."""
    global _ignore_spec, _ignore_spec_loaded
    _ignore_spec = None
    _ignore_spec_loaded = False


class BaseScanner(ABC):
    """Abstract base class for all scanners with automatic registration.

    Concrete scanners should:
    1. Set class attributes `name` and `description`
    2. Implement `supports()` to filter paths
    3. Implement `scan()` to detect AI components

    Auto-registration happens when the scanner class is defined (imported).
    """

    name: str = ""
    description: str = ""

    #: Maximum file size in bytes to scan. Files larger than this are skipped.
    #: Default is 10 MB. Override per-instance or pass to ``get_all_scanners()``.
    max_file_size: int = 10_485_760  # 10 MB

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Automatically register concrete scanner subclasses.

        Only registers classes that have a non-empty `name` attribute,
        ensuring abstract intermediate classes are not registered.

        Args:
            **kwargs: Forwarded to parent __init_subclass__
        """
        super().__init_subclass__(**kwargs)
        # Only register concrete classes with a name set
        if cls.name:
            _scanner_registry.append(cls)

    @abstractmethod
    def supports(self, path: Path) -> bool:
        """Check if this scanner should run on the given path.

        Args:
            path: Directory or file path to check

        Returns:
            True if this scanner can analyze the path, False otherwise
        """
        ...

    @abstractmethod
    def scan(self, path: Path) -> list[AIComponent]:
        """Scan the given path and return discovered AI components.

        Args:
            path: Directory or file path to scan

        Returns:
            List of detected AI components with metadata and risk assessments
        """
        ...

    def safe_read_text(self, path: Path) -> str | None:
        """Safely read text file with encoding fallback chain.

        Attempts to read the file using:
        1. UTF-8 encoding
        2. Latin-1 encoding (fallback)
        3. Returns None if both fail or file contains binary content

        Args:
            path: Path to file to read

        Returns:
            File contents as string, or None if file cannot be read or is binary
        """
        # First check for binary content (null bytes in first 8KB)
        try:
            with open(path, "rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    logger.debug("Skipping binary file (null bytes detected): %s", path)
                    return None
        except (OSError, PermissionError) as e:
            logger.warning("Cannot read file %s: %s", path, e)
            return None

        # Try UTF-8 first
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.debug("UTF-8 decode failed for %s, trying latin-1", path)
        except (OSError, PermissionError) as e:
            logger.warning("Cannot read file %s: %s", path, e)
            return None

        # Fallback to latin-1
        try:
            return path.read_text(encoding="latin-1")
        except (OSError, PermissionError) as e:
            logger.warning("Cannot read file %s with latin-1: %s", path, e)
            return None
        except Exception as e:
            logger.warning("Unexpected error reading file %s: %s", path, e)
            return None

    def iter_files(
        self,
        root: Path,
        extensions: set[str] | None = None,
        filenames: set[str] | None = None,
        include_tests: bool = False,
    ) -> Iterator[Path]:
        """Walk directory tree yielding matching files with intelligent pruning.

        Automatically skips:
        - EXCLUDED_DIRS (node_modules, .git, __pycache__, etc.)
        - Test directories (test, tests, spec, specs) unless include_tests=True
        - Files larger than ``max_file_size`` (default 10 MB)
        - Binary files (containing null bytes in first 8KB)
        - .pyc compiled Python files
        - Symlinks that create cycles or point outside root
        - Files that cannot be read due to permissions

        Args:
            root: Root directory to walk
            extensions: Set of file extensions to match (e.g., {".py", ".js"})
                       Extensions should include the dot prefix
            filenames: Set of exact filenames to match (e.g., {"Dockerfile", "requirements.txt"})
            include_tests: Whether to include test directories in the walk

        Yields:
            Path objects for files matching the criteria

        Examples:
            # Find all Python files
            for file in scanner.iter_files(root, extensions={".py"}):
                ...

            # Find Dockerfiles and docker-compose.yml files
            for file in scanner.iter_files(
                root,
                filenames={"Dockerfile", "docker-compose.yml"}
            ):
                ...
        """
        # Convert root to absolute path for consistency
        root = root.resolve()

        # Load .ai-bomignore spec (cached after first call)
        ignore_spec = _load_ignore_spec(root if root.is_dir() else root.parent)

        # Track real paths to detect symlink cycles
        seen_real_paths: set[Path] = set()
        root_real = Path(os.path.realpath(root))

        # Handle single file: yield it if it matches criteria, then return
        if root.is_file():
            # Check if this is a symlink pointing outside root directory
            try:
                real_path = Path(os.path.realpath(root))
                if not str(real_path).startswith(str(root_real.parent)):
                    logger.warning("Skipping symlink outside root: %s -> %s", root, real_path)
                    return
            except (OSError, ValueError) as e:
                logger.warning("Cannot resolve symlink %s: %s", root, e)
                return

            # Skip .pyc files
            if root.suffix == ".pyc":
                return

            # Skip files larger than max_file_size to avoid binary/generated files
            try:
                file_size = os.path.getsize(root)
                if file_size > self.max_file_size:
                    logger.warning("Skipping large file (>%dMB): %s (%d bytes)", self.max_file_size // (1024 * 1024), root, file_size)
                    return
            except OSError as e:
                logger.warning("Cannot get size of %s: %s", root, e)
                return

            # Check for binary content (null bytes in first 8KB)
            try:
                with open(root, "rb") as f:
                    chunk = f.read(8192)
                    if b"\x00" in chunk:
                        logger.debug("Skipping binary file: %s", root)
                        return
            except PermissionError:
                logger.warning("Permission denied reading %s", root)
                return
            except OSError as e:
                logger.warning("Cannot read file %s: %s", root, e)
                return

            matches = False
            if extensions is not None and root.suffix.lower() in extensions:
                matches = True
            if filenames is not None and (root.name in filenames or root.name.lower() in filenames):
                matches = True
            if extensions is None and filenames is None:
                matches = True
            if matches:
                # Check .ai-bomignore
                if ignore_spec is not None:
                    rel = str(root.relative_to(root.parent))
                    if ignore_spec.match_file(rel):
                        logger.debug("Skipping ignored file: %s", root)
                        return
                yield root
            return

        # Test directory names to exclude
        test_dirs = {"test", "tests", "spec", "specs"} if not include_tests else set()

        # Walk the directory tree
        try:
            for dirpath, dirnames, filenames_list in os.walk(root, topdown=True, followlinks=True):
                # Resolve current directory to detect symlink cycles
                try:
                    current_real = Path(os.path.realpath(dirpath))

                    # Skip if this creates a cycle
                    if current_real in seen_real_paths:
                        logger.warning("Skipping symlink cycle at: %s", dirpath)
                        dirnames[:] = []  # Don't descend into this directory
                        continue

                    # Skip if symlink points outside root
                    if not str(current_real).startswith(str(root_real)):
                        logger.warning(
                            "Skipping symlink outside root: %s -> %s",
                            dirpath,
                            current_real,
                        )
                        dirnames[:] = []
                        continue

                    seen_real_paths.add(current_real)
                except (OSError, ValueError) as e:
                    logger.warning("Cannot resolve directory %s: %s", dirpath, e)
                    dirnames[:] = []
                    continue

                # Prune excluded directories in-place (modifies dirnames)
                dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and d not in test_dirs]

                # Check each file in current directory
                for filename in filenames_list:
                    # Skip .pyc files
                    if filename.endswith(".pyc"):
                        continue

                    file_path = Path(dirpath) / filename

                    # Check for symlink safety
                    try:
                        file_real = Path(os.path.realpath(file_path))

                        # Skip if symlink points outside root
                        if not str(file_real).startswith(str(root_real)):
                            logger.warning(
                                "Skipping symlink outside root: %s -> %s",
                                file_path,
                                file_real,
                            )
                            continue
                    except (OSError, ValueError) as e:
                        logger.warning("Cannot resolve file %s: %s", file_path, e)
                        continue

                    # Skip files larger than max_file_size to avoid binary/generated files
                    try:
                        file_size = os.path.getsize(file_path)
                        if file_size > self.max_file_size:
                            logger.warning(
                                "Skipping large file (>%dMB): %s (%d bytes)",
                                self.max_file_size // (1024 * 1024),
                                file_path,
                                file_size,
                            )
                            continue
                    except PermissionError:
                        logger.warning("Permission denied accessing %s", file_path)
                        continue
                    except OSError as e:
                        logger.warning("Cannot get size of %s: %s", file_path, e)
                        continue

                    # Check for binary content (null bytes in first 8KB)
                    try:
                        with open(file_path, "rb") as f:
                            chunk = f.read(8192)
                            if b"\x00" in chunk:
                                logger.debug("Skipping binary file: %s", file_path)
                                continue
                    except PermissionError:
                        logger.warning("Permission denied reading %s", file_path)
                        continue
                    except OSError as e:
                        logger.warning("Cannot read file %s: %s", file_path, e)
                        continue

                    # Match by extension or exact filename
                    matches = False

                    if extensions is not None:
                        file_ext = file_path.suffix.lower()
                        if file_ext in extensions:
                            matches = True

                    if filenames is not None and (
                        filename in filenames or filename.lower() in filenames
                    ):
                        matches = True

                    # If no filters specified, match all files
                    if extensions is None and filenames is None:
                        matches = True

                    if matches:
                        # Check .ai-bomignore
                        if ignore_spec is not None:
                            try:
                                rel = str(file_path.relative_to(root))
                            except ValueError:
                                rel = str(file_path)
                            if ignore_spec.match_file(rel):
                                logger.debug("Skipping ignored file: %s", file_path)
                                continue
                        yield file_path
        except PermissionError as e:
            logger.warning("Permission denied walking directory %s: %s", root, e)


def get_all_scanners(*, max_file_size: int | None = None) -> list[BaseScanner]:
    """Instantiate and return all registered scanners.

    Args:
        max_file_size: Optional override for the maximum file size (in bytes)
            that scanners will process.  Files larger than this are skipped.
            When *None* the per-scanner default (10 MB) is used.

    Returns:
        List of scanner instances ready to use for scanning

    Note:
        Scanner registration happens automatically when scanner
        modules are imported via __init_subclass__
    """
    scanners = [scanner_cls() for scanner_cls in _scanner_registry]
    if max_file_size is not None:
        for s in scanners:
            s.max_file_size = max_file_size
    return scanners
