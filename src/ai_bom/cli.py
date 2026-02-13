from __future__ import annotations

import contextlib
import json
import logging
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.text import Text

from ai_bom import __version__
from ai_bom.models import ScanResult
from ai_bom.reporters import get_reporter
from ai_bom.scanners import get_all_scanners
from ai_bom.scanners.ast_scanner import ASTScanner
from ai_bom.utils.risk_scorer import score_component

# Exit codes
EXIT_ERROR = 2  # Operational errors (bad path, network failure, parse error, etc.)

app = typer.Typer(
    name="ai-bom",
    help="AI Bill of Materials — discover and inventory all AI/LLM components.",
    rich_markup_mode="markdown",
    no_args_is_help=True,
)

console = Console()
logger = logging.getLogger("ai_bom")


def _send_telemetry(result: ScanResult, scan_type: str) -> None:
    """Send anonymous telemetry data if opted in via AI_BOM_TELEMETRY=true.

    Non-blocking: runs in a background thread. Fails silently on any error.
    No PII is collected — only aggregate scan statistics.
    """
    if os.environ.get("AI_BOM_TELEMETRY", "").lower() != "true":
        return

    def _post() -> None:
        try:
            import urllib.request

            payload = json.dumps(
                {
                    "scan_type": scan_type,
                    "component_counts": dict(result.summary.by_type),
                    "severity_counts": dict(result.summary.by_severity),
                    "scanner_version": result.ai_bom_version,
                    "timestamp": result.scan_timestamp,
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                "https://api.trusera.dev/api/v1/telemetry",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)  # noqa: S310
        except Exception:
            pass  # Never crash the CLI due to telemetry

    threading.Thread(target=_post, daemon=True).start()


def _setup_logging(verbose: bool = False, debug: bool = False) -> None:
    """Configure logging based on verbosity flags."""
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
            stream=sys.stderr,
        )
    elif verbose:
        logging.basicConfig(
            level=logging.INFO,
            format="%(name)s: %(message)s",
            stream=sys.stderr,
        )
    else:
        logging.basicConfig(level=logging.WARNING, stream=sys.stderr)


def _print_banner() -> None:
    """Print the AI-BOM banner."""
    banner = Text()
    banner.append("  AI-BOM  ", style="bold white on blue")
    banner.append("  ", style="")
    banner.append("AI Bill of Materials Discovery Scanner", style="bold cyan")
    banner.append("\n  by ", style="dim")
    banner.append("Trusera", style="bold green")
    banner.append(" | ", style="dim")
    banner.append("trusera.dev", style="dim underline")
    console.print(Panel(banner, box=box.DOUBLE, border_style="cyan", padding=(0, 1)))
    console.print()


def _clone_repo(url: str) -> Path:
    """Clone a git repo to a temp directory.

    Args:
        url: Git repository URL (http, https, or git@)

    Returns:
        Path to the cloned repository

    Raises:
        typer.Exit: If cloning fails
    """
    try:
        import git
    except ImportError:
        console.print(
            "[red]GitPython is not installed. Install it with: pip install gitpython[/red]"
        )
        raise typer.Exit(EXIT_ERROR) from None

    try:
        tmp = Path(tempfile.mkdtemp(prefix="ai-bom-"))
        console.print("[cyan]Cloning repository to temporary directory...[/cyan]")
        git.Repo.clone_from(url, str(tmp), depth=1)
        console.print(f"[green]Repository cloned to {tmp}[/green]")
        return tmp
    except Exception as e:
        console.print(f"[red]Failed to clone repository: {e}[/red]")
        raise typer.Exit(EXIT_ERROR) from None


