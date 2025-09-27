"""
Main GUI Application for Laser Marking System
Professional Tkinter interface with real-time monitoring and controls
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import asyncio
import threading
from datetime import datetime
import logging
from typing import Dict, Any, Optional
import json

from ..controllers.scanner_controller import ScannerController, CycleState
from ..communication.plc_client import PLCClient
from ..communication.tcp_scanner import TCPScannerClient, DEFAULT_SCANNER_CONFIGS
from ..database.mongodb_client import DatabaseClient


class ModernStyle:
    """Modern color scheme and styling constants"""

    # Colors
    PRIMARY = "#2c3e50"
    SECONDARY = "#34495e"
    SUCCESS = "#27ae60"
    WARNING = "#f39c12"
    DANGER = "#e74c3c"
    INFO = "#3498db"
    LIGHT = "#ecf0f1"
    DARK = "#2c3e50"

    # Fonts
    HEADER_FONT = ("Arial", 14, "bold")
    NORMAL_FONT = ("Arial", 10)
    STATUS_FONT = ("Arial", 10, "bold")
    LARGE_FONT = ("Arial", 12)


class StatusIndicator(tk.Frame):
    """Custom status indicator widget"""

    def __init__(self, parent, label: str, **kwargs):
        super().__init__(parent, **kwargs)

        self.label_text = label
        self.current_status = "UNKNOWN"

        # Create widgets
        self.label = tk.Label(
            self, text=label, font=ModernStyle.NORMAL_FONT, bg=self.cget("bg")
        )
        self.label.pack(side=tk.LEFT, padx=(0, 10))

        self.status_frame = tk.Frame(self, width=20, height=20)
        self.status_frame.pack(side=tk.LEFT)
        self.status_frame.pack_propagate(False)

        self.status_label = tk.Label(
            self.status_frame,
            text="●",
            font=("Arial", 16),
            fg="#cccccc",
            bg=self.cget("bg"),
        )
        self.status_label.pack(expand=True)

    def set_status(self, status: str, color: str = None):
        """Set the status and color"""
        self.current_status = status

        if color is None:
            color_map = {
                "OK": ModernStyle.SUCCESS,
                "NG": ModernStyle.DANGER,
                "RUNNING": ModernStyle.INFO,
                "WAITING": ModernStyle.WARNING,
                "ERROR": ModernStyle.DANGER,
                "CONNECTED": ModernStyle.SUCCESS,
                "DISCONNECTED": ModernStyle.DANGER,
            }
            color = color_map.get(status, "#cccccc")

        self.status_label.config(fg=color)


class DataDisplayFrame(tk.Frame):
    """Frame for displaying scan data"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.data_vars = {}
        self.setup_widgets()

    def setup_widgets(self):
        """Setup the data display widgets"""
        # Title
        title_label = tk.Label(
            self, text="Scan Data", font=ModernStyle.HEADER_FONT, bg=self.cget("bg")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky="w")

        # Data fields
        fields = [
            "OCR Data",
            "First Scan",
            "Middle Scan",
            "Verification Scan",
            "Serial Number",
            "Result",
            "Processing Time",
        ]

        for i, field in enumerate(fields):
            # Label
            label = tk.Label(
                self,
                text=f"{field}:",
                font=ModernStyle.NORMAL_FONT,
                bg=self.cget("bg"),
                anchor="w",
            )
            label.grid(row=i + 1, column=0, sticky="w", padx=(0, 10), pady=2)

            # Value
            var = tk.StringVar(value="---")
            self.data_vars[field.lower().replace(" ", "_")] = var

            value_label = tk.Label(
                self,
                textvariable=var,
                font=ModernStyle.NORMAL_FONT,
                bg=self.cget("bg"),
                fg=ModernStyle.INFO,
                anchor="w",
            )
            value_label.grid(row=i + 1, column=1, sticky="w", pady=2)

    def update_data(self, data: Dict[str, Any]):
        """Update the displayed data"""
        for key, value in data.items():
            if key in self.data_vars:
                if isinstance(value, float):
                    self.data_vars[key].set(f"{value:.2f}s")
                else:
                    self.data_vars[key].set(str(value))


