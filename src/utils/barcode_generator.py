"""
Barcode Generation Utilities for Laser Marking System
Handles serial number generation, shift management, and barcode formatting
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Dict, Any, Optional, Tuple
import re
import hashlib
import json
import os
from pathlib import Path


class ShiftManager:
    """
    Manages production shifts and shift-based serial numbering
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize shift manager

        Args:
            config: Configuration dictionary with shift settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Shift configuration
        self.shift_start_hour = config.get("shift_start_hour", 6)
        self.shift_duration_hours = config.get("shift_duration_hours", 8)

        # Calculate shift boundaries
        self._calculate_shift_boundaries()

    def _calculate_shift_boundaries(self):
        """Calculate shift time boundaries"""
        # Shift 1: 06:00 - 14:00
        # Shift 2: 14:00 - 22:00
        # Shift 3: 22:00 - 06:00 (next day)

        self.shifts = {
            1: {"start": time(6, 0), "end": time(14, 0), "name": "Day Shift"},
            2: {"start": time(14, 0), "end": time(22, 0), "name": "Evening Shift"},
            3: {
                "start": time(22, 0),
                "end": time(6, 0),  # Next day
                "name": "Night Shift",
            },
        }

    def get_current_shift(
        self, current_time: Optional[datetime] = None
    ) -> Tuple[int, str]:
        """
        Get current shift number and name

        Args:
            current_time: Time to check (default: now)

        Returns:
            Tuple of (shift_number, shift_name)
        """
        if current_time is None:
            current_time = datetime.now()

        current_time_only = current_time.time()

        # Check each shift
        for shift_num, shift_info in self.shifts.items():
            start_time = shift_info["start"]
            end_time = shift_info["end"]

            if shift_num == 3:  # Night shift crosses midnight
                if current_time_only >= start_time or current_time_only < end_time:
                    return shift_num, shift_info["name"]
            else:
                if start_time <= current_time_only < end_time:
                    return shift_num, shift_info["name"]

        # Default to shift 1 if no match
        return 1, self.shifts[1]["name"]

    def get_shift_date_key(self, current_time: Optional[datetime] = None) -> str:
        """
        Get date key for shift-based numbering
        For night shift, use the date when the shift started

        Args:
            current_time: Time to check (default: now)

        Returns:
            Date key in YYYYMMDD format
        """
        if current_time is None:
            current_time = datetime.now()

        shift_num, _ = self.get_current_shift(current_time)

        if shift_num == 3:  # Night shift
            # If it's before 6 AM, use previous day's date
            if current_time.time() < time(6, 0):
                shift_date = current_time.date() - datetime.timedelta(days=1)
            else:
                shift_date = current_time.date()
        else:
            shift_date = current_time.date()

        return shift_date.strftime("%Y%m%d")