def _resolve_target(
    target: str,
    n8n_local: bool,
    n8n_url: Optional[str] = None,
) -> tuple[Path, bool]:
    """Resolve the target path to scan.

    Args:
        target: Target path, URL, or directory
        n8n_local: Whether to scan local ~/.n8n/ directory
        n8n_url: n8n instance URL for live scanning

    Returns:
        Tuple of (resolved_path, is_temp_dir)
    """
    is_temp = False

    # Check if target is a Git URL
    if target.startswith(("http://", "https://", "git@")):
        scan_path = _clone_repo(target)
        is_temp = True
    elif n8n_local:
        # Scan local n8n directory
        n8n_path = Path.home() / ".n8n"
        if not n8n_path.exists():
            console.print(f"[red]n8n directory not found at {n8n_path}[/red]")
            raise typer.Exit(EXIT_ERROR)
        scan_path = n8n_path
    elif n8n_url:
        # Live n8n scanning via API — handled separately in scan()
        # Return a dummy path; the caller uses the n8n_url flag to branch.
        scan_path = Path(".")  # not used for actual file scanning
    else:
        # Resolve as local path
        scan_path = Path(target).resolve()
        if not scan_path.exists():
            console.print(f"[red]Target path does not exist: {scan_path}[/red]")
            raise typer.Exit(EXIT_ERROR)

    return scan_path, is_temp


def _filter_by_severity(
    result: ScanResult,
    severity_str: str,
    quiet: bool = False,
) -> None:
    """Filter scan results by minimum severity level.

    Args:
        result: Scan result to filter (modified in place)
        severity_str: Minimum severity string (critical, high, medium, low)
    """
    severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    min_level = severity_order.get(severity_str.lower())
    if min_level is None:
        console.print(f"[yellow]Invalid severity level: {severity_str}. Using all levels.[/yellow]")
        return

    # Filter components by severity
    original_count = len(result.components)
    result.components = [
        comp
        for comp in result.components
        if severity_order.get(comp.risk.severity.value, 0) >= min_level
    ]

    filtered_count = original_count - len(result.components)
    if filtered_count > 0 and not quiet:
        console.print(
            f"[dim]Filtered out {filtered_count} components"
            f" below {severity_str.upper()} severity[/dim]"
        )

    # Rebuild summary after filtering
    result.build_summary()


def _save_to_dashboard(result: ScanResult, scan_duration: float, quiet: bool = False) -> None:
    """Save scan result to the dashboard SQLite database.

    Uses lazy imports so the dashboard deps are not required for normal CLI usage.
    """
    from uuid import uuid4

    try:
        from ai_bom.dashboard.db import init_db, save_scan
    except ImportError:
        if not quiet:
            console.print(
                "[yellow]Dashboard dependencies not installed. "
                "Install with: pip install ai-bom[dashboard][/yellow]"
            )
        return

    try:
        init_db()
        scan_id = str(uuid4())
        summary_dict = result.summary.model_dump()
        components_list = [c.model_dump(mode="json") for c in result.components]
        save_scan(
            scan_id=scan_id,
            timestamp=result.scan_timestamp,
            target_path=result.target_path,
            summary_json=json.dumps(summary_dict),
            components_json=json.dumps(components_list),
            scan_duration=scan_duration,
            ai_bom_version=result.ai_bom_version,
        )
        if not quiet:
            console.print(f"[green]Scan saved to dashboard (id: {scan_id[:8]}...)[/green]")
    except Exception as e:
        if not quiet:
            console.print(f"[yellow]Failed to save to dashboard: {e}[/yellow]")


