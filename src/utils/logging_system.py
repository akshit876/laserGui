"""
Logging and Error Handling for Laser Marking System
Comprehensive logging setup with error recovery mechanisms
"""

import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from pathlib import Path
import asyncio
from functools import wraps


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for better log readability"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset_color = self.COLORS["RESET"]

        # Add color to level name
        record.levelname = f"{log_color}{record.levelname}{reset_color}"

        return super().format(record)


class SystemLogger:
    """
    Centralized logging system for the laser marking application
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the logging system

        Args:
            config: Logging configuration dictionary
        """
        self.config = config or self._get_default_config()
        self.loggers = {}
        self.error_callbacks = []

        self.setup_logging()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default logging configuration"""
        return {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "log_file_path": "./logs/system.log",
            "max_file_size": 10485760,  # 10MB
            "backup_count": 5,
            "console_output": True,
        }

    def setup_logging(self):
        """Setup the logging configuration"""
        try:
            # Create logs directory if it doesn't exist
            log_file = self.config["log_file_path"]
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

            # Configure root logger
            root_logger = logging.getLogger()
            root_logger.setLevel(getattr(logging, self.config["level"].upper()))

            # Clear existing handlers
            root_logger.handlers.clear()

            # File handler with rotation
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self.config["max_file_size"],
                backupCount=self.config["backup_count"],
                encoding="utf-8",
            )

            file_formatter = logging.Formatter(
                self.config["format"], datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)

            # Console handler (if enabled)
            if self.config["console_output"]:
                console_handler = logging.StreamHandler(sys.stdout)
                console_formatter = ColoredFormatter(
                    self.config["format"], datefmt="%Y-%m-%d %H:%M:%S"
                )
                console_handler.setFormatter(console_formatter)
                root_logger.addHandler(console_handler)

            # Setup exception handler
            sys.excepthook = self._handle_exception

            # Log system startup
            logger = self.get_logger("SystemLogger")
            logger.info("Logging system initialized")
            logger.info(f"Log level: {self.config['level']}")
            logger.info(f"Log file: {log_file}")

        except Exception as e:
            print(f"Failed to setup logging: {e}")

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get or create a logger with the given name

        Args:
            name: Logger name

        Returns:
            Logger instance
        """
        if name not in self.loggers:
            logger = logging.getLogger(name)
            self.loggers[name] = logger

        return self.loggers[name]

    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions"""
        if issubclass(exc_type, KeyboardInterrupt):
            # Allow keyboard interrupts to work normally
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger = self.get_logger("UncaughtException")
        logger.critical(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

        # Notify error callbacks
        error_info = {
            "type": "uncaught_exception",
            "exception_type": exc_type.__name__,
            "message": str(exc_value),
            "traceback": traceback.format_exception(exc_type, exc_value, exc_traceback),
        }

        for callback in self.error_callbacks:
            try:
                callback(error_info)
            except:
                pass  # Don't let callback errors crash the system

    def add_error_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Add callback function to be called on errors

        Args:
            callback: Function to call with error information
        """
        self.error_callbacks.append(callback)

    def remove_error_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Remove error callback"""
        if callback in self.error_callbacks:
            self.error_callbacks.remove(callback)

    def log_system_info(self):
        """Log system information at startup"""
        logger = self.get_logger("SystemInfo")

        logger.info(f"Python version: {sys.version}")
        logger.info(f"Platform: {sys.platform}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Log file: {self.config['log_file_path']}")


class ErrorHandler:
    """
    Error handling and recovery mechanisms
    """

    def __init__(self, logger: logging.Logger):
        """
        Initialize error handler

        Args:
            logger: Logger instance to use
        """
        self.logger = logger
        self.error_counts = {}
        self.recovery_strategies = {}

    def register_recovery_strategy(self, error_type: str, strategy: Callable):
        """
        Register a recovery strategy for specific error types

        Args:
            error_type: Type of error (e.g., "connection_error")
            strategy: Recovery function to call
        """
        self.recovery_strategies[error_type] = strategy

    async def handle_error(
        self, error: Exception, error_type: str = None, context: Dict[str, Any] = None
    ) -> bool:
        """
        Handle an error with logging and recovery attempts

        Args:
            error: Exception that occurred
            error_type: Type of error for recovery strategy lookup
            context: Additional context information

        Returns:
            bool: True if error was handled/recovered, False otherwise
        """
        error_key = error_type or type(error).__name__

        # Increment error count
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

        # Log the error
        context_str = f" Context: {context}" if context else ""
        self.logger.error(
            f"Error ({error_key}): {str(error)}{context_str}", exc_info=True
        )

        # Try recovery strategy if available
        if error_type in self.recovery_strategies:
            try:
                self.logger.info(f"Attempting recovery for {error_type}")
                recovery_func = self.recovery_strategies[error_type]

                if asyncio.iscoroutinefunction(recovery_func):
                    result = await recovery_func(error, context)
                else:
                    result = recovery_func(error, context)

                if result:
                    self.logger.info(f"Recovery successful for {error_type}")
                    return True
                else:
                    self.logger.warning(f"Recovery failed for {error_type}")

            except Exception as recovery_error:
                self.logger.error(
                    f"Recovery strategy failed for {error_type}: {recovery_error}",
                    exc_info=True,
                )

        return False

    def get_error_statistics(self) -> Dict[str, int]:
        """Get error count statistics"""
        return self.error_counts.copy()

    def reset_error_counts(self):
        """Reset error count statistics"""
        self.error_counts.clear()


class PerformanceMonitor:
    """
    Performance monitoring and logging
    """

    def __init__(self, logger: logging.Logger):
        """
        Initialize performance monitor

        Args:
            logger: Logger instance to use
        """
        self.logger = logger
        self.performance_data = {}

    def start_timing(self, operation: str) -> str:
        """
        Start timing an operation

        Args:
            operation: Name of the operation

        Returns:
            str: Timing ID for stopping the timer
        """
        timing_id = f"{operation}_{datetime.now().timestamp()}"
        self.performance_data[timing_id] = {
            "operation": operation,
            "start_time": datetime.now(),
            "end_time": None,
            "duration": None,
        }
        return timing_id

    def stop_timing(self, timing_id: str):
        """
        Stop timing an operation

        Args:
            timing_id: Timing ID returned by start_timing
        """
        if timing_id in self.performance_data:
            data = self.performance_data[timing_id]
            data["end_time"] = datetime.now()
            data["duration"] = (data["end_time"] - data["start_time"]).total_seconds()

            # Log if duration is significant
            if data["duration"] > 1.0:  # More than 1 second
                self.logger.info(
                    f"Performance: {data['operation']} took {data['duration']:.2f}s"
                )

    def log_performance_summary(self):
        """Log performance summary"""
        if not self.performance_data:
            return

        operations = {}
        for data in self.performance_data.values():
            if data["duration"] is not None:
                op_name = data["operation"]
                if op_name not in operations:
                    operations[op_name] = []
                operations[op_name].append(data["duration"])

        for op_name, durations in operations.items():
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)

            self.logger.info(
                f"Performance Summary - {op_name}: "
                f"avg={avg_duration:.2f}s, max={max_duration:.2f}s, "
                f"min={min_duration:.2f}s, count={len(durations)}"
            )


def timing_decorator(logger: Optional[logging.Logger] = None):
    """
    Decorator to automatically time function execution

    Args:
        logger: Logger to use (default: create new one)
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)

            start_time = datetime.now()

            try:
                result = await func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()

                if duration > 0.1:  # Log if > 100ms
                    logger.debug(f"{func.__name__} executed in {duration:.3f}s")

                return result

            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"{func.__name__} failed after {duration:.3f}s: {e}", exc_info=True
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)

            start_time = datetime.now()

            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()

                if duration > 0.1:  # Log if > 100ms
                    logger.debug(f"{func.__name__} executed in {duration:.3f}s")

                return result

            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"{func.__name__} failed after {duration:.3f}s: {e}", exc_info=True
                )
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    logger: Optional[logging.Logger] = None,
):
    """
    Decorator to retry function execution on failure

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay on each retry
        logger: Logger to use for retry messages
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)

            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}",
                            exc_info=True,
                        )

            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)

            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        import time

                        time.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}",
                            exc_info=True,
                        )

            raise last_exception

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


# Global system logger instance
system_logger = None


def initialize_logging(config: Optional[Dict[str, Any]] = None) -> SystemLogger:
    """
    Initialize the global logging system

    Args:
        config: Logging configuration

    Returns:
        SystemLogger instance
    """
    global system_logger
    system_logger = SystemLogger(config)
    return system_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    if system_logger is None:
        initialize_logging()

    return system_logger.get_logger(name)
