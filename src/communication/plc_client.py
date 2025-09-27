"""
PLC Communication Module for Laser Marking System
Handles Modbus TCP communication with PLC for control and status operations
"""

import asyncio
import logging
from typing import Optional, List, Union
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
import struct


class PLCClient:
    """
    PLC Communication client using Modbus TCP protocol
    Manages all register read/write operations for the laser marking system
    """

    def __init__(
        self,
        host: str = "192.168.3.146",
        port: int = 502,
        timeout: int = 5,
        retries: int = 3,
    ):
        """
        Initialize PLC client

        Args:
            host: PLC IP address
            port: Modbus TCP port
            timeout: Connection timeout in seconds
            retries: Number of retry attempts
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries
        self.client = None
        self.logger = logging.getLogger(__name__)
        self.is_connected = False
        # Add semaphore to prevent concurrent operations
        self._operation_semaphore = asyncio.Semaphore(1)
        self._connection_lock = asyncio.Lock()

    async def connect(self) -> bool:
        """
        Establish connection to PLC

        Returns:
            bool: True if connection successful, False otherwise
        """
        async with self._connection_lock:
            try:
                # If already connected, close the existing connection first
                if self.client and self.is_connected:
                    await self.disconnect()
                    
                self.client = AsyncModbusTcpClient(
                    host=self.host, port=self.port, timeout=self.timeout
                )
                result = await self.client.connect()
                self.is_connected = result

                if self.is_connected:
                    self.logger.info(f"Connected to PLC at {self.host}:{self.port}")
                else:
                    self.logger.error(
                        f"Failed to connect to PLC at {self.host}:{self.port}"
                    )

                return self.is_connected

            except Exception as e:
                self.logger.error(f"PLC connection error: {e}")
                self.is_connected = False
                return False

    async def disconnect(self):
        """Disconnect from PLC"""
        async with self._connection_lock:
            if self.client and self.is_connected:
                try:
                    await self.client.close()
                except Exception as e:
                    self.logger.warning(f"Error during disconnect: {e}")
                finally:
                    self.is_connected = False
                    self.client = None
                    self.logger.info("Disconnected from PLC")

    async def reconnect(self) -> bool:
        """Force reconnection to PLC"""
        await self.disconnect()
        return await self.connect()

    async def _ensure_connection(self) -> bool:
        """Ensure PLC connection is active with connection health check"""
        # First check if we think we're connected (without lock to avoid deadlock)
        if not self.is_connected or not self.client:
            self.logger.debug("Connection not established, attempting to connect")
            return await self.connect()
        
        # Check if connection is actually healthy by attempting a simple read
        try:
            # Try to read a status register to verify connection health
            test_result = await asyncio.wait_for(
                self.client.read_holding_registers(address=1600, count=1),
                timeout=1.0
            )
            if test_result.isError():
                self.logger.warning("Connection health check failed, reconnecting")
                self.is_connected = False
                return await self.connect()
                
            return True
            
        except Exception as e:
            self.logger.warning(f"Connection health check error: {e}, reconnecting")
            self.is_connected = False
            return await self.connect()

    async def read_bit(self, register: int, bit: int) -> Optional[bool]:
        """
        Read a single bit from PLC register

        Args:
            register: Register address
            bit: Bit position (0-15)

        Returns:
            bool: Bit value or None if error
        """
        # Remove semaphore for read operations to prevent deadlock
        self.logger.info(f"🔍 read_bit called for {register}.{bit}")
        
        if not await self._ensure_connection():
            self.logger.error(f"❌ _ensure_connection failed for {register}.{bit}")
            return None
        
        self.logger.info(f"🔍 Connection ensured, starting read attempts for {register}.{bit}")

        for attempt in range(self.retries):
            try:
                self.logger.info(f"🔍 Attempt {attempt + 1} reading register {register}")
                # Read holding register with timeout
                result = await asyncio.wait_for(
                    self.client.read_holding_registers(address=register, count=1),
                    timeout=self.timeout
                )

                if result.isError():
                    self.logger.error(f"Error reading register {register}: {result}")
                    continue

                register_value = result.registers[0]
                bit_value = bool(register_value & (1 << bit))

                self.logger.info(f"✅ Successfully read bit {register}.{bit}: {bit_value}")
                return bit_value

            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout reading bit {register}.{bit}")
                # Mark connection as unhealthy and try to reconnect
                self.is_connected = False
                continue
            except Exception as e:
                self.logger.error(
                    f"Attempt {attempt + 1} failed reading bit {register}.{bit}: {e}"
                )
                if attempt < self.retries - 1:
                    await asyncio.sleep(0.1)  # Reduced delay for better performance

        self.logger.error(f"❌ All attempts failed for {register}.{bit}")
        return None

    async def write_bit(self, register: int, bit: int, value: bool) -> bool:
        """
        Write a single bit to PLC register

        Args:
            register: Register address
            bit: Bit position (0-15)
            value: Bit value to write

        Returns:
            bool: True if successful, False otherwise
        """
        async with self._operation_semaphore:
            if not await self._ensure_connection():
                return False

            for attempt in range(self.retries):
                try:
                    # First read the current register value with timeout
                    read_result = await asyncio.wait_for(
                        self.client.read_holding_registers(address=register, count=1),
                        timeout=self.timeout
                    )

                    if read_result.isError():
                        self.logger.error(
                            f"Error reading register {register} for bit write: {read_result}"
                        )
                        continue

                    current_value = read_result.registers[0]

                    # Modify the specific bit
                    if value:
                        new_value = current_value | (1 << bit)
                    else:
                        new_value = current_value & ~(1 << bit)

                    # Write back the modified value with timeout
                    write_result = await asyncio.wait_for(
                        self.client.write_register(address=register, value=new_value),
                        timeout=self.timeout
                    )

                    if write_result.isError():
                        self.logger.error(
                            f"Error writing register {register}: {write_result}"
                        )
                        continue

                    self.logger.debug(f"Wrote bit {register}.{bit}: {value}")
                    return True

                except asyncio.TimeoutError:
                    self.logger.warning(f"Timeout writing bit {register}.{bit}")
                    # Mark connection as unhealthy and try to reconnect
                    self.is_connected = False
                    continue
                except Exception as e:
                    self.logger.error(
                        f"Attempt {attempt + 1} failed writing bit {register}.{bit}: {e}"
                    )
                    if attempt < self.retries - 1:
                        await asyncio.sleep(0.1)  # Reduced delay for better performance

            return False

    async def read_ascii_data(
        self, start_register: int, length: int = 20
    ) -> Optional[str]:
        """
        Read ASCII data from consecutive registers

        Args:
            start_register: Starting register address
            length: Number of registers to read

        Returns:
            str: ASCII string or None if error
        """
        async with self._operation_semaphore:
            if not await self._ensure_connection():
                return None

            for attempt in range(self.retries):
                try:
                    result = await self.client.read_holding_registers(
                        address=start_register, count=length
                    )

                    if result.isError():
                        self.logger.error(
                            f"Error reading ASCII data from register {start_register}: {result}"
                        )
                    continue

                    # Convert registers to ASCII string
                    ascii_bytes = []
                    for register_value in result.registers:
                        # Each register contains 2 bytes (16 bits)
                        high_byte = (register_value >> 8) & 0xFF
                        low_byte = register_value & 0xFF
                        ascii_bytes.extend([high_byte, low_byte])

                    # Convert bytes to string and remove null characters
                    ascii_string = (
                        bytes(ascii_bytes).decode("ascii", errors="ignore").rstrip("\x00")
                    )

                    self.logger.debug(
                        f"Read ASCII data from register {start_register}: '{ascii_string}'"
                    )
                    return ascii_string

                except Exception as e:
                    self.logger.error(
                        f"Attempt {attempt + 1} failed reading ASCII data from register {start_register}: {e}"
                    )
                    if attempt < self.retries - 1:
                        await asyncio.sleep(0.1)

            return None

    async def write_ascii_data(
        self, start_register: int, data: str, length: int = 20
    ) -> bool:
        """
        Write ASCII data to consecutive registers

        Args:
            start_register: Starting register address
            data: ASCII string to write
            length: Number of registers to write

        Returns:
            bool: True if successful, False otherwise
        """
        async with self._operation_semaphore:
            if not await self._ensure_connection():
                return False

            # Pad or truncate data to fit in specified registers
            padded_data = data.ljust(length * 2, "\x00")[: length * 2]

            # Convert string to register values
            register_values = []
            for i in range(0, len(padded_data), 2):
                high_byte = ord(padded_data[i]) if i < len(padded_data) else 0
                low_byte = ord(padded_data[i + 1]) if i + 1 < len(padded_data) else 0
                register_value = (high_byte << 8) | low_byte
                register_values.append(register_value)

            for attempt in range(self.retries):
                try:
                    result = await self.client.write_registers(
                        address=start_register, values=register_values
                    )

                    if result.isError():
                        self.logger.error(
                            f"Error writing ASCII data to register {start_register}: {result}"
                        )
                        continue

                    self.logger.debug(
                        f"Wrote ASCII data to register {start_register}: '{data}'"
                    )
                    return True

                except Exception as e:
                    self.logger.error(
                        f"Attempt {attempt + 1} failed writing ASCII data to register {start_register}: {e}"
                    )
                    if attempt < self.retries - 1:
                        await asyncio.sleep(0.1)

            return False

    async def check_reset_or_bit(
        self, register: int, bit: int, expected_value: int, timeout: float = None
    ) -> str:
        """
        Wait for a specific bit to reach expected value or detect reset signal

        Args:
            register: Register to monitor
            bit: Bit position to monitor
            expected_value: Expected bit value (0 or 1)
            timeout: Maximum wait time in seconds

        Returns:
            str: "OK" if bit reached expected value, "RESET" if reset detected, "TIMEOUT" if timeout
        """
        start_time = asyncio.get_event_loop().time()
        
        # Use a single semaphore acquisition for the entire check to avoid deadlocks
        async with self._operation_semaphore:
            while True:
                if not await self._ensure_connection():
                    self.logger.error("Failed to ensure PLC connection")
                    return "TIMEOUT"

                try:
                    # Check reset signal first
                    reset_result = await asyncio.wait_for(
                        self.client.read_holding_registers(address=1600, count=1),
                        timeout=self.timeout
                    )
                    if not reset_result.isError():
                        reset_value = reset_result.registers[0]
                        if reset_value & 1:  # Check bit 0
                            self.logger.warning("Reset signal detected")
                            return "RESET"

                    # Check target bit
                    bit_result = await asyncio.wait_for(
                        self.client.read_holding_registers(address=register, count=1),
                        timeout=self.timeout
                    )
                    if not bit_result.isError():
                        register_value = bit_result.registers[0]
                        bit_value = bool(register_value & (1 << bit))
                        
                        self.logger.info(f"🔍 Checking bit {register}.{bit}: read={bit_value}, expected={bool(expected_value)}")
                        
                        if bit_value == bool(expected_value):
                            self.logger.info(f"✅ Bit {register}.{bit} reached expected value: {expected_value}")
                            return "OK"

                    # Check timeout
                    if timeout and (asyncio.get_event_loop().time() - start_time) > timeout:
                        self.logger.warning(
                            f"Timeout waiting for bit {register}.{bit} = {expected_value}"
                        )
                        return "TIMEOUT"

                    await asyncio.sleep(0.1)  # 100ms polling interval
                    
                except Exception as e:
                    self.logger.error(f"Error in check_reset_or_bit: {e}")
                    return "TIMEOUT"

    async def reset_all_bits(self):
        """Reset all control and status bits to 0"""
        reset_registers = [
            (1414, [3, 4, 6, 7, 15]),  # Status bits
            (1415, [0]),  # First scanner trigger
            (1416, [15]),  # Verification scanner trigger
            (1418, [0]),  # Middle scanner trigger
        ]

        for register, bits in reset_registers:
            for bit in bits:
                await self.write_bit(register, bit, False)

        self.logger.info("Reset all PLC bits")


class PLCRegisterMap:
    """PLC Register mapping constants"""

    # Control Registers (Read)
    START_SIGNAL = (1410, 0)
    OCR_READ_TRIGGER = (1410, 1)
    LASER_DATA_TRANSFER = (1410, 2)
    SCANNER_READ_TRIGGER = (1410, 3)
    FILE_TRANSFER_SIGNAL = (1410, 11)
    CYCLE_COMPLETION = (1410, 12)

    # Status Registers (Write)
    DATA_MATCH_OK = (1414, 3)
    DATA_MATCH_NG = (1414, 4)
    FIRST_SCAN_OK = (1414, 6)
    FIRST_SCAN_NG = (1414, 7)
    OCR_READ_CONFIRMATION = (1414, 15)

    # Scanner Triggers (Write)
    FIRST_SCANNER_TRIGGER = (1415, 0)
    VERIFICATION_SCANNER_TRIGGER = (1416, 15)
    MIDDLE_SCANNER_TRIGGER = (1418, 0)

    # Data Registers
    OCR_DATA_START = 1450
    SCANNER_DATA_START = 1470

    # Reset Signal
    RESET_SIGNAL = (1600, 0)