@app.command()
def scan(
    target: str = typer.Argument(".", help="Path to scan (file, directory, or git URL)"),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table, cyclonedx, json, html, markdown, sarif, spdx3, csv, junit",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path",
    ),
    deep: bool = typer.Option(
        False,
        "--deep",
        help="Enable deep AST-based Python analysis",
    ),
    severity: Optional[str] = typer.Option(
        None,
        "--severity",
        "-s",
        help="Minimum severity: critical, high, medium, low",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable colored output",
    ),
    n8n_url: Optional[str] = typer.Option(
        None,
        "--n8n-url",
        help="n8n instance URL for live scanning",
    ),
    n8n_api_key: Optional[str] = typer.Option(None, "--n8n-api-key", help="n8n API key"),
    n8n_local: bool = typer.Option(False, "--n8n-local", help="Scan local ~/.n8n/ directory"),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress banner and progress (for CI)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show scanner details, file counts, and timing",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug logging with full stack traces",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help="Path to .ai-bom.yml config file",
    ),
    save_dashboard: bool = typer.Option(
        False,
        "--save-dashboard",
        help="Save scan results to the dashboard database",
    ),
    fail_on: Optional[str] = typer.Option(
        None,
        "--fail-on",
        help="Exit code 1 if severity threshold met: critical, high, medium, low",
    ),
    policy: Optional[str] = typer.Option(
        None,
        "--policy",
        help="Path to YAML policy file for CI/CD enforcement",
    ),
    workers: int = typer.Option(
        0,
        "--workers",
        help="Number of parallel scanner workers (0 = sequential)",
    ),
    cache: bool = typer.Option(
        False,
        "--cache/--no-cache",
        help="Enable incremental scanning cache",
    ),
    max_file_size: int = typer.Option(
        10,
        "--max-file-size",
        help="Max file size in MB (default: 10). Increase for large models.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON (shorthand for --format json)",
    ),
) -> None:
    """Scan a directory or repository for AI/LLM components."""
    # --json / -j overrides --format
    if json_output:
        format = "json"

    # Setup logging
    _setup_logging(verbose=verbose, debug=debug)

    # Load config file if specified or auto-discover
    if config or verbose:
        from ai_bom.config_file import load_config

        cfg = load_config(Path(config) if config else None)
        if cfg and verbose:
            console.print(f"[dim]Loaded config: {cfg}[/dim]")

    # Disable colors if requested or if NO_COLOR environment variable is set
    if no_color or os.environ.get("NO_COLOR") is not None:
        console.no_color = True

    # Print banner for table format (unless quiet)
    if format == "table" and not quiet:
        _print_banner()

    # Enable AST scanner when --deep is used
    if deep and not quiet:
        console.print("[cyan]Deep scanning (AST mode) enabled.[/cyan]")

    # Resolve target path
    try:
        scan_path, is_temp = _resolve_target(target, n8n_local, n8n_url)
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Scan cancelled by user.[/yellow]")
        raise typer.Exit(0) from None

    try:
        # Initialize scan result
        result = ScanResult(target_path=n8n_url or str(scan_path))
        start_time = time.time()

        if n8n_url:
            # --- Live n8n API scanning ---
            if not n8n_api_key:
                console.print("[red]--n8n-api-key is required when using --n8n-url[/red]")
                raise typer.Exit(EXIT_ERROR)

            from ai_bom.integrations.n8n_api import (
                N8nAPIClient,
                N8nAPIError,
                N8nAuthError,
                N8nConnectionError,
            )
            from ai_bom.scanners.n8n_scanner import N8nScanner

            if format == "table" and not quiet:
                console.print(f"[cyan]Scanning n8n instance: {n8n_url}[/cyan]")
                console.print()

            client = N8nAPIClient(n8n_url, n8n_api_key)
            n8n_scanner = N8nScanner()

            try:
                components = n8n_scanner.scan_from_api(client)
            except N8nAuthError:
                console.print("[red]Authentication failed. Check your n8n API key.[/red]")
                raise typer.Exit(EXIT_ERROR) from None
            except N8nConnectionError as exc:
                console.print(f"[red]Cannot connect to n8n: {exc}[/red]")
                raise typer.Exit(EXIT_ERROR) from None
            except N8nAPIError as exc:
                console.print(f"[red]n8n API error: {exc}[/red]")
                raise typer.Exit(EXIT_ERROR) from None

            for comp in components:
                comp.risk = score_component(comp)
            result.components.extend(components)
        else:
            # --- File-system scanning ---
            # Get all scanners (convert MB CLI option to bytes)
            max_file_size_bytes = max_file_size * 1024 * 1024
            scanners = get_all_scanners(max_file_size=max_file_size_bytes)

            # Enable AST scanner if --deep flag is set
            if deep:
                for s in scanners:
                    if isinstance(s, ASTScanner):
                        s.enabled = True

            if format == "table" and not quiet:
                console.print(f"[cyan]Scanning: {scan_path}[/cyan]")
                if verbose:
                    active = ", ".join(s.name for s in scanners if s.supports(scan_path))
                    console.print(f"[dim]Scanners: {active}[/dim]")
                console.print()

            # Optionally initialise the incremental cache
            scan_cache = None
            if cache:
                from ai_bom.cache import ScanCache

                scan_cache = ScanCache()

            if workers > 0:
                # --- Parallel scanning ---
                from ai_bom.scanners import run_scanners_parallel

                if format == "table" and not quiet:
                    console.print(f"[dim]Parallel scanning with {workers} workers[/dim]")

                components = run_scanners_parallel(scanners, scan_path, workers=workers)
                for comp in components:
                    comp.risk = score_component(comp)
                result.components.extend(components)
            else:
                # --- Sequential scanning with progress indicator ---
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(bar_width=20),
                    TaskProgressColumn(),
                    console=console,
                    disable=(format != "table" or quiet),
                ) as progress:
                    for scanner in scanners:
                        # Check if scanner supports this path
                        if not scanner.supports(scan_path):
                            continue

                        scanner_start = time.time()
                        task = progress.add_task(f"Running {scanner.name} scanner...", total=None)

                        try:
                            # Run scanner
                            components = scanner.scan(scan_path)

                            # Apply risk scoring to each component
                            for comp in components:
                                comp.risk = score_component(comp)

                            # Add components to result
                            result.components.extend(components)

                            scanner_elapsed = time.time() - scanner_start
                            if verbose and not quiet:
                                console.print(
                                    f"[dim]  {scanner.name}: "
                                    f"{len(components)} component(s) "
                                    f"in {scanner_elapsed:.2f}s[/dim]"
                                )

                        except Exception as e:
                            if debug:
                                logger.exception("Error in %s scanner", scanner.name)
                            console.print(f"[red]Error running {scanner.name} scanner: {e}[/red]")

                        progress.update(task, completed=True)

            # Persist the incremental cache if enabled
            if scan_cache is not None:
                scan_cache.save()

        # Calculate scan duration
        end_time = time.time()
        result.summary.scan_duration_seconds = end_time - start_time

        # Build summary
        result.build_summary()

        # Filter by severity if specified
        if severity:
            _filter_by_severity(result, severity, quiet=(format != "table" or quiet))

        # Handle case where no components were found
        if not result.components:
            if format == "table" and not quiet:
                console.print()
                console.print("[green]No AI/LLM components detected in the scan.[/green]")
                console.print("[dim]This could mean your project doesn't use AI libraries,[/dim]")
                console.print("[dim]or they weren't detected by the current scanners.[/dim]")
            else:
                # Still generate a report for non-table formats
                pass
        else:
            if format == "table" and not quiet:
                console.print()
                console.print(f"[green]Found {len(result.components)} AI/LLM component(s)[/green]")
                if verbose:
                    console.print(
                        f"[dim]Scan completed in {result.summary.scan_duration_seconds:.2f}s[/dim]"
                    )
                console.print()

        # Get reporter and render output
        try:
            reporter = get_reporter(format)
            output_str = reporter.render(result)

            # Write to file if output specified
            if output:
                reporter.write(result, output)
                if format == "table" and not quiet:
                    console.print(f"[green]Report written to {output}[/green]")
            elif format == "table":
                # Print table format directly (already rendered by Rich)
                print(output_str)
            else:
                # For non-table formats, print raw output
                print(output_str)

        except Exception as e:
            if debug:
                logger.exception("Error generating report")
            console.print(f"[red]Error generating report: {e}[/red]")
            raise typer.Exit(EXIT_ERROR) from None

        # Print friendly call-to-action if scan was successful and not in quiet mode
        if format == "table" and not quiet:
            console.print()
            star_msg = (
                "✨ Found ai-bom useful? "
                "Give us a star: https://github.com/Trusera/ai-bom ⭐"
            )
            console.print(f"[cyan]{star_msg}[/cyan]")

        # Save to dashboard database if requested
        if save_dashboard:
            _save_to_dashboard(result, end_time - start_time, quiet=quiet)

        # Send anonymous telemetry (opt-in only, non-blocking)
        if target.startswith(("http://", "https://", "git@")):
            _scan_type = "repo"
        elif scan_path.is_file():
            _scan_type = "file"
        else:
            _scan_type = "dir"
        _send_telemetry(result, _scan_type)

        # --- Policy enforcement ---
        exit_code = 0

        # --fail-on severity check
        if fail_on and result.components:
            severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            threshold = severity_order.get(fail_on.lower())
            if threshold is None:
                console.print(
                    f"[yellow]Invalid --fail-on value: {fail_on}. "
                    f"Use: critical, high, medium, low[/yellow]"
                )
            else:
                for comp in result.components:
                    comp_level = severity_order.get(comp.risk.severity.value, 0)
                    if comp_level >= threshold:
                        if quiet:
                            print(
                                f"FAIL: {comp.name} has severity "
                                f"{comp.risk.severity.value.upper()} "
                                f"(threshold: {fail_on.upper()})",
                                file=sys.stderr,
                            )
                        else:
                            console.print(
                                f"[red]POLICY FAIL: Found component '{comp.name}' "
                                f"with severity {comp.risk.severity.value.upper()} "
                                f"(threshold: {fail_on.upper()})[/red]"
                            )
                        exit_code = 1
                        break

        # --policy file evaluation
        if policy:
            from ai_bom.policy import evaluate_policy, load_policy

            try:
                pol = load_policy(policy)
                passed, violations = evaluate_policy(result, pol)
                if not passed:
                    exit_code = 1
                    if quiet:
                        print(
                            f"FAIL: {len(violations)} policy violation(s)",
                            file=sys.stderr,
                        )
                    else:
                        console.print()
                        console.print(f"[red]POLICY VIOLATIONS ({len(violations)}):[/red]")
                        for v in violations:
                            console.print(f"  [red]- {v}[/red]")
                elif not quiet and format == "table":
                    console.print("[green]Policy check passed.[/green]")
            except FileNotFoundError as e:
                console.print(f"[red]{e}[/red]")
                exit_code = 1
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                exit_code = 1

        if exit_code != 0:
            raise typer.Exit(exit_code)

    except KeyboardInterrupt:
        console.print("\n[yellow]Scan cancelled by user.[/yellow]")
        raise typer.Exit(0) from None

    finally:
        # Cleanup temp directory if we cloned a repo
        if is_temp and scan_path.exists():
            try:
                shutil.rmtree(scan_path)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to clean up temp directory: {e}[/yellow]")