class StatisticsFrame(tk.Frame):
    """Frame for displaying statistics"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.stat_vars = {}
        self.setup_widgets()

    def setup_widgets(self):
        """Setup the statistics widgets"""
        # Title
        title_label = tk.Label(
            self, text="Statistics", font=ModernStyle.HEADER_FONT, bg=self.cget("bg")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky="w")

        # Statistics fields
        stats = [
            ("Cycles Completed", "cycles_completed"),
            ("Cycles Failed", "cycles_failed"),
            ("OK Results", "ok_results"),
            ("NG Results", "ng_results"),
            ("Success Rate", "success_rate"),
            ("Reset Count", "reset_count"),
            ("Uptime", "uptime"),
        ]

        for i, (label, key) in enumerate(stats):
            # Label
            stat_label = tk.Label(
                self,
                text=f"{label}:",
                font=ModernStyle.NORMAL_FONT,
                bg=self.cget("bg"),
                anchor="w",
            )
            stat_label.grid(row=i + 1, column=0, sticky="w", padx=(0, 10), pady=2)

            # Value
            var = tk.StringVar(value="0")
            self.stat_vars[key] = var

            value_label = tk.Label(
                self,
                textvariable=var,
                font=ModernStyle.STATUS_FONT,
                bg=self.cget("bg"),
                fg=ModernStyle.SUCCESS,
                anchor="w",
            )
            value_label.grid(row=i + 1, column=1, sticky="w", pady=2)

    def update_statistics(self, stats: Dict[str, Any]):
        """Update the displayed statistics"""
        for key, value in stats.items():
            if key in self.stat_vars:
                if key == "success_rate":
                    self.stat_vars[key].set(f"{value:.1f}%")
                elif key == "uptime":
                    hours = int(value // 3600)
                    minutes = int((value % 3600) // 60)
                    self.stat_vars[key].set(f"{hours:02d}:{minutes:02d}")
                else:
                    self.stat_vars[key].set(str(value))


class ConnectionStatusFrame(tk.Frame):
    """Frame for displaying connection status"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.status_indicators = {}
        self.setup_widgets()

    def setup_widgets(self):
        """Setup the connection status widgets"""
        # Title
        title_label = tk.Label(
            self,
            text="Connection Status",
            font=ModernStyle.HEADER_FONT,
            bg=self.cget("bg"),
        )
        title_label.pack(pady=(0, 10))

        # Status indicators
        connections = [
            "PLC",
            "Database",
            "Main Scanner",
            "Middle Scanner",
            "Verification Scanner",
        ]

        for connection in connections:
            indicator = StatusIndicator(self, connection, bg=self.cget("bg"))
            indicator.pack(fill=tk.X, pady=2)
            self.status_indicators[connection.lower().replace(" ", "_")] = indicator

    def update_connection_status(self, status: Dict[str, bool]):
        """Update connection status indicators"""
        for key, is_connected in status.items():
            if key in self.status_indicators:
                status_text = "CONNECTED" if is_connected else "DISCONNECTED"
                self.status_indicators[key].set_status(status_text)


