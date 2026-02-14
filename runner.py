#!/opt/homebrew/bin/python3
import tomllib
import argparse
import subprocess
import os
import time
import signal
from rich.console import Console
from rich.theme import Theme as RichTheme
from textual.app import App, ComposeResult
from textual.theme import Theme
from textual.widgets import Static, Footer
from textual.events import Click
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.binding import Binding

console = Console(theme=RichTheme({
    "repr.str": "cyan",
    "repr.number": "green",
    "repr.bool": "green",
    "repr.null": "red",
}))

HARLEQUIN_THEME = Theme(
    name="harlequin",
    primary="#FEFFAC",
    secondary="#45FFCA",
    warning="#FEFFAC",
    error="#FFB6D9",
    success="#45FFCA",
    accent="#D67BFF",
    foreground="#DDDDDD",
    background="#0C0C0C",
    surface="#0C0C0C",
    panel="#555555",
    dark=True,
)

NORD_THEME = Theme(
    name="nord",
    primary="#88c0d0",
    secondary="#81a1c1",
    warning="#ebcb8b",
    error="#bf616a",
    success="#a3be8c",
    accent="#b48ead",
    foreground="#d8dee9",
    background="#2e3440",
    surface="#2e3440",
    panel="#3b4252",
    dark=True,
)

NIGHTFOX_THEME = Theme(
    name="nightfox",
    primary="#7aa2f7",
    secondary="#bb9af7",
    warning="#e0af68",
    error="#f7768e",
    success="#9ece6a",
    accent="#7dcfff",
    foreground="#c0caf5",
    background="#1a1c25",
    surface="#1a1c25",
    panel="#24283b",
    dark=True,
)


