"""
Canvas CLI - Main entry point for Canvas automation actions
"""

import os
import argparse
import subprocess
import sys
import signal
import threading
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from rich.prompt import PromptBase
from rich.text import Text

# Load environment variables
load_dotenv()

console = Console()

# Global flag to track if browser window is closed
browser_closed = False


def signal_handler(signum, frame):
    """Handle signals for graceful shutdown"""
    global browser_closed
    browser_closed = True
    console.print("\n[yellow]Browser window closed by user[/yellow]")
    console.print("[green]Goodbye![/green]")
    sys.exit(0)


def monitor_browser_window():
    """Monitor if browser window is still open"""
    global browser_closed
    import time
    
    # Try to import psutil, if not available use alternative method
    try:
        import psutil
        has_psutil = True
    except ImportError:
        has_psutil = False
        console.print("[yellow]Note: psutil not available, using alternative browser monitoring[/yellow]")
    
    while not browser_closed:
        try:
            if has_psutil:
                # Check if any Chromium/Chrome processes are running
                chromium_processes = [p for p in psutil.process_iter(['pid', 'name']) 
                                    if 'chrome' in p.info['name'].lower() or 'chromium' in p.info['name'].lower()]
                
                if not chromium_processes:
                    browser_closed = True
                    console.print("\n[yellow]Browser window closed[/yellow]")
                    console.print("[green]Goodbye![/green]")
                    sys.exit(0)
            else:
                # Alternative: Check if we can still interact with the browser
                # This is a simpler approach that doesn't require psutil
                import subprocess
                try:
                    # Try to list processes using system commands
                    if os.name == 'posix':  # Unix/Linux/Mac
                        result = subprocess.run(['pgrep', '-f', 'chrome'], 
                                              capture_output=True, text=True)
                        if result.returncode != 0:  # No chrome processes found
                            browser_closed = True
                            console.print("\n[yellow]Browser window closed[/yellow]")
                            console.print("[green]Goodbye![/green]")
                            sys.exit(0)
                    else:  # Windows
                        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                                              capture_output=True, text=True)
                        if 'chrome.exe' not in result.stdout:
                            browser_closed = True
                            console.print("\n[yellow]Browser window closed[/yellow]")
                            console.print("[green]Goodbye![/green]")
                            sys.exit(0)
                except Exception:
                    pass
                
        except Exception:
            pass
        
        time.sleep(2)  # Check every 2 seconds


def select_from_list(options, title="Select an option", default=0):
    """Interactive selection using arrow keys"""
    if not options:
        return None
    
    current_index = default
    
    def display_options():
        """Display the current options with highlighting"""
        # Clear the screen properly
        os.system('clear' if os.name == 'posix' else 'cls')
        
        console.print(f"[bold cyan]{title}[/bold cyan]")
        console.print("[dim]Use ↑/↓ arrows to navigate, Enter to select, Ctrl+C to exit[/dim]\n")
        
        for i, option in enumerate(options):
            if i == current_index:
                console.print(f"[bold green]▶ {option}[/bold green]")
            else:
                console.print(f"  {option}")
        console.print()  # Add a newline at the end
    
    # Initial display
    display_options()
    
    try:
        while True:
            # Get user input
            try:
                import msvcrt  # Windows
                key = msvcrt.getch()
                if key == b'\xe0':  # Arrow key prefix on Windows
                    key = msvcrt.getch()
                    if key == b'H':  # Up arrow
                        current_index = (current_index - 1) % len(options)
                        display_options()
                    elif key == b'P':  # Down arrow
                        current_index = (current_index + 1) % len(options)
                        display_options()
                elif key == b'\r':  # Enter key
                    return options[current_index]
            except ImportError:
                # Unix/Linux/Mac
                import tty
                import termios
                import sys
                
                def getch():
                    fd = sys.stdin.fileno()
                    old_settings = termios.tcgetattr(fd)
                    try:
                        tty.setraw(sys.stdin.fileno())
                        ch = sys.stdin.read(1)
                        if ch == '\x1b':  # Escape sequence
                            ch += sys.stdin.read(2)
                        return ch
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                
                key = getch()
                if key == '\x1b[A':  # Up arrow
                    current_index = (current_index - 1) % len(options)
                    display_options()
                elif key == '\x1b[B':  # Down arrow
                    current_index = (current_index + 1) % len(options)
                    display_options()
                elif key == '\r':  # Enter key
                    return options[current_index]
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        console.print("[green]Goodbye![/green]")
        return None