class SerialNumberGenerator:
    """
    Generates unique serial numbers with configurable formats
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize serial number generator

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Serial number configuration
        self.format_template = config.get(
            "serial_number_format", "YYYYMMDD{shift}{counter:04d}"
        )
        self.counter_file = config.get(
            "counter_file_path", "./data/serial_counter.json"
        )

        # Shift manager
        self.shift_manager = ShiftManager(config)

        # Load/initialize counters
        self.counters = self._load_counters()

    def _load_counters(self) -> Dict[str, int]:
        """Load serial number counters from file"""
        try:
            if os.path.exists(self.counter_file):
                with open(self.counter_file, "r") as f:
                    return json.load(f)
            else:
                return {}
        except Exception as e:
            self.logger.error(f"Error loading counters: {e}")
            return {}

    def _save_counters(self):
        """Save serial number counters to file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.counter_file), exist_ok=True)

            with open(self.counter_file, "w") as f:
                json.dump(self.counters, f, indent=2)

        except Exception as e:
            self.logger.error(f"Error saving counters: {e}")

    def _get_counter_key(self, date_key: str, shift: int) -> str:
        """Get counter key for date and shift"""
        return f"{date_key}_shift_{shift}"

    def _get_next_counter(self, counter_key: str) -> int:
        """Get and increment counter for given key"""
        if counter_key not in self.counters:
            self.counters[counter_key] = 0

        self.counters[counter_key] += 1
        counter_value = self.counters[counter_key]

        # Save counters after increment
        self._save_counters()

        return counter_value

    def generate_serial_number(self, current_time: Optional[datetime] = None) -> str:
        """
        Generate a unique serial number

        Args:
            current_time: Time to use for generation (default: now)

        Returns:
            Generated serial number
        """
        if current_time is None:
            current_time = datetime.now()

        # Get shift information
        shift_num, shift_name = self.shift_manager.get_current_shift(current_time)
        date_key = self.shift_manager.get_shift_date_key(current_time)

        # Get counter
        counter_key = self._get_counter_key(date_key, shift_num)
        counter_value = self._get_next_counter(counter_key)

        # Format serial number
        serial_number = self._format_serial_number(
            date_key, shift_num, counter_value, current_time
        )

        self.logger.info(
            f"Generated serial number: {serial_number} "
            f"(Date: {date_key}, Shift: {shift_num}, Counter: {counter_value})"
        )

        return serial_number

    def _format_serial_number(
        self, date_key: str, shift: int, counter: int, current_time: datetime
    ) -> str:
        """
        Format serial number according to template

        Args:
            date_key: Date key (YYYYMMDD)
            shift: Shift number
            counter: Counter value
            current_time: Current time

        Returns:
            Formatted serial number
        """
        # Replace date placeholders
        formatted = self.format_template.replace("YYYYMMDD", date_key)
        formatted = formatted.replace("YYYY", current_time.strftime("%Y"))
        formatted = formatted.replace("MM", current_time.strftime("%m"))
        formatted = formatted.replace("DD", current_time.strftime("%d"))

        # Replace shift and counter placeholders using format
        formatted = formatted.format(shift=shift, counter=counter)

        return formatted

    def validate_serial_number(self, serial_number: str) -> bool:
        """
        Validate serial number format

        Args:
            serial_number: Serial number to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Basic length and character validation
            min_length = self.config.get("min_barcode_length", 5)
            max_length = self.config.get("max_barcode_length", 50)
            allowed_chars = self.config.get(
                "allowed_characters", "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            )

            if not (min_length <= len(serial_number) <= max_length):
                return False

            if not all(c in allowed_chars for c in serial_number):
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating serial number: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get serial number generation statistics"""
        current_time = datetime.now()
        shift_num, shift_name = self.shift_manager.get_current_shift(current_time)
        date_key = self.shift_manager.get_shift_date_key(current_time)
        counter_key = self._get_counter_key(date_key, shift_num)

        return {
            "current_shift": shift_num,
            "current_shift_name": shift_name,
            "current_date_key": date_key,
            "current_shift_counter": self.counters.get(counter_key, 0),
            "total_counters": len(self.counters),
            "counters": self.counters.copy(),
        }


class BarcodeGenerator:
    """
    Main barcode generation class combining serial numbers with part information
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize barcode generator

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize serial number generator
        self.serial_generator = SerialNumberGenerator(config)

        # Part/model configuration
        self.model_number = config.get("model_number", "MODEL123")

    async def generate_barcode(
        self, part_number: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate barcode data with serial number

        Args:
            part_number: Part number to use (default: from config)

        Returns:
            Dictionary with barcode text and serial number
        """
        try:
            if part_number is None:
                part_number = self.model_number

            # Generate serial number
            serial_number = self.serial_generator.generate_serial_number()

            # Create barcode text (combine part number and serial)
            barcode_text = f"{part_number}{serial_number}"

            # Validate the generated barcode
            if not self.validate_barcode(barcode_text):
                raise ValueError(f"Generated barcode failed validation: {barcode_text}")

            self.logger.info(f"Generated barcode: {barcode_text}")

            return {
                "text": barcode_text,
                "serialNo": serial_number,
                "partNumber": part_number,
                "timestamp": datetime.now().isoformat(),
                "shift": self.serial_generator.shift_manager.get_current_shift()[0],
            }

        except Exception as e:
            self.logger.error(f"Error generating barcode: {e}")
            return None

    def validate_barcode(self, barcode_text: str) -> bool:
        """
        Validate complete barcode

        Args:
            barcode_text: Barcode text to validate

        Returns:
            True if valid, False otherwise
        """
        return self.serial_generator.validate_serial_number(barcode_text)

    def get_barcode_info(self, barcode_text: str) -> Optional[Dict[str, str]]:
        """
        Extract information from barcode text

        Args:
            barcode_text: Barcode text to analyze

        Returns:
            Dictionary with extracted information or None
        """
        try:
            # Try to extract part number and serial number
            # This assumes part number is the model number prefix
            if barcode_text.startswith(self.model_number):
                part_number = self.model_number
                serial_number = barcode_text[len(self.model_number) :]

                return {
                    "barcode_text": barcode_text,
                    "part_number": part_number,
                    "serial_number": serial_number,
                    "is_valid": self.validate_barcode(barcode_text),
                }

            return None

        except Exception as e:
            self.logger.error(f"Error extracting barcode info: {e}")
            return None

    def generate_checksum(self, data: str) -> str:
        """
        Generate checksum for data integrity verification

        Args:
            data: Data to generate checksum for

        Returns:
            Checksum string
        """
        return hashlib.md5(data.encode()).hexdigest()[:8].upper()

    def verify_checksum(self, data: str, checksum: str) -> bool:
        """
        Verify data against checksum

        Args:
            data: Original data
            checksum: Checksum to verify against

        Returns:
            True if valid, False otherwise
        """
        return self.generate_checksum(data) == checksum.upper()

    def get_statistics(self) -> Dict[str, Any]:
        """Get barcode generation statistics"""
        serial_stats = self.serial_generator.get_statistics()

        return {
            "model_number": self.model_number,
            "serial_generator": serial_stats,
            "validation_config": {
                "min_length": self.config.get("min_barcode_length", 5),
                "max_length": self.config.get("max_barcode_length", 50),
                "allowed_characters": self.config.get(
                    "allowed_characters", "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
                ),
            },
        }


