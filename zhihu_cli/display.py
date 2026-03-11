"""Terminal display utilities for zhihu-cli.

Provides a consistent visual theme for all CLI output.
Uses Rich library for professional terminal rendering.
"""

from __future__ import annotations

import re
from html import unescape

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# ── Theme ──────────────────────────────────────────────────────────────────────

ZHIHU_THEME = Theme({
    "info": "dim cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "title": "bold cyan",
    "subtitle": "dim white",
    "accent": "bold blue",
    "muted": "dim",
    "stat.key": "cyan",
    "stat.value": "white",
    "badge": "bold magenta",
})

console = Console(theme=ZHIHU_THEME)

# ── Brand ──────────────────────────────────────────────────────────────────────

BRAND = "[bold blue]zhihu[/bold blue][bold white]-cli[/bold white]"
SEPARATOR = "[dim]─" * 50 + "[/dim]"


def print_banner():
    """Print a branded banner."""
    ver = _get_version()
    console.print(
        Panel(
            f"{BRAND}  [dim]v{ver}[/dim]\n"
            "[dim]知乎命令行工具 — Search, Read, Interact[/dim]",
            border_style="blue",
            padding=(0, 2),
        ),
        highlight=False,
    )


def _get_version() -> str:
    from . import __version__
    return __version__


# ── Message helpers ────────────────────────────────────────────────────────────

def print_success(msg: str):
    """Print a success message."""
    console.print(f"  [success]✓[/success] {msg}")


def print_error(msg: str):
    """Print an error message."""
    console.print(f"  [error]✗[/error] {msg}")


def print_warning(msg: str):
    """Print a warning message."""
    console.print(f"  [warning]![/warning] {msg}")


def print_info(msg: str):
    """Print an informational message."""
    console.print(f"  [info]›[/info] {msg}")


def print_hint(msg: str):
    """Print a hint/tip message."""
    console.print(f"  [muted]hint: {msg}[/muted]")


# ── Text utilities ─────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    return unescape(clean).strip()


def format_count(count: int | str) -> str:
    """Format large numbers for display (e.g. 12345 → 1.2万)."""
    if isinstance(count, str):
        try:
            count = int(count)
        except ValueError:
            return str(count)
    if count >= 100_000_000:
        return f"{count / 100_000_000:.1f}亿"
    if count >= 10_000:
        return f"{count / 10_000:.1f}万"
    return str(count)


def truncate(text: str, max_len: int = 50) -> str:
    """Truncate text with ellipsis."""
    if not text:
        return ""
    text = text.replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


# ── Table factories ────────────────────────────────────────────────────────────

def make_table(title: str, *, show_lines: bool = False, pad_edge: bool = False) -> Table:
    """Create a branded Table with standard styling."""
    return Table(
        title=f"[title]{title}[/title]",
        title_style="",
        border_style="blue",
        header_style="bold cyan",
        show_lines=show_lines,
        pad_edge=pad_edge,
        expand=False,
    )


def make_kv_table(title: str) -> Table:
    """Create a key-value profile table."""
    table = Table(
        title=f"[title]{title}[/title]",
        title_style="",
        border_style="blue",
        show_header=False,
        pad_edge=False,
        expand=False,
    )
    table.add_column("Key", style="stat.key", width=12, justify="right")
    table.add_column("Value", style="stat.value")
    return table


# ── Stats display ──────────────────────────────────────────────────────────────

def format_stats_line(pairs: dict[str, str | int]) -> str:
    """Create an inline stats display like '▸ 1.2万 Answers  ▸ 500 Followers'."""
    parts = []
    for label, value in pairs.items():
        parts.append(f"[dim]▸[/dim] [white]{format_count(value)}[/white] [dim]{label}[/dim]")
    return "  ".join(parts)