def get_course_selector():
    """Get course selector from user"""
    from course_utils import load_courses_config

    config = load_courses_config()
    courses = config.get('courses', {})
    
    if not courses:
        console.print("[red]No courses found in courses.json[/red]")
        return None
    
    # Create options with display names
    course_options = []
    course_keys = []
    for key, course in courses.items():
        course_id = course.get('course_id', 'N/A')
        name = course.get('name', 'Unnamed Course')
        display_name = f"{key} - {name} (ID: {course_id})"
        course_options.append(display_name)
        course_keys.append(key)
    
    # Show course info first
    console.print("\n[bold blue]Available Courses:[/bold blue]")
    for i, option in enumerate(course_options):
        console.print(f"  {option}")
    
    # Use arrow key selection
    selected_display = select_from_list(course_options, "Select a Course")
    if selected_display:
        # Extract the key from the selected display name
        selected_index = course_options.index(selected_display)
        return course_keys[selected_index]
    return None


def get_week_selector():
    """Get week selector from user"""
    while True:
        try:
            week_input = Prompt.ask(
                "Enter week number (or press Enter for auto-calculate)",
                default=""
            )
            if week_input.strip() == "":
                return None
            week_id = int(week_input)
            if 1 <= week_id <= 8:
                return week_id
            else:
                console.print("[red]Week must be between 1 and 8[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")


def get_llm_provider():
    """Get LLM provider from user"""
    # Check which providers have API keys
    openai_key = os.getenv('OPENAI_API_KEY', '')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY', '')
    deepseek_key = os.getenv('DEEPSEEK_API_KEY', '')
    
    available_providers = []
    if openai_key:
        available_providers.append('openai')
    if anthropic_key:
        available_providers.append('anthropic')
    if deepseek_key:
        available_providers.append('deepseek')
    
    if not available_providers:
        console.print("[red]No LLM API keys found. Please set at least one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY[/red]")
        return None
    
    if len(available_providers) == 1:
        console.print(f"[green]Using {available_providers[0]} (only provider available)[/green]")
        return available_providers[0]
    
    # Create display options with descriptions
    provider_descriptions = {
        'openai': 'OpenAI GPT models',
        'anthropic': 'Anthropic Claude models',
        'deepseek': 'DeepSeek models'
    }
    
    provider_options = []
    for provider in available_providers:
        description = provider_descriptions.get(provider, '')
        display_name = f"{provider} - {description}"
        provider_options.append(display_name)
    
    console.print("\n[bold blue]Available LLM Providers:[/bold blue]")
    for option in provider_options:
        console.print(f"  {option}")
    
    # Use arrow key selection
    selected_display = select_from_list(provider_options, "Select LLM Provider")
    if selected_display:
        # Extract the provider name from the selected display name
        return selected_display.split(' - ')[0]
    return None


def run_discussion_action(args=None):
    """Run the discussion scraping action"""
    from discussions import run_discussion_action
    
    username = os.getenv('CANVAS_USERNAME')
    password = os.getenv('CANVAS_PASSWORD')
    
    if not username or not password:
        raise ValueError("CANVAS_USERNAME and CANVAS_PASSWORD environment variables must be set")
    
    # If args provided (from CLI), use them; otherwise use interactive mode
    if args:
        course_selector = args.course
        week_id = args.week
        llm_provider = args.provider
    else:
        # Interactive mode
        console.print(Panel.fit("[bold blue]Discussion Action Setup[/bold blue]"))
        course_selector = get_course_selector()
        if not course_selector:
            return
        
        week_id = get_week_selector()
        llm_provider = get_llm_provider()
        if not llm_provider:
            return
    
    # Start browser monitoring thread
    browser_monitor = threading.Thread(target=monitor_browser_window, daemon=True)
    browser_monitor.start()
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        run_discussion_action(
            email=username, 
            password=password, 
            course_selector=course_selector,
            week_id=week_id,
            llm_provider=llm_provider
        )
    except Exception as e:
        if not browser_closed:
            console.print(f"[red]Error: {e}[/red]")
            console.print("[green]Goodbye![/green]")