@app.command(name="scan-cloud")
def scan_cloud(
    provider: str = typer.Argument(help="Cloud provider: aws, gcp, azure"),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table, cyclonedx, json, html, markdown, sarif, spdx3, csv, junit",
    ),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress banner and progress"),
) -> None:
    """Scan cloud provider for managed AI/ML services."""
    provider = provider.lower()
    provider_map = {
        "aws": "aws-live",
        "gcp": "gcp-live",
        "azure": "azure-live",
    }
    scanner_name = provider_map.get(provider)
    if scanner_name is None:
        console.print(
            f"[red]Unknown cloud provider: {provider}. Choose from: {', '.join(provider_map)}[/red]"
        )
        raise typer.Exit(EXIT_ERROR)

    if format == "table" and not quiet:
        _print_banner()

    # Find and enable the requested live scanner
    scanners = get_all_scanners()
    live_scanner = None
    for s in scanners:
        if s.name == scanner_name:
            live_scanner = s
            break

    if live_scanner is None:
        console.print(
            f"[red]{provider.upper()} live scanner is not available. "
            f"Install the SDK: pip install ai-bom[{provider}][/red]"
        )
        raise typer.Exit(EXIT_ERROR)

    # Enable and run
    live_scanner.enabled = True  # type: ignore[attr-defined]

    if format == "table" and not quiet:
        console.print(f"[cyan]Scanning {provider.upper()} account for AI/ML services...[/cyan]")
        console.print()

    result = ScanResult(target_path=f"cloud://{provider}")
    start_time = time.time()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=(format != "table" or quiet),
        ) as progress:
            task = progress.add_task(
                f"Running {live_scanner.name} scanner...",
                total=None,
            )
            components = live_scanner.scan(Path("."))
            for comp in components:
                comp.risk = score_component(comp)
            result.components.extend(components)
            progress.update(task, completed=True)
    except Exception as exc:
        console.print(f"[red]Cloud scan error: {exc}[/red]")
        raise typer.Exit(EXIT_ERROR) from None
    finally:
        live_scanner.enabled = False  # type: ignore[attr-defined]

    result.summary.scan_duration_seconds = time.time() - start_time
    result.build_summary()

    if not result.components:
        if format == "table" and not quiet:
            console.print()
            console.print(f"[green]No AI/ML services found in {provider.upper()} account.[/green]")
    else:
        if format == "table" and not quiet:
            console.print()
            console.print(f"[green]Found {len(result.components)} AI/ML service(s)[/green]")
            console.print()

    try:
        reporter = get_reporter(format)
        output_str = reporter.render(result)
        if output:
            reporter.write(result, output)
            if format == "table" and not quiet:
                console.print(f"[green]Report written to {output}[/green]")
        elif format == "table":
            print(output_str)
        else:
            print(output_str)
    except Exception as exc:
        console.print(f"[red]Error generating report: {exc}[/red]")
        raise typer.Exit(EXIT_ERROR) from None

    # Print friendly call-to-action if scan was successful and not in quiet mode
    if format == "table" and not quiet:
        console.print()
        star_msg = (
            "✨ Found ai-bom useful? "
            "Give us a star: https://github.com/Trusera/ai-bom ⭐"
        )
        console.print(f"[cyan]{star_msg}[/cyan]")