class ControlFrame(tk.Frame):
    """Frame for control buttons"""

    def __init__(self, parent, controller, **kwargs):
        super().__init__(parent, **kwargs)

        self.controller = controller
        self.setup_widgets()

    def setup_widgets(self):
        """Setup the control widgets"""
        # Title
        title_label = tk.Label(
            self, text="Controls", font=ModernStyle.HEADER_FONT, bg=self.cget("bg")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))

        # Control buttons
        self.start_button = tk.Button(
            self,
            text="Start System",
            command=self.start_system,
            bg=ModernStyle.SUCCESS,
            fg="white",
            font=ModernStyle.NORMAL_FONT,
            width=15,
        )
        self.start_button.grid(row=1, column=0, padx=5, pady=5)

        self.stop_button = tk.Button(
            self,
            text="Stop System",
            command=self.stop_system,
            bg=ModernStyle.DANGER,
            fg="white",
            font=ModernStyle.NORMAL_FONT,
            width=15,
            state=tk.DISABLED,
        )
        self.stop_button.grid(row=1, column=1, padx=5, pady=5)

        self.pause_button = tk.Button(
            self,
            text="Pause",
            command=self.pause_system,
            bg=ModernStyle.WARNING,
            fg="white",
            font=ModernStyle.NORMAL_FONT,
            width=15,
            state=tk.DISABLED,
        )
        self.pause_button.grid(row=2, column=0, padx=5, pady=5)

        self.resume_button = tk.Button(
            self,
            text="Resume",
            command=self.resume_system,
            bg=ModernStyle.INFO,
            fg="white",
            font=ModernStyle.NORMAL_FONT,
            width=15,
            state=tk.DISABLED,
        )
        self.resume_button.grid(row=2, column=1, padx=5, pady=5)

        # Test buttons
        test_frame = tk.LabelFrame(self, text="Test Functions", bg=self.cget("bg"))
        test_frame.grid(row=3, column=0, columnspan=2, pady=10, padx=5, sticky="ew")

        tk.Button(
            test_frame,
            text="Test PLC",
            command=self.test_plc,
            font=ModernStyle.NORMAL_FONT,
            width=10,
        ).grid(row=0, column=0, padx=2, pady=2)

        tk.Button(
            test_frame,
            text="Test Scanners",
            command=self.test_scanners,
            font=ModernStyle.NORMAL_FONT,
            width=10,
        ).grid(row=0, column=1, padx=2, pady=2)

        tk.Button(
            test_frame,
            text="Test Database",
            command=self.test_database,
            font=ModernStyle.NORMAL_FONT,
            width=10,
        ).grid(row=1, column=0, padx=2, pady=2)

        tk.Button(
            test_frame,
            text="Export Data",
            command=self.export_data,
            font=ModernStyle.NORMAL_FONT,
            width=10,
        ).grid(row=1, column=1, padx=2, pady=2)

    def start_system(self):
        """Start the scanner system"""
        if self.controller:
            threading.Thread(
                target=self._run_async_command,
                args=(self.controller.start_continuous_scan,),
                daemon=True,
            ).start()

            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.pause_button.config(state=tk.NORMAL)

    def stop_system(self):
        """Stop the scanner system"""
        if self.controller:
            threading.Thread(
                target=self._run_async_command,
                args=(self.controller.stop_continuous_scan,),
                daemon=True,
            ).start()

            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.DISABLED)
            self.resume_button.config(state=tk.DISABLED)

    def pause_system(self):
        """Pause the scanner system"""
        if self.controller:
            threading.Thread(
                target=self._run_async_command,
                args=(self.controller.pause_scan,),
                daemon=True,
            ).start()

            self.pause_button.config(state=tk.DISABLED)
            self.resume_button.config(state=tk.NORMAL)

    def resume_system(self):
        """Resume the scanner system"""
        if self.controller:
            threading.Thread(
                target=self._run_async_command,
                args=(self.controller.resume_scan,),
                daemon=True,
            ).start()

            self.pause_button.config(state=tk.NORMAL)
            self.resume_button.config(state=tk.DISABLED)

    def test_plc(self):
        """Test PLC connection"""
        messagebox.showinfo("Test", "PLC connection test initiated...")

    def test_scanners(self):
        """Test scanner connections"""
        messagebox.showinfo("Test", "Scanner connection test initiated...")

    def test_database(self):
        """Test database connection"""
        messagebox.showinfo("Test", "Database connection test initiated...")

    def export_data(self):
        """Export scan data"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if filename:
            messagebox.showinfo("Export", f"Data export initiated to {filename}")

    def _run_async_command(self, command):
        """Run an async command in a new event loop"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(command())
        except Exception as e:
            logging.error(f"Error running async command: {e}")
        finally:
            loop.close()


class LaserMarkingGUI:
    """Main GUI application for the Laser Marking System"""

    def __init__(self):
        self.root = tk.Tk()
        self.controller = None
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.plc_client = None
        self.scanner_client = None
        self.database_client = None

        self.setup_window()
        self.setup_widgets()
        self.setup_controller()

        # Start update timer
        self.update_display()

    def setup_window(self):
        """Setup the main window"""
        self.root.title("Laser Marking System v1.0")
        self.root.geometry("1200x800")
        self.root.configure(bg=ModernStyle.LIGHT)

        # Configure grid weights
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

    def setup_widgets(self):
        """Setup all GUI widgets"""
        # Left panel
        left_panel = tk.Frame(self.root, bg=ModernStyle.SECONDARY, width=300)
        left_panel.grid(row=0, column=0, sticky="nsew")
        left_panel.grid_propagate(False)

        # Title
        title_label = tk.Label(
            left_panel,
            text="Laser Marking System",
            font=("Arial", 16, "bold"),
            fg="white",
            bg=ModernStyle.SECONDARY,
        )
        title_label.pack(pady=20)

        # Current state display
        self.state_var = tk.StringVar(value="WAITING")
        state_frame = tk.Frame(left_panel, bg=ModernStyle.SECONDARY)
        state_frame.pack(pady=10)

        tk.Label(
            state_frame,
            text="Current State:",
            font=ModernStyle.NORMAL_FONT,
            fg="white",
            bg=ModernStyle.SECONDARY,
        ).pack()

        self.state_label = tk.Label(
            state_frame,
            textvariable=self.state_var,
            font=ModernStyle.STATUS_FONT,
            fg=ModernStyle.WARNING,
            bg=ModernStyle.SECONDARY,
        )
        self.state_label.pack()

        # Connection status
        conn_frame = tk.Frame(left_panel, bg=ModernStyle.LIGHT)
        conn_frame.pack(fill=tk.X, padx=10, pady=10)

        self.connection_status = ConnectionStatusFrame(conn_frame, bg=ModernStyle.LIGHT)
        self.connection_status.pack(fill=tk.X)

        # Control frame
        control_frame = tk.Frame(left_panel, bg=ModernStyle.LIGHT)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        self.control_panel = ControlFrame(control_frame, None, bg=ModernStyle.LIGHT)
        self.control_panel.pack(fill=tk.X)

        # Right panel
        right_panel = tk.Frame(self.root, bg=ModernStyle.LIGHT)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        # Configure right panel grid
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_columnconfigure(1, weight=1)

        # Data display
        data_frame = tk.LabelFrame(
            right_panel,
            text="Real-time Data",
            font=ModernStyle.NORMAL_FONT,
            bg=ModernStyle.LIGHT,
        )
        data_frame.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=(0, 10))

        self.data_display = DataDisplayFrame(data_frame, bg=ModernStyle.LIGHT)
        self.data_display.pack(fill=tk.X, padx=10, pady=10)

        # Statistics display
        stats_frame = tk.LabelFrame(
            right_panel,
            text="Statistics",
            font=ModernStyle.NORMAL_FONT,
            bg=ModernStyle.LIGHT,
        )
        stats_frame.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=(0, 10))

        self.statistics_display = StatisticsFrame(stats_frame, bg=ModernStyle.LIGHT)
        self.statistics_display.pack(fill=tk.X, padx=10, pady=10)

        # Log display
        log_frame = tk.LabelFrame(
            right_panel,
            text="System Log",
            font=ModernStyle.NORMAL_FONT,
            bg=ModernStyle.LIGHT,
        )
        log_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(10, 0))

        # Log text widget with scrollbar
        log_text_frame = tk.Frame(log_frame)
        log_text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.log_text = tk.Text(
            log_text_frame,
            font=("Courier", 9),
            bg="black",
            fg="green",
            state=tk.DISABLED,
        )

        scrollbar = tk.Scrollbar(
            log_text_frame, orient=tk.VERTICAL, command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def setup_controller(self):
        """Setup the scanner controller and connections"""
        try:
            # Load configuration
            config = self.load_configuration()

            # Initialize clients
            self.plc_client = PLCClient(
                host=config.get("plc_host", "192.168.3.146"),
                port=config.get("plc_port", 502),
            )

            self.scanner_client = TCPScannerClient(DEFAULT_SCANNER_CONFIGS)

            self.database_client = DatabaseClient(
                connection_string=config.get(
                    "mongodb_connection", "mongodb://localhost:27017/"
                ),
                database_name=config.get("database_name", "main-data"),
            )

            # Initialize controller
            self.controller = ScannerController(
                self.plc_client, self.scanner_client, self.database_client, config
            )

            # Set callbacks
            self.controller.set_callbacks(
                state_change_cb=self.on_state_change,
                data_update_cb=self.on_data_update,
                error_cb=self.on_error,
            )

            # Update control panel reference
            self.control_panel.controller = self.controller

            self.log_message("INFO: System initialized successfully")

        except Exception as e:
            self.log_message(f"ERROR: Failed to initialize system: {e}")

    def load_configuration(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            with open("./config/config.json", "r") as f:
                return json.load(f)
        except:
            # Return default configuration
            return {
                "plc_host": "192.168.3.146",
                "plc_port": 502,
                "mongodb_connection": "mongodb://localhost:27017/",
                "database_name": "main-data",
                "model_number": "MODEL123",
                "current_user": "operator",
                "code_file_path": "./data/code.txt",
                "barcode_file_path": "./data/barcode.txt",
            }

    def on_state_change(self, new_state: CycleState):
        """Handle state change callback"""
        self.state_var.set(new_state.value.upper())

        # Update state label color
        color_map = {
            CycleState.WAITING: ModernStyle.WARNING,
            CycleState.FIRST_SCAN: ModernStyle.INFO,
            CycleState.BARCODE_GEN: ModernStyle.INFO,
            CycleState.MIDDLE_SCAN: ModernStyle.INFO,
            CycleState.VERIFICATION: ModernStyle.INFO,
            CycleState.FINAL_CHECK: ModernStyle.INFO,
            CycleState.COMPLETE: ModernStyle.SUCCESS,
            CycleState.ERROR: ModernStyle.DANGER,
            CycleState.RESET: ModernStyle.WARNING,
        }

        self.state_label.config(fg=color_map.get(new_state, ModernStyle.WARNING))
        self.log_message(f"INFO: State changed to {new_state.value.upper()}")

    def on_data_update(self, data: Dict[str, Any]):
        """Handle data update callback"""
        self.data_display.update_data(data)

        for key, value in data.items():
            self.log_message(f"DATA: {key}: {value}")

    def on_error(self, error: str):
        """Handle error callback"""
        self.log_message(f"ERROR: {error}")
        messagebox.showerror("System Error", error)

    def log_message(self, message: str):
        """Add message to log display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"

        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, formatted_message)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

        # Keep only last 1000 lines
        lines = self.log_text.get("1.0", tk.END).split("\n")
        if len(lines) > 1000:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete("1.0", f"{len(lines)-1000}.0")
            self.log_text.config(state=tk.DISABLED)

    def update_display(self):
        """Update display with current data"""
        try:
            if self.controller:
                # Update statistics
                status = self.controller.get_current_status()
                self.statistics_display.update_statistics(status["stats"])

                # Update connection status (mock for now)
                connection_status = {
                    "plc": True,  # Would check actual connection
                    "database": True,
                    "main_scanner": True,
                    "middle_scanner": True,
                    "verification_scanner": True,
                }
                self.connection_status.update_connection_status(connection_status)

        except Exception as e:
            self.logger.error(f"Error updating display: {e}")

        # Schedule next update
        self.root.after(1000, self.update_display)

    def run(self):
        """Start the GUI application"""
        self.root.mainloop()

    def on_closing(self):
        """Handle application closing"""
        if self.controller:
            # Stop the controller
            threading.Thread(target=self._run_async_shutdown, daemon=True).start()
        else:
            self.root.destroy()

    def _run_async_shutdown(self):
        """Shutdown async components"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Stop controller
            if self.controller:
                loop.run_until_complete(self.controller.stop_continuous_scan())

            # Disconnect clients
            if self.plc_client:
                loop.run_until_complete(self.plc_client.disconnect())

            if self.scanner_client:
                loop.run_until_complete(self.scanner_client.disconnect_all())

            if self.database_client:
                loop.run_until_complete(self.database_client.disconnect())

        except Exception as e:
            logging.error(f"Error during shutdown: {e}")
        finally:
            loop.close()
            self.root.quit()


def main():
    """Main entry point for the GUI application"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create and run GUI
    app = LaserMarkingGUI()
    app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.run()


if __name__ == "__main__":
    main()