def run_announcement_action(args=None):
    """Run the announcement scheduling action"""
    from announcements import schedule_announcements
    
    username = os.getenv('CANVAS_USERNAME')
    password = os.getenv('CANVAS_PASSWORD')
    
    if not username or not password:
        raise ValueError("CANVAS_USERNAME and CANVAS_PASSWORD environment variables must be set")
    
    # If args provided (from CLI), use them; otherwise use interactive mode
    if args:
        course_selector = args.course
    else:
        # Interactive mode
        console.print(Panel.fit("[bold blue]Announcement Action Setup[/bold blue]"))
        course_selector = get_course_selector()
        if not course_selector:
            return
    
    # Start browser monitoring thread
    browser_monitor = threading.Thread(target=monitor_browser_window, daemon=True)
    browser_monitor.start()
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        schedule_announcements(username, password, course_selector)
    except Exception as e:
        if not browser_closed:
            console.print(f"[red]Error: {e}[/red]")
            console.print("[green]Goodbye![/green]")


def show_main_menu():
    """Show the main interactive menu"""
    try:
        console.print(Panel.fit(
            "[bold green]Canvas CLI - Automation Tools[/bold green]\n\n"
            "Choose an action to perform:",
            title="Welcome"
        ))
        
        # Create menu options
        menu_options = [
            "discussion - Scrape discussions and generate AI responses",
            "announcement - Schedule course announcements",
            "donate - Support the project ☕",
            "exit - Exit the application"
        ]
        
        console.print("\n[bold blue]Available Actions:[/bold blue]")
        for option in menu_options:
            console.print(f"  {option}")
        
        # Use arrow key selection
        selected = select_from_list(menu_options, "Select an Action")
        
        if selected:
            action = selected.split(' - ')[0]
            if action == "discussion":
                run_discussion_action()
            elif action == "announcement":
                run_announcement_action()
            elif action == "donate":
                console.print()
                console.print(Panel.fit(
                    "[bold cyan]☕ Support Canvas CLI[/bold cyan]\n\n"
                    "Thank you for considering supporting this project!\n\n"
                    "Your donation helps maintain and improve this tool\n"
                    "for educators everywhere.\n\n"
                    "[bold green]Visit:[/bold green] [link=https://buymeacoffee.com/seanpavlak]https://buymeacoffee.com/seanpavlak[/link]\n\n"
                    "[dim]Opening in your browser...[/dim]",
                    title="Donation"
                ))
                import webbrowser
                webbrowser.open("https://buymeacoffee.com/seanpavlak")
                console.print("\n[green]Press Enter to return to menu...[/green]")
                input()
                show_main_menu()  # Return to menu
            elif action == "exit":
                console.print("[green]Goodbye![/green]")
        else:
            # User cancelled with Ctrl+C
            console.print("[green]Goodbye![/green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        console.print("[green]Goodbye![/green]")


def main():
    """Main entry point with CLI argument support and interactive mode"""
    try:
        parser = argparse.ArgumentParser(
            description='Canvas CLI - Automation tools for Canvas LMS',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Available actions:
  discussion    - Scrape discussions and generate AI responses
  announcement  - Schedule course announcements

Examples:
  python main.py discussion --course A --week 3
  python main.py announcement --course B
  python main.py  (interactive mode)

---
💡 Find this tool helpful? Support the project: https://buymeacoffee.com/seanpavlak
            """
        )
        
        # Add subcommands
        subparsers = parser.add_subparsers(dest='action', help='Available actions')
        
        # Discussion action
        discussion_parser = subparsers.add_parser('discussion', help='Scrape discussions and generate AI responses')
        discussion_parser.add_argument('--provider', choices=['openai', 'anthropic', 'deepseek'], 
                                     help='LLM provider to use (auto-detected if not specified)')
        discussion_parser.add_argument('--course', default='A', 
                                     help='Course selector (default: A)')
        discussion_parser.add_argument('--week', type=int, 
                                     help='Week ID (auto-calculated if not specified)')
        
        # Announcement action
        announcement_parser = subparsers.add_parser('announcement', help='Schedule course announcements')
        announcement_parser.add_argument('--course', default='A', 
                                       help='Course selector (default: A)')
        
        args = parser.parse_args()
        
        # If no arguments provided, show interactive menu
        if not args.action:
            show_main_menu()
            return
        
        # Route to appropriate action
        if args.action == 'discussion':
            run_discussion_action(args)
        elif args.action == 'announcement':
            run_announcement_action(args)
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        console.print("[green]Goodbye![/green]")
        sys.exit(0)


if __name__ == "__main__":
    main()