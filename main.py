#!/usr/bin/env python3
"""
Laser Marking System - Main Entry Point
Professional industrial laser marking and barcode scanning system
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.utils.logging_system import initialize_logging
from src.utils.config_manager import ConfigurationManager
from src.gui.main_gui import LaserMarkingGUI, main as gui_main


def setup_environment():
    """Setup the application environment"""
    # Create required directories
    directories = ["./data", "./logs", "./config", "./data/backup"]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    # Create empty data files if they don't exist
    data_files = ["./data/code.txt", "./data/barcode.txt", "./data/serial_counter.json"]

    for file_path in data_files:
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                if file_path.endswith(".json"):
                    f.write("{}")
                else:
                    f.write("")


def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = ["pymodbus", "pymongo", "motor", "tkinter"]

    missing_packages = []

    for package in required_packages:
        try:
            if package == "tkinter":
                import tkinter
            else:
                __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print("Error: Missing required packages:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nPlease install required packages:")
        print("  pip install -r requirements.txt")
        return False

    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Laser Marking System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Start GUI application
  python main.py --config custom.json  # Use custom config
  python main.py --check-deps       # Check dependencies only
  python main.py --setup-env        # Setup environment only
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        default="./config/config.json",
        help="Configuration file path (default: ./config/config.json)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--check-deps", action="store_true", help="Check dependencies and exit"
    )

    parser.add_argument(
        "--setup-env", action="store_true", help="Setup environment and exit"
    )

    parser.add_argument(
        "--version", action="version", version="Laser Marking System v1.0.0"
    )

    args = parser.parse_args()

    # Handle special commands
    if args.check_deps:
        if check_dependencies():
            print("All dependencies are installed correctly.")
            return 0
        else:
            return 1

    if args.setup_env:
        setup_environment()
        print("Environment setup completed.")
        return 0

    # Check dependencies
    if not check_dependencies():
        return 1

    # Setup environment
    setup_environment()

    try:
        # Initialize configuration
        config_manager = ConfigurationManager(args.config)
        config = config_manager.get_config()

        # Override log level if specified
        if args.log_level:
            config["logging"]["level"] = args.log_level

        # Initialize logging
        initialize_logging(config.get("logging", {}))

        # Validate configuration
        issues = config_manager.validate_configuration()
        if issues:
            print("Configuration validation issues found:")
            for section, section_issues in issues.items():
                print(f"  {section}:")
                for issue in section_issues:
                    print(f"    - {issue}")
            print("\nPlease fix configuration issues before continuing.")
            return 1

        print("Starting Laser Marking System...")
        print(f"Configuration: {args.config}")
        print(f"Log level: {args.log_level}")
        print("=" * 50)

        # Start GUI application
        gui_main()

        return 0

    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        return 0

    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