@app.command()
def demo() -> None:
    """Run a demo scan on the bundled example project."""
    # Try package-internal location first (works after pip install)
    demo_path = Path(__file__).parent / "demo_data"
    if not demo_path.exists():
        # Fallback to development layout (git clone / editable install)
        demo_path = Path(__file__).parent.parent.parent / "examples" / "demo-project"

    if not demo_path.exists():
        console.print("[red]Demo project not found.[/red]")
        raise typer.Exit(EXIT_ERROR)

    console.print(f"[cyan]Running demo scan on {demo_path}...[/cyan]")
    console.print()

    # Call scan directly with explicit defaults
    scan(
        target=str(demo_path),
        format="table",
        output=None,
        deep=False,
        severity=None,
        no_color=False,
        n8n_url=None,
        n8n_api_key=None,
        n8n_local=False,
        quiet=False,
        verbose=False,
        debug=False,
        config=None,
        save_dashboard=False,
        fail_on=None,
        policy=None,
        workers=0,
        cache=False,
        max_file_size=10,
    )


@app.command(name="list-scanners")
def list_scanners() -> None:
    """List all registered scanners and their status."""
    _print_banner()

    scanners = get_all_scanners()
    console.print(f"[bold]Registered scanners ({len(scanners)}):[/bold]")
    console.print()

    for scanner in scanners:
        enabled = getattr(scanner, "enabled", True)
        status = "[green]enabled[/green]" if enabled else "[yellow]disabled[/yellow]"
        console.print(f"  [bold]{scanner.name}[/bold] - {scanner.description} ({status})")

    console.print()
    console.print("[dim]Use --deep to enable AST scanner for Python analysis.[/dim]")


