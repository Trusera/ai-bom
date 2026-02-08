from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from ai_bom import __version__
from ai_bom.models import ScanResult
from ai_bom.reporters import get_reporter
from ai_bom.scanners import get_all_scanners
from ai_bom.utils.risk_scorer import score_component

app = typer.Typer(
    name="ai-bom",
    help="AI Bill of Materials — discover and inventory all AI/LLM components.",
    rich_markup_mode="markdown",
    no_args_is_help=True,
)

console = Console()


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
        raise typer.Exit(1)

    try:
        tmp = Path(tempfile.mkdtemp(prefix="ai-bom-"))
        console.print("[cyan]Cloning repository to temporary directory...[/cyan]")
        git.Repo.clone_from(url, str(tmp), depth=1)
        console.print(f"[green]Repository cloned to {tmp}[/green]")
        return tmp
    except Exception as e:
        console.print(f"[red]Failed to clone repository: {e}[/red]")
        raise typer.Exit(1)


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
            raise typer.Exit(1)
        scan_path = n8n_path
    elif n8n_url:
        # For live n8n scanning, we'll need to implement API access
        # For now, just indicate it's not supported yet
        console.print("[yellow]Live n8n scanning via API is not yet implemented.[/yellow]")
        console.print("[yellow]Use --n8n-local to scan your local n8n directory.[/yellow]")
        raise typer.Exit(1)
    else:
        # Resolve as local path
        scan_path = Path(target).resolve()
        if not scan_path.exists():
            console.print(f"[red]Target path does not exist: {scan_path}[/red]")
            raise typer.Exit(1)

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
        comp for comp in result.components
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


@app.command()
def scan(
    target: str = typer.Argument(".", help="Path to scan (file, directory, or git URL)"),
    format: str = typer.Option(
        "table", "--format", "-f",
        help="Output format: table, cyclonedx, json, html, markdown, sarif",
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path",
    ),
    deep: bool = typer.Option(
        False, "--deep", help="Enable deep scanning (reserved for future AST mode)",
    ),
    include_tests: bool = typer.Option(
        False, "--include-tests", help="Include test directories in scan",
    ),
    severity: Optional[str] = typer.Option(
        None, "--severity", "-s",
        help="Minimum severity: critical, high, medium, low",
    ),
    no_color: bool = typer.Option(
        False, "--no-color", help="Disable colored output",
    ),
    n8n_url: Optional[str] = typer.Option(
        None, "--n8n-url", help="n8n instance URL for live scanning",
    ),
    n8n_api_key: Optional[str] = typer.Option(None, "--n8n-api-key", help="n8n API key"),
    n8n_local: bool = typer.Option(False, "--n8n-local", help="Scan local ~/.n8n/ directory"),
) -> None:
    """Scan a directory or repository for AI/LLM components."""
    # Disable colors if requested
    if no_color:
        console.no_color = True

    # Print banner for table format
    if format == "table":
        _print_banner()

    # Show warning for unimplemented features
    if deep:
        console.print("[yellow]Deep scanning (AST mode) is not yet implemented.[/yellow]")

    # Resolve target path
    try:
        scan_path, is_temp = _resolve_target(target, n8n_local, n8n_url)
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Scan cancelled by user.[/yellow]")
        raise typer.Exit(0)

    try:
        # Initialize scan result
        result = ScanResult(target_path=str(scan_path))
        start_time = time.time()

        # Get all scanners
        scanners = get_all_scanners()

        if format == "table":
            console.print(f"[cyan]Scanning: {scan_path}[/cyan]")
            console.print()

        # Run scanners with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=(format != "table"),
        ) as progress:
            for scanner in scanners:
                # Check if scanner supports this path
                if not scanner.supports(scan_path):
                    continue

                task = progress.add_task(f"Running {scanner.name} scanner...", total=None)

                try:
                    # Run scanner
                    components = scanner.scan(scan_path)

                    # Apply risk scoring to each component
                    for comp in components:
                        comp.risk = score_component(comp)

                    # Add components to result
                    result.components.extend(components)

                except Exception as e:
                    console.print(f"[red]Error running {scanner.name} scanner: {e}[/red]")

                progress.update(task, completed=True)

        # Calculate scan duration
        end_time = time.time()
        result.summary.scan_duration_seconds = end_time - start_time

        # Build summary
        result.build_summary()

        # Filter by severity if specified
        if severity:
            _filter_by_severity(result, severity, quiet=(format != "table"))

        # Handle case where no components were found
        if not result.components:
            if format == "table":
                console.print()
                console.print("[green]No AI/LLM components detected in the scan.[/green]")
                console.print("[dim]This could mean your project doesn't use AI libraries,[/dim]")
                console.print("[dim]or they weren't detected by the current scanners.[/dim]")
            else:
                # Still generate a report for non-table formats
                pass
        else:
            if format == "table":
                console.print()
                console.print(f"[green]Found {len(result.components)} AI/LLM component(s)[/green]")
                console.print()

        # Get reporter and render output
        try:
            reporter = get_reporter(format)
            output_str = reporter.render(result)

            # Write to file if output specified
            if output:
                reporter.write(result, output)
                if format == "table":
                    console.print(f"[green]Report written to {output}[/green]")
            elif format == "table":
                # Print table format directly (already rendered by Rich)
                print(output_str)
            else:
                # For non-table formats, print raw output
                print(output_str)

        except Exception as e:
            console.print(f"[red]Error generating report: {e}[/red]")
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Scan cancelled by user.[/yellow]")
        raise typer.Exit(0)

    finally:
        # Cleanup temp directory if we cloned a repo
        if is_temp and scan_path.exists():
            try:
                shutil.rmtree(scan_path)
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Failed to clean up temp directory: {e}[/yellow]"
                )


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
        raise typer.Exit(1)

    console.print(f"[cyan]Running demo scan on {demo_path}...[/cyan]")
    console.print()

    # Call scan directly with explicit defaults
    scan(
        target=str(demo_path),
        format="table",
        output=None,
        deep=False,
        include_tests=False,
        severity=None,
        no_color=False,
        n8n_url=None,
        n8n_api_key=None,
        n8n_local=False,
    )


@app.command()
def version() -> None:
    """Show AI-BOM version."""
    console.print(f"ai-bom version {__version__}")


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