class TestRunnerApp(App):
    title = ""
    subtitle = ""
    header = None
    themes = [NIGHTFOX_THEME]
    
    CSS = """
    $border-color-nofocus: $panel;
    $border-title-color-nofocus: $panel;
    $border-color-focus: $primary;
    $border-title-color-focus: $primary;

    Screen > .--bar {
        height: 0;
    }

    Screen {
        background: $background;
    }

    #main-container {
        height: 1fr;
    }

    #sidebar {
        width: 30;
        border: round $border-color-focus;
        border-title-color: $border-title-color-focus;
    }

    #sidebar:focus-within {
        border: round $border-color-focus;
        border-title-color: $border-title-color-focus;
    }

    #test-list {
        height: 1fr;
        overflow-y: auto;
    }

    #test-list > .test-item {
        padding: 0 1;
        height: 1;
    }

    #test-list > .test-item:hover {
        background: #414868;
    }

    #test-list > .test-item--focus {
        text-style: bold;
        color: #7aa2f7;
    }

    #main-panel {
        width: 1fr;
        border: round $border-color-nofocus;
        border-title-color: $border-title-color-nofocus;
    }

    #main-panel:focus-within {
        border: round $border-color-focus;
        border-title-color: $border-title-color-focus;
    }

    #detail-content {
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
    }

    #detail-content > Static {
        height: auto;
    }

    .detail-label {
        color: white;
        text-style: bold;
    }

    .code-block {
        color: $foreground;
        background: #24283b;
        padding: 0 1;
        margin-bottom: 1;
        border-left: hkey #7aa2f7;
    }

    .error-block {
        color: $error;
    }

    #status-bar {
        height: 1;
        dock: bottom;
        background: $background;
        color: $secondary;
        padding: 0 1;
    }

    #compile-status {
        height: 1;
        padding: 0 1;
    }

    #compile-status.success {
        color: $success;
    }

    #compile-status.error {
        color: $error;
    }

    .status-passed {
        color: $success;
    }

    .status-failed {
        color: $error;
    }

    .test-name {
        width: 16;
    }

    .test-time {
        width: 12;
    }

    Footer {
        background: $background;
        color: $secondary;
    }

    Footer > .footer--key {
        color: $primary;
    }
    """

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False, priority=True),
        Binding("down", "cursor_down", "Down", show=False, priority=True),
        Binding("enter", "toggle_expand", "Expand/Collapse", show=True),
        Binding("tab", "toggle_focus", "Switch Panel", show=True),
        Binding("v", "toggle_verbose", "Verbose", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, path: str, testcase: str = "all", verbose: bool = False, toml_file: str = None):
        super().__init__()
        self.path = path
        self.filename = os.path.basename(path).rsplit(".", 1)[0]
        self.directory = os.path.dirname(os.path.abspath(path))
        self.input_filename = toml_file if toml_file else f"{self.directory}/{self.filename}.toml"
        self.testcase_filter = testcase
        self.verbose = verbose
        self.test_results = []
        self.focused_index = 0
        self._button_counter = 0
        self.focused_panel = "sidebar"

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-container"):
            with Container(id="sidebar"):
                yield Container(id="test-list")
            
            with Vertical(id="main-panel"):
                yield ScrollableContainer(id="detail-content")
        
        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.register_theme(NIGHTFOX_THEME)
        self.theme = "nightfox"
        
        sidebar = self.query_one("#sidebar")
        sidebar.border_title = "Tests"
        
        main_panel = self.query_one("#main-panel")
        main_panel.border_title = "Test Details"
        
        self.run_tests()

    def run_tests(self) -> None:
        test_list = self.query_one("#test-list")
        
        test_data = self.parse_tests()
        
        for name, test in test_data.items():
            if self.testcase_filter != "all" and name != self.testcase_filter:
                continue
            
            self.run_single_test(test_list, name, test)
            
            if self.test_results[-1]["status"] == "timeout":
                break

        self.render_detail()
        self.show_summary()
        
        self.call_later(self._set_initial_focus)

    @classmethod
    def compile(cls, path: str) -> bool:
        import subprocess
        import os
        filename = os.path.basename(path).rsplit(".", 1)[0]
        directory = os.path.dirname(os.path.abspath(path))
        compile_command = f"/opt/homebrew/bin/g++-12 -std=c++17 -O2 -o {directory}/{filename} {path}"
        
        console.print("[bold blue]Compiling...[/bold blue]")
        
        result = subprocess.run(compile_command, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            console.print("[bold green]✓ Compiled successfully[/bold green]")
            return True
        else:
            console.print(f"[bold red]✗ Compilation failed[/bold red]")
            console.print(result.stderr)
            return False

    def parse_tests(self) -> dict:
        with open(self.input_filename, 'rb') as file:
            data = tomllib.load(file)
        
        tests = {}
        for name, value in data.items():
            if isinstance(value, str):
                tests[name] = {"input": value, "expected_output": None}
            elif isinstance(value, dict):
                tests[name] = {
                    "input": value.get("input", ""),
                    "expected_output": value.get("expected_output", None)
                }
        return tests

    def run_single_test(self, test_list, name: str, test: dict):
        input_data = test["input"]
        expected = test["expected_output"]
        
        run_command = f"{self.directory}/{self.filename}"
        output = ""
        error = ""
        time_ms = 0
        status = "pending"
        
        try:
            start = time.time()
            result = subprocess.run(
                run_command,
                input=input_data,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            end = time.time()
            time_ms = (end - start) * 1000
            
            if result.returncode != 0:
                exit_code = result.returncode
                try:
                    signal_name = signal.Signals(-(exit_code)).name
                except:
                    signal_name = f"Signal {-exit_code}"
                status = "error"
                error = f"Runtime Error: {signal_name}"
            else:
                output = result.stdout
                error = result.stderr
                
                if expected is not None:
                    import re
                    actual_tokens = re.split(r'\s+', output.strip())
                    expected_tokens = re.split(r'\s+', expected.strip())
                    if actual_tokens == expected_tokens:
                        status = "passed"
                    else:
                        status = "failed"
                else:
                    status = "failed"
                    
        except subprocess.TimeoutExpired:
            status = "timeout"
            time_ms = 5000
            error = "Time Limit Exceeded"

        test_info = {
            "name": name,
            "index": len(self.test_results),
            "status": status,
            "time_ms": time_ms,
            "input": input_data,
            "output": output,
            "expected": expected,
            "error": error,
            "expanded": False
        }
        self.test_results.append(test_info)
        
        self.render_test_item(test_list, test_info)

    def render_test_item(self, test_list, test_info):
        status_icon = {
            "passed": "[#9ece6a]■[/]",
            "failed": "[#f7768e]■[/]",
            "timeout": "[#e0af68]■[/]",
            "error": "[#f7768e]■[/]"
        }.get(test_info["status"], "?")
        
        color = {
            "passed": "#9ece6a",
            "failed": "#f7768e",
            "timeout": "#e0af68",
            "error": "#f7768e"
        }.get(test_info["status"], "white")
        
        label = f"[{color}]{status_icon}[/{color}] {test_info['name']:<12} {test_info['time_ms']:>6.0f}ms"
        
        item = Static(label, classes="test-item", id=f"test_{self._button_counter}")
        item.test_index = test_info["index"]
        self._button_counter += 1
        test_list.mount(item)

    def render_detail(self) -> None:
        if not self.test_results or self.focused_index >= len(self.test_results):
            return
        
        test = self.test_results[self.focused_index]
        
        main_panel = self.query_one("#main-panel")
        detail_content = self.query_one("#detail-content")
        
        status_icon = {
            "passed": "[#9ece6a]■[/]",
            "failed": "[#f7768e]■[/]",
            "timeout": "[#e0af68]■[/]",
            "error": "[#f7768e]■[/]"
        }.get(test["status"], "?")
        
        status_color = {
            "passed": "#9ece6a",
            "failed": "#f7768e",
            "timeout": "#e0af68",
            "error": "#f7768e"
        }.get(test["status"], "white")
        
        main_panel.border_title = f"Test: {test['name']}  [{status_color}]{status_icon}[/{status_color}] {test['status']}  [dim]{test['time_ms']:.1f}ms[/dim]"
        
        show_expanded = self.verbose or test["status"] != "passed" or test.get("expanded", False)
        
        for child in detail_content.children:
            child.remove()
        
        detail_content.mount(Static("[bold]Input:[/bold]", classes="detail-label"))
        detail_content.mount(Static(test['input'], classes="code-block"))
        
        if show_expanded:
            if test["expected"] is not None:
                detail_content.mount(Static("[bold]Expected:[/bold]", classes="detail-label"))
                detail_content.mount(Static(test['expected'], classes="code-block"))
            
            if test["status"] == "timeout":
                detail_content.mount(Static("[bold]Output:[/bold]", classes="detail-label"))
                detail_content.mount(Static("[#e0af68]Time Limit Exceeded[/#e0af68]", classes="code-block"))
            else:
                detail_content.mount(Static("[bold]Output:[/bold]", classes="detail-label"))
                detail_content.mount(Static(test['output'], classes="code-block"))
        
        if test["error"] and test["status"] != "timeout":
            detail_content.mount(Static("[bold red]Error:[/bold red]", classes="detail-label"))
            detail_content.mount(Static(test['error'], classes="code-block error-block"))

    def show_summary(self) -> None:
        passed = sum(1 for t in self.test_results if t["status"] == "passed")
        failed = sum(1 for t in self.test_results if t["status"] == "failed")
        total = len(self.test_results)
        
        total_time = sum(t["time_ms"] for t in self.test_results)
        
        if failed == 0:
            status_text = f"[bold green]✓ {passed}/{total} passed[/bold green]"
        else:
            status_text = f"[bold green]✓ {passed}[/bold green]  [bold red]✗ {failed}[/bold red]"
        
        status_bar = self.query_one("#status-bar")
        status_bar.update(f"[bold]Runner[/bold] {self.path}  |  {status_text}  |  Total: {total_time:.0f}ms")

    def _set_initial_focus(self):
        test_list = self.query_one("#test-list")
        items = list(test_list.children)
        if items:
            items[0].add_class("test-item--focus")
            items[0].focus()

    def on_click(self, event: Click) -> None:
        widget = event.widget
        if hasattr(widget, 'test_index'):
            test_list = self.query_one("#test-list")
            items = list(test_list.children)
            
            if items and 0 <= self.focused_index < len(items):
                items[self.focused_index].remove_class("test-item--focus")
            
            self.focused_index = widget.test_index
            self.focused_panel = "sidebar"
            
            if items and 0 <= self.focused_index < len(items):
                items[self.focused_index].add_class("test-item--focus")
                items[self.focused_index].focus()
            
            self.render_detail()

    def action_cursor_up(self) -> None:
        test_list = self.query_one("#test-list")
        items = list(test_list.children)
        
        if items and self.focused_index > 0:
            items[self.focused_index].remove_class("test-item--focus")
            self.focused_index -= 1
            items[self.focused_index].add_class("test-item--focus")
            self.focused_panel = "sidebar"
            items[self.focused_index].focus()
            self.render_detail()

    def action_cursor_down(self) -> None:
        test_list = self.query_one("#test-list")
        items = list(test_list.children)
        
        if items and self.focused_index < len(items) - 1:
            items[self.focused_index].remove_class("test-item--focus")
            self.focused_index += 1
            items[self.focused_index].add_class("test-item--focus")
            self.focused_panel = "sidebar"
            items[self.focused_index].focus()
            self.render_detail()

    def action_toggle_expand(self) -> None:
        if 0 <= self.focused_index < len(self.test_results):
            self.test_results[self.focused_index]["expanded"] = not self.test_results[self.focused_index].get("expanded", False)
            self.render_detail()

    def action_toggle_verbose(self) -> None:
        self.verbose = not self.verbose
        for test in self.test_results:
            test["expanded"] = self.verbose
        self.render_detail()

    def action_toggle_focus(self) -> None:
        if self.focused_panel == "sidebar":
            self.focused_panel = "detail"
            detail_content = self.query_one("#detail-content")
            detail_content.focus()
        else:
            self.focused_panel = "sidebar"
            test_list = self.query_one("#test-list")
            items = list(test_list.children)
            if items and 0 <= self.focused_index < len(items):
                items[self.focused_index].focus()


def main():
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Path to file")
    parser.add_argument("-t", "--testcase", default="all", help="Testcase#")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show full details for all tests")
    parser.add_argument("-i", "--input", default=None, help="Input TOML file (default: filename.toml)")
    args = parser.parse_args()

    if not TestRunnerApp.compile(args.path):
        sys.exit(1)
    
    app = TestRunnerApp(args.path, args.testcase, args.verbose, args.input)
    app.run()


if __name__ == "__main__":
    main()