@app.command()
def diff(
    scan1: str = typer.Argument(help="Path to first scan JSON file"),
    scan2: str = typer.Argument(help="Path to second scan JSON file"),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table, json, markdown",
    ),
) -> None:
    """Compare two scan results and show differences."""
    from ai_bom.reporters.diff_reporter import (
        compare_scans,
        format_diff_as_json,
        format_diff_as_markdown,
        format_diff_as_table,
        load_scan_from_file,
    )

    try:
        # Load both scan files
        console.print(f"[cyan]Loading scan 1: {scan1}[/cyan]")
        result1 = load_scan_from_file(scan1)

        console.print(f"[cyan]Loading scan 2: {scan2}[/cyan]")
        result2 = load_scan_from_file(scan2)

        # Compare scans
        console.print("[cyan]Comparing scans...[/cyan]")
        diff_result = compare_scans(result1, result2)

        # Format output
        if format == "json":
            output = format_diff_as_json(diff_result)
        elif format == "markdown":
            output = format_diff_as_markdown(diff_result)
        else:  # table
            output = format_diff_as_table(diff_result)

        console.print()
        print(output)

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(EXIT_ERROR) from None
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(EXIT_ERROR) from None
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(EXIT_ERROR) from None


@app.command()
def dashboard(
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to bind"),
) -> None:
    """Launch the AI-BOM web dashboard."""
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]Dashboard dependencies not installed. "
            "Install with: pip install ai-bom[dashboard][/red]"
        )
        raise typer.Exit(EXIT_ERROR) from None

    from ai_bom.dashboard import create_app

    _print_banner()
    console.print(f"[cyan]Starting dashboard at http://{host}:{port}[/cyan]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    dash_app = create_app()
    uvicorn.run(dash_app, host=host, port=port, log_level="info")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind"),  # noqa: S104
    port: int = typer.Option(8080, help="Port to bind"),
) -> None:
    """Start the AI-BOM REST API server."""
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]Server dependencies not installed. Install with: pip install ai-bom[server][/red]"
        )
        raise typer.Exit(EXIT_ERROR) from None

    from ai_bom.server import create_server_app

    _print_banner()
    console.print(f"[cyan]Starting AI-BOM API server at http://{host}:{port}[/cyan]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    server_app = create_server_app()
    uvicorn.run(server_app, host=host, port=port, log_level="info")


@app.command()
def watch(
    target: str = typer.Argument(".", help="Directory to watch"),
    format: str = typer.Option("table", "--format", "-f"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Watch a directory for changes and re-scan automatically."""
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        console.print("[red]watchdog is not installed. Install it with: pip install watchdog[/red]")
        raise typer.Exit(EXIT_ERROR) from None

    scan_path = Path(target).resolve()
    if not scan_path.exists():
        console.print(f"[red]Target path does not exist: {scan_path}[/red]")
        raise typer.Exit(EXIT_ERROR)

    _print_banner()
    console.print(f"[cyan]Watching {scan_path} for changes... (Ctrl+C to stop)[/cyan]")
    console.print()

    class _Handler(FileSystemEventHandler):
        def on_modified(self, event: Any) -> None:
            if event.is_directory:
                return
            console.print(f"[dim]Change detected: {event.src_path}[/dim]")
            with contextlib.suppress(SystemExit):
                scan(
                    target=str(scan_path),
                    format=format,
                    output=None,
                    deep=False,
                    severity=None,
                    no_color=False,
                    n8n_url=None,
                    n8n_api_key=None,
                    n8n_local=False,
                    quiet=True,
                    verbose=verbose,
                    debug=False,
                    config=None,
                    save_dashboard=False,
                    fail_on=None,
                    policy=None,
                    workers=0,
                    cache=False,
                )

    observer = Observer()
    observer.schedule(_Handler(), str(scan_path), recursive=True)
    observer.start()
    try:
        import time as _time

        while True:
            _time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch stopped by user.[/yellow]")
        observer.stop()
    observer.join()


@app.command()
def version() -> None:
    """Show AI-BOM version."""
    console.print(f"ai-bom version {__version__}")


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