class BarcodeFileManager:
    """
    Manages barcode data file operations
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize file manager

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # File paths
        self.barcode_file_path = config.get("barcode_file_path", "./data/barcode.txt")
        self.code_file_path = config.get("code_file_path", "./data/code.txt")

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure required directories exist"""
        for file_path in [self.barcode_file_path, self.code_file_path]:
            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)

    async def write_barcode_to_file(self, barcode_data: str) -> bool:
        """
        Write barcode data to file for laser system

        Args:
            barcode_data: Barcode data to write

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.barcode_file_path, "w", encoding="utf-8") as f:
                f.write(barcode_data)

            self.logger.info(f"Wrote barcode data to file: {barcode_data}")
            return True

        except Exception as e:
            self.logger.error(f"Error writing barcode to file: {e}")
            return False

    async def write_code_to_file(self, code_data: str) -> bool:
        """
        Write code data to file

        Args:
            code_data: Code data to write

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.code_file_path, "w", encoding="utf-8") as f:
                f.write(code_data)

            self.logger.info(f"Wrote code data to file: {code_data}")
            return True

        except Exception as e:
            self.logger.error(f"Error writing code to file: {e}")
            return False

    async def read_code_from_file(self) -> Optional[str]:
        """
        Read code data from file

        Returns:
            Code data or None if error
        """
        try:
            if os.path.exists(self.code_file_path):
                with open(self.code_file_path, "r", encoding="utf-8") as f:
                    code_data = f.read().strip()
                return code_data
            else:
                return None

        except Exception as e:
            self.logger.error(f"Error reading code from file: {e}")
            return None

    async def clear_files(self):
        """Clear all barcode and code files"""
        try:
            # Clear barcode file
            with open(self.barcode_file_path, "w", encoding="utf-8") as f:
                f.write("")

            # Clear code file
            with open(self.code_file_path, "w", encoding="utf-8") as f:
                f.write("")

            self.logger.info("Cleared barcode and code files")

        except Exception as e:
            self.logger.error(f"Error clearing files: {e}")

    def get_file_status(self) -> Dict[str, Any]:
        """Get status of barcode files"""
        status = {}

        for name, path in [
            ("barcode", self.barcode_file_path),
            ("code", self.code_file_path),
        ]:
            try:
                if os.path.exists(path):
                    stat = os.stat(path)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()

                    status[name] = {
                        "exists": True,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "content_length": len(content),
                        "has_content": len(content.strip()) > 0,
                    }
                else:
                    status[name] = {
                        "exists": False,
                        "size": 0,
                        "modified": None,
                        "content_length": 0,
                        "has_content": False,
                    }

            except Exception as e:
                self.logger.error(f"Error getting status for {name} file: {e}")
                status[name] = {"error": str(e)}

        return status
