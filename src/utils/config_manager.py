"""
Configuration Management for Laser Marking System
Handles loading and validation of configuration files
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class PLCConfig:
    """PLC configuration"""

    host: str = "192.168.3.146"
    port: int = 502
    timeout: int = 5
    retries: int = 3
    polling_interval: float = 0.1


@dataclass
class ScannerConfig:
    """Scanner configuration"""

    host: str
    port: int
    timeout: int = 30
    trigger_command: Optional[str] = None
    description: str = ""


@dataclass
class DatabaseConfig:
    """Database configuration"""

    connection_string: str = "mongodb://localhost:27017/"
    database_name: str = "main-data"
    collection_name: str = "records"
    timeout: int = 10
    backup_interval: int = 3600


@dataclass
class FileConfig:
    """File paths configuration"""

    code_file_path: str = "./data/code.txt"
    barcode_file_path: str = "./data/barcode.txt"
    log_file_path: str = "./logs/system.log"
    backup_directory: str = "./data/backup"


@dataclass
class ProductionConfig:
    """Production settings"""

    model_number: str = "MODEL123"
    current_user: str = "operator"
    shift_start_hour: int = 6
    shift_duration_hours: int = 8
    serial_number_format: str = "YYYYMMDD{shift}{counter:04d}"
    quality_grades: list = None

    def __post_init__(self):
        if self.quality_grades is None:
            self.quality_grades = ["A", "B", "C", "N/A"]


@dataclass
class LoggingConfig:
    """Logging configuration"""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5
    console_output: bool = True
    log_file_path: str = "./logs/system.log"


class ConfigurationManager:
    """
    Configuration manager for the laser marking system
    Handles loading, validation, and access to configuration settings
    """

    def __init__(self, config_file: str = "./config/config.json"):
        """
        Initialize configuration manager

        Args:
            config_file: Path to configuration file
        """
        self.config_file = config_file
        self.logger = logging.getLogger(__name__)
        self._config_data = {}
        self._typed_configs = {}

        # Load configuration
        self.load_configuration()

    def load_configuration(self) -> bool:
        """
        Load configuration from file

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create config file with defaults if it doesn't exist
            if not os.path.exists(self.config_file):
                self.create_default_config()

            with open(self.config_file, "r", encoding="utf-8") as f:
                self._config_data = json.load(f)

            # Create typed configuration objects
            self._create_typed_configs()

            self.logger.info(f"Configuration loaded from {self.config_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            # Use defaults
            self._config_data = self._get_default_config()
            self._create_typed_configs()
            return False

    def save_configuration(self) -> bool:
        """
        Save current configuration to file

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Configuration saved to {self.config_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            return False

    def create_default_config(self):
        """Create default configuration file"""
        self._config_data = self._get_default_config()
        self.save_configuration()

    def _create_typed_configs(self):
        """Create typed configuration objects"""
        try:
            # PLC configuration
            plc_data = self._config_data.get("plc", {})
            self._typed_configs["plc"] = PLCConfig(**plc_data)

            # Scanner configurations
            scanners_data = self._config_data.get("scanners", {})
            self._typed_configs["scanners"] = {}

            for scanner_name, scanner_data in scanners_data.items():
                self._typed_configs["scanners"][scanner_name] = ScannerConfig(
                    **scanner_data
                )

            # Database configuration
            db_data = self._config_data.get("database", {})
            self._typed_configs["database"] = DatabaseConfig(**db_data)

            # File configuration
            files_data = self._config_data.get("files", {})
            self._typed_configs["files"] = FileConfig(**files_data)

            # Production configuration
            prod_data = self._config_data.get("production", {})
            self._typed_configs["production"] = ProductionConfig(**prod_data)

            # Logging configuration
            log_data = self._config_data.get("logging", {})
            self._typed_configs["logging"] = LoggingConfig(**log_data)

        except Exception as e:
            self.logger.error(f"Error creating typed configurations: {e}")

    def get_config(self, section: str = None) -> Any:
        """
        Get configuration section or entire config

        Args:
            section: Configuration section name (None for entire config)

        Returns:
            Configuration data
        """
        if section is None:
            return self._config_data

        # Return typed config if available
        if section in self._typed_configs:
            return self._typed_configs[section]

        # Return raw config data
        return self._config_data.get(section, {})

    def get_plc_config(self) -> PLCConfig:
        """Get PLC configuration"""
        return self._typed_configs.get("plc", PLCConfig())

    def get_scanner_config(self, scanner_name: str) -> Optional[ScannerConfig]:
        """Get scanner configuration by name"""
        scanners = self._typed_configs.get("scanners", {})
        return scanners.get(scanner_name)

    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration"""
        return self._typed_configs.get("database", DatabaseConfig())

    def get_file_config(self) -> FileConfig:
        """Get file configuration"""
        return self._typed_configs.get("files", FileConfig())

    def get_production_config(self) -> ProductionConfig:
        """Get production configuration"""
        return self._typed_configs.get("production", ProductionConfig())

    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration"""
        return self._typed_configs.get("logging", LoggingConfig())

    def get_value(self, key_path: str, default=None):
        """
        Get configuration value using dot notation

        Args:
            key_path: Dot-separated key path (e.g., "plc.host")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        try:
            keys = key_path.split(".")
            value = self._config_data

            for key in keys:
                value = value[key]

            return value

        except (KeyError, TypeError):
            return default

    def set_value(self, key_path: str, value: Any):
        """
        Set configuration value using dot notation

        Args:
            key_path: Dot-separated key path
            value: Value to set
        """
        try:
            keys = key_path.split(".")
            config = self._config_data

            # Navigate to parent of target key
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]

            # Set the value
            config[keys[-1]] = value

            # Recreate typed configs
            self._create_typed_configs()

        except Exception as e:
            self.logger.error(f"Error setting configuration value: {e}")

    def validate_configuration(self) -> Dict[str, list]:
        """
        Validate configuration and return any issues

        Returns:
            Dictionary with validation issues by section
        """
        issues = {}

        # Validate PLC config
        plc_issues = []
        plc_config = self.get_plc_config()

        if not plc_config.host:
            plc_issues.append("PLC host is required")
        if plc_config.port <= 0 or plc_config.port > 65535:
            plc_issues.append("PLC port must be between 1 and 65535")
        if plc_config.timeout <= 0:
            plc_issues.append("PLC timeout must be positive")

        if plc_issues:
            issues["plc"] = plc_issues

        # Validate scanner configs
        scanners = self._typed_configs.get("scanners", {})
        for scanner_name, scanner_config in scanners.items():
            scanner_issues = []

            if not scanner_config.host:
                scanner_issues.append(f"Scanner '{scanner_name}' host is required")
            if scanner_config.port <= 0 or scanner_config.port > 65535:
                scanner_issues.append(
                    f"Scanner '{scanner_name}' port must be between 1 and 65535"
                )
            if scanner_config.timeout <= 0:
                scanner_issues.append(
                    f"Scanner '{scanner_name}' timeout must be positive"
                )

            if scanner_issues:
                issues[f"scanner_{scanner_name}"] = scanner_issues

        # Validate database config
        db_issues = []
        db_config = self.get_database_config()

        if not db_config.connection_string:
            db_issues.append("Database connection string is required")
        if not db_config.database_name:
            db_issues.append("Database name is required")
        if not db_config.collection_name:
            db_issues.append("Collection name is required")

        if db_issues:
            issues["database"] = db_issues

        # Validate file paths
        file_issues = []
        file_config = self.get_file_config()

        required_dirs = [
            os.path.dirname(file_config.code_file_path),
            os.path.dirname(file_config.barcode_file_path),
            os.path.dirname(file_config.log_file_path),
            file_config.backup_directory,
        ]

        for directory in required_dirs:
            if directory and not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                except Exception:
                    file_issues.append(f"Cannot create directory: {directory}")

        if file_issues:
            issues["files"] = file_issues

        return issues

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "system": {
                "name": "Laser Marking System",
                "version": "1.0.0",
                "description": "Industrial laser marking and scanning system",
            },
            "plc": asdict(PLCConfig()),
            "scanners": {
                "main": asdict(
                    ScannerConfig(
                        "192.168.1.100", 8080, description="Main barcode scanner"
                    )
                ),
                "middle": asdict(
                    ScannerConfig("192.168.1.101", 8080, description="Middle scanner")
                ),
                "verification": asdict(
                    ScannerConfig(
                        "192.168.1.102", 8080, description="Verification scanner"
                    )
                ),
            },
            "database": asdict(DatabaseConfig()),
            "files": asdict(FileConfig()),
            "production": asdict(ProductionConfig()),
            "timeouts": {
                "scanner_read": 30.0,
                "plc_response": 5.0,
                "database_operation": 10.0,
                "reset_check_interval": 0.1,
            },
            "logging": asdict(LoggingConfig()),
            "gui": {
                "window_title": "Laser Marking System v1.0",
                "window_size": "1200x800",
                "update_interval": 1000,
                "max_log_lines": 1000,
                "theme": "modern",
            },
            "validation": {
                "min_barcode_length": 5,
                "max_barcode_length": 50,
                "allowed_characters": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                "require_serial_uniqueness": True,
            },
            "maintenance": {
                "auto_backup_enabled": True,
                "auto_backup_interval": 86400,
                "statistics_retention_days": 30,
                "log_retention_days": 7,
            },
        }

    def export_config(self, filename: str) -> bool:
        """
        Export configuration to a file

        Args:
            filename: Output filename

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self._config_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"Failed to export configuration: {e}")
            return False

    def import_config(self, filename: str) -> bool:
        """
        Import configuration from a file

        Args:
            filename: Input filename

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(filename, "r", encoding="utf-8") as f:
                imported_config = json.load(f)

            # Validate imported config
            old_config = self._config_data
            self._config_data = imported_config
            issues = self.validate_configuration()

            if issues:
                # Restore old config if validation fails
                self._config_data = old_config
                self.logger.error(
                    f"Imported configuration has validation issues: {issues}"
                )
                return False

            # Save the imported config
            self._create_typed_configs()
            self.save_configuration()
            return True

        except Exception as e:
            self.logger.error(f"Failed to import configuration: {e}")
            return False


# Global configuration instance
config_manager = ConfigurationManager()
