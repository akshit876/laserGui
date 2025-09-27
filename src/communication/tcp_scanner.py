"""
TCP Scanner Communication Module for Laser Marking System
Handles TCP socket communication with multiple scanner types
"""

import asyncio
import logging
import socket
from typing import Optional, Dict, Any
from enum import Enum


class ScannerType(Enum):
    """Scanner type enumeration"""

    MAIN = "main"
    MIDDLE = "middle"
    VERIFICATION = "verification"


class TCPScannerClient:
    """
    TCP Scanner communication client
    Manages connections and data exchange with barcode scanners
    """

    def __init__(self, scanner_configs: Dict[str, Dict[str, Any]]):
        """
        Initialize TCP Scanner client

        Args:
            scanner_configs: Dictionary of scanner configurations
        """
        self.configs = scanner_configs
        self.logger = logging.getLogger(__name__)
        self.connections = {}
        self.active_readers = {}

    async def connect_scanner(self, scanner_type: ScannerType) -> bool:
        """
        Establish connection to a specific scanner

        Args:
            scanner_type: Type of scanner to connect

        Returns:
            bool: True if connection successful, False otherwise
        """
        config = self.configs.get(scanner_type.value)
        if not config:
            self.logger.error(
                f"No configuration found for scanner type: {scanner_type.value}"
            )
            return False

        try:
            # Create TCP connection
            reader, writer = await asyncio.open_connection(
                config["host"], config["port"]
            )

            self.connections[scanner_type] = {
                "reader": reader,
                "writer": writer,
                "config": config,
            }

            self.logger.info(
                f"Connected to {scanner_type.value} scanner at {config['host']}:{config['port']}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to {scanner_type.value} scanner: {e}")
            return False

    async def disconnect_scanner(self, scanner_type: ScannerType):
        """
        Disconnect from a specific scanner

        Args:
            scanner_type: Type of scanner to disconnect
        """
        if scanner_type in self.connections:
            try:
                writer = self.connections[scanner_type]["writer"]
                writer.close()
                await writer.wait_closed()
                del self.connections[scanner_type]
                self.logger.info(f"Disconnected from {scanner_type.value} scanner")
            except Exception as e:
                self.logger.error(
                    f"Error disconnecting from {scanner_type.value} scanner: {e}"
                )

    async def disconnect_all(self):
        """Disconnect from all scanners"""
        for scanner_type in list(self.connections.keys()):
            await self.disconnect_scanner(scanner_type)

    async def read_scanner_data(
        self, scanner_type: ScannerType, timeout: float = 30.0
    ) -> str:
        """
        Read data from a specific scanner with timeout

        Args:
            scanner_type: Type of scanner to read from
            timeout: Timeout in seconds

        Returns:
            str: Scanner data or "NG" if timeout/error
        """
        if scanner_type not in self.connections:
            if not await self.connect_scanner(scanner_type):
                return "NG"

        connection = self.connections[scanner_type]
        reader = connection["reader"]

        try:
            # Read data with timeout
            data = await asyncio.wait_for(reader.readline(), timeout=timeout)

            result = data.decode("utf-8", errors="ignore").strip()
            self.logger.info(
                f"Received data from {scanner_type.value} scanner: '{result}'"
            )

            # Validate data (non-empty and reasonable length)
            if result and len(result) > 0:
                return result
            else:
                self.logger.warning(
                    f"Empty data received from {scanner_type.value} scanner"
                )
                return "NG"

        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout reading from {scanner_type.value} scanner")
            return "NG"

        except Exception as e:
            self.logger.error(f"Error reading from {scanner_type.value} scanner: {e}")
            # Try to reconnect for next time
            await self.disconnect_scanner(scanner_type)
            return "NG"

    async def send_command(self, scanner_type: ScannerType, command: str) -> bool:
        """
        Send command to a specific scanner

        Args:
            scanner_type: Type of scanner to send command to
            command: Command string to send

        Returns:
            bool: True if successful, False otherwise
        """
        if scanner_type not in self.connections:
            if not await self.connect_scanner(scanner_type):
                return False

        connection = self.connections[scanner_type]
        writer = connection["writer"]

        try:
            writer.write(command.encode("utf-8") + b"\n")
            await writer.drain()

            self.logger.debug(
                f"Sent command to {scanner_type.value} scanner: '{command}'"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"Error sending command to {scanner_type.value} scanner: {e}"
            )
            # Try to reconnect for next time
            await self.disconnect_scanner(scanner_type)
            return False

    async def trigger_scan(
        self, scanner_type: ScannerType, timeout: float = 30.0
    ) -> str:
        """
        Trigger a scan operation and wait for result

        Args:
            scanner_type: Type of scanner to trigger
            timeout: Timeout in seconds

        Returns:
            str: Scanner data or "NG" if timeout/error
        """
        # Send trigger command (if required by scanner)
        trigger_command = self.configs.get(scanner_type.value, {}).get(
            "trigger_command"
        )
        if trigger_command:
            success = await self.send_command(scanner_type, trigger_command)
            if not success:
                return "NG"

        # Read the scan result
        return await self.read_scanner_data(scanner_type, timeout)

    async def test_connection(self, scanner_type: ScannerType) -> bool:
        """
        Test connection to a specific scanner

        Args:
            scanner_type: Type of scanner to test

        Returns:
            bool: True if connection is working, False otherwise
        """
        try:
            config = self.configs.get(scanner_type.value)
            if not config:
                return False

            # Create a simple socket connection test
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)

            result = sock.connect_ex((config["host"], config["port"]))
            sock.close()

            is_connected = result == 0

            if is_connected:
                self.logger.debug(
                    f"Connection test successful for {scanner_type.value} scanner"
                )
            else:
                self.logger.warning(
                    f"Connection test failed for {scanner_type.value} scanner"
                )

            return is_connected

        except Exception as e:
            self.logger.error(
                f"Connection test error for {scanner_type.value} scanner: {e}"
            )
            return False

    def get_scanner_status(self, scanner_type: ScannerType) -> Dict[str, Any]:
        """
        Get status information for a specific scanner

        Args:
            scanner_type: Type of scanner to check

        Returns:
            dict: Status information
        """
        is_connected = scanner_type in self.connections
        config = self.configs.get(scanner_type.value, {})

        return {
            "type": scanner_type.value,
            "connected": is_connected,
            "host": config.get("host", "Unknown"),
            "port": config.get("port", "Unknown"),
            "timeout": config.get("timeout", 30),
        }

    def get_all_scanner_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status information for all scanners

        Returns:
            dict: Status information for all scanners
        """
        status = {}
        for scanner_type in ScannerType:
            status[scanner_type.value] = self.get_scanner_status(scanner_type)
        return status


class ScannerService:
    """
    High-level scanner service that manages PLC integration
    """

    def __init__(self, plc_client, scanner_client: TCPScannerClient):
        """
        Initialize Scanner Service

        Args:
            plc_client: PLC client instance
            scanner_client: TCP scanner client instance
        """
        self.plc = plc_client
        self.scanner_client = scanner_client
        self.logger = logging.getLogger(__name__)

    async def fetch_scanner_data(
        self,
        scanner_type: ScannerType,
        plc_trigger_register: int,
        plc_trigger_bit: int,
        timeout: float = 30.0,
    ) -> str:
        """
        Fetch scanner data with PLC trigger integration

        Args:
            scanner_type: Type of scanner
            plc_trigger_register: PLC register for trigger
            plc_trigger_bit: PLC bit for trigger
            timeout: Timeout in seconds

        Returns:
            str: Scanner data or "NG"/"RESET"
        """
        try:
            # Set up data reading task
            read_task = asyncio.create_task(
                self.scanner_client.read_scanner_data(scanner_type, timeout)
            )

            # Set up reset monitoring task
            reset_task = asyncio.create_task(self._monitor_reset())

            # Trigger scanner via PLC
            trigger_success = await self.plc.write_bit(
                plc_trigger_register, plc_trigger_bit, True
            )
            if not trigger_success:
                read_task.cancel()
                reset_task.cancel()
                return "NG"

            # Wait for either data or reset
            done, pending = await asyncio.wait(
                [read_task, reset_task], return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel remaining tasks
            for task in pending:
                task.cancel()

            # Check results
            for task in done:
                result = await task
                if result == "RESET":
                    return "RESET"
                elif result != "NG":
                    # Clear the trigger bit
                    await self.plc.write_bit(
                        plc_trigger_register, plc_trigger_bit, False
                    )
                    return result

            # If we get here, it was a timeout or error
            await self.plc.write_bit(plc_trigger_register, plc_trigger_bit, False)
            return "NG"

        except Exception as e:
            self.logger.error(f"Error fetching scanner data: {e}")
            return "NG"

    async def _monitor_reset(self) -> str:
        """
        Monitor for reset signal

        Returns:
            str: "RESET" when reset detected
        """
        while True:
            reset_signal = await self.plc.read_bit(1600, 0)
            if reset_signal:
                return "RESET"
            await asyncio.sleep(0.1)


# Default scanner configuration
DEFAULT_SCANNER_CONFIGS = {
    "main": {
        "host": "192.168.1.100",
        "port": 8080,
        "timeout": 30,
        "trigger_command": None,  # Some scanners need a trigger command
    },
    "middle": {
        "host": "192.168.1.101",
        "port": 8080,
        "timeout": 30,
        "trigger_command": None,
    },
    "verification": {
        "host": "192.168.1.102",
        "port": 8080,
        "timeout": 30,
        "trigger_command": None,
    },
}
