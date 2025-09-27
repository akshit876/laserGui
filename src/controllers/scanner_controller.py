"""
Scanner Controller for Laser Marking System
Main controller implementing the continuous scan cycle logic
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, Tuple
from enum import Enum
from datetime import datetime, timezone

from ..communication.plc_client import PLCClient, PLCRegisterMap
from ..communication.tcp_scanner import TCPScannerClient, ScannerType, ScannerService
from ..database.mongodb_client import DatabaseClient, ScanRecord


class CycleState(Enum):
    """Scanner cycle states"""

    WAITING = "waiting"
    FIRST_SCAN = "first_scan"
    BARCODE_GEN = "barcode_gen"
    MIDDLE_SCAN = "middle_scan"
    VERIFICATION = "verification"
    FINAL_CHECK = "final_check"
    COMPLETE = "complete"
    ERROR = "error"
    RESET = "reset"


class ScanResult:
    """Result container for scan operations"""

    def __init__(self, should_continue: bool = True, data: str = "", error: str = ""):
        self.should_continue = should_continue
        self.data = data
        self.error = error


class ScannerController:
    """
    Main Scanner Controller implementing the continuous scan cycle
    """

    def __init__(
        self,
        plc_client: PLCClient,
        scanner_client: TCPScannerClient,
        database_client: DatabaseClient,
        config: Dict[str, Any],
    ):
        """
        Initialize Scanner Controller

        Args:
            plc_client: PLC communication client
            scanner_client: TCP scanner client
            database_client: Database client
            config: Configuration dictionary
        """
        self.plc = plc_client
        self.scanner_client = scanner_client
        self.database = database_client
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Scanner service for PLC integration
        self.scanner_service = ScannerService(self.plc, self.scanner_client)

        # Control flags
        self.is_running = False
        self.is_paused = False
        self.current_state = CycleState.WAITING
        self.current_record = None
        self.cycle_start_time = 0

        # Statistics
        self.stats = {
            "cycles_completed": 0,
            "cycles_failed": 0,
            "ok_results": 0,
            "ng_results": 0,
            "reset_count": 0,
            "uptime_start": time.time(),
        }

        # Event callbacks for GUI updates
        self.state_change_callback = None
        self.data_update_callback = None
        self.error_callback = None

    def set_callbacks(self, state_change_cb=None, data_update_cb=None, error_cb=None):
        """Set callback functions for GUI updates"""
        self.state_change_callback = state_change_cb
        self.data_update_callback = data_update_cb
        self.error_callback = error_cb

    def _notify_state_change(self, new_state: CycleState):
        """Notify GUI of state change"""
        self.current_state = new_state
        if self.state_change_callback:
            self.state_change_callback(new_state)

    def _notify_data_update(self, data: Dict[str, Any]):
        """Notify GUI of data update"""
        if self.data_update_callback:
            self.data_update_callback(data)

    def _notify_error(self, error: str):
        """Notify GUI of error"""
        if self.error_callback:
            self.error_callback(error)

    async def start_continuous_scan(self):
        """Start the continuous scan cycle"""
        if self.is_running:
            self.logger.warning("Scanner already running")
            return

        self.is_running = True
        self.stats["uptime_start"] = time.time()
        self.logger.info("Starting continuous scan cycle")

        try:
            await self.run_continuous_scan()
        except Exception as e:
            self.logger.error(f"Fatal error in continuous scan: {e}")
            self._notify_error(f"Fatal error: {e}")
        finally:
            self.is_running = False
            self._notify_state_change(CycleState.WAITING)

    async def stop_continuous_scan(self):
        """Stop the continuous scan cycle"""
        self.is_running = False
        self.logger.info("Stopping continuous scan cycle")

    async def pause_scan(self):
        """Pause the scan cycle"""
        self.is_paused = True
        self.logger.info("Pausing scan cycle")

    async def resume_scan(self):
        """Resume the scan cycle"""
        self.is_paused = False
        self.logger.info("Resuming scan cycle")

    async def run_continuous_scan(self):
        """Main continuous scan loop"""
        while self.is_running:
            try:
                # Check for pause
                while self.is_paused and self.is_running:
                    await asyncio.sleep(0.5)

                if not self.is_running:
                    break

                self.cycle_start_time = time.time()

                # Phase 1: Check start signal (since PLC hardware is connected)
                self._notify_state_change(CycleState.WAITING)
                self.logger.info("Checking START_SIGNAL from PLC (1410.0)...")
                
                # Add debug info before the read_bit call
                self.logger.info("🔍 About to call plc.read_bit...")
                
                try:
                    # Direct read of START_SIGNAL since we know PLC is connected
                    start_signal = await self.plc.read_bit(*PLCRegisterMap.START_SIGNAL)
                    self.logger.info(f"✅ Successfully read START_SIGNAL: {start_signal}")
                    
                    if not start_signal:
                        self.logger.info("START_SIGNAL not active, waiting...")
                        await asyncio.sleep(1.0)  # Wait 1 second and try again
                        continue
                    
                    self.logger.info("✅ START_SIGNAL active, proceeding to first scan")
                    
                except Exception as e:
                    self.logger.error(f"❌ Error reading START_SIGNAL: {e}")
                    await asyncio.sleep(1.0)
                    continue

                # Phase 2: First scan
                self._notify_state_change(CycleState.FIRST_SCAN)
                first_scan_result = await self.handle_first_scan()
                if not first_scan_result.should_continue:
                    await self.handle_reset_or_error(first_scan_result.error)
                    continue

                # Phase 3: Generate barcode
                self._notify_state_change(CycleState.BARCODE_GEN)
                barcode_data = await self.generate_and_write_barcode()
                if not barcode_data:
                    await self.handle_error("Failed to generate barcode")
                    continue

                # Phase 4: Middle scan
                self._notify_state_change(CycleState.MIDDLE_SCAN)
                middle_scan_result = await self.handle_middle_scan()
                if not middle_scan_result.should_continue:
                    await self.handle_reset_or_error(middle_scan_result.error)
                    continue

                # Phase 5: Verification scan
                self._notify_state_change(CycleState.VERIFICATION)
                verification_result = await self.handle_verification_scan()
                if not verification_result.should_continue:
                    await self.handle_reset_or_error(verification_result.error)
                    continue

                # Phase 6: Final checks
                self._notify_state_change(CycleState.FINAL_CHECK)
                await self.perform_final_checks()

                # Mark cycle complete
                self._notify_state_change(CycleState.COMPLETE)
                self.stats["cycles_completed"] += 1

                # Brief pause before next cycle
                await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.error(f"Error in scan cycle: {e}")
                await self.handle_error(str(e))

    async def check_reset_or_bit(
        self, register: int, bit: int, expected_value: int, timeout: float = None
    ) -> str:
        """Check for bit value or reset signal"""
        return await self.plc.check_reset_or_bit(register, bit, expected_value, timeout)

    async def handle_first_scan(self) -> ScanResult:
        """Handle first scanner operation"""
        try:
            # Wait for OCR read trigger
            result = await self.check_reset_or_bit(*PLCRegisterMap.OCR_READ_TRIGGER, 1)
            if result == "RESET":
                return ScanResult(False, "", "RESET")
            elif result == "TIMEOUT":
                return ScanResult(False, "", "Timeout waiting for OCR trigger")

            # Read OCR data from PLC
            ocr_data = await self.plc.read_ascii_data(PLCRegisterMap.OCR_DATA_START)
            if not ocr_data:
                await self.plc.write_bit(*PLCRegisterMap.FIRST_SCAN_NG, True)
                return ScanResult(False, "", "Failed to read OCR data")

            # Write OCR data to file
            await self.write_ocr_data_to_file(ocr_data)

            # Trigger first scanner
            scanner_data = await self.scanner_service.fetch_scanner_data(
                ScannerType.MAIN, *PLCRegisterMap.FIRST_SCANNER_TRIGGER, timeout=30.0
            )

            if scanner_data == "RESET":
                return ScanResult(False, "", "RESET")
            elif scanner_data == "NG":
                await self.plc.write_bit(*PLCRegisterMap.FIRST_SCAN_NG, True)
                return ScanResult(False, "", "First scanner timeout")

            # Compare scanner data with OCR data
            if await self.compare_scanner_data_with_code(scanner_data):
                await self.plc.write_bit(*PLCRegisterMap.FIRST_SCAN_OK, True)

                # Create new record
                self.current_record = ScanRecord(
                    SerialNumber="",  # Will be set in barcode generation
                    MarkingData=ocr_data,
                    ScannerData=scanner_data,
                    Result="OK",
                    Grading="N/A",
                    ModelNumber=self.config.get("model_number", ""),
                    Timestamp=datetime.now(timezone.utc).isoformat(),
                    User=self.config.get("current_user", "operator"),
                    CurrentId=0,  # Will be set by database
                    FirstScanData=scanner_data,
                )

                self._notify_data_update(
                    {
                        "ocr_data": ocr_data,
                        "first_scan_data": scanner_data,
                        "first_scan_result": "OK",
                    }
                )

                return ScanResult(True, scanner_data)
            else:
                await self.plc.write_bit(*PLCRegisterMap.FIRST_SCAN_NG, True)
                return ScanResult(False, "", "First scan data mismatch")

        except Exception as e:
            self.logger.error(f"Error in first scan: {e}")
            await self.plc.write_bit(*PLCRegisterMap.FIRST_SCAN_NG, True)
            return ScanResult(False, "", str(e))

    async def generate_and_write_barcode(self) -> Optional[Dict[str, Any]]:
        """Generate barcode data and write to laser system"""
        try:
            # Wait for laser data transfer signal
            result = await self.check_reset_or_bit(
                *PLCRegisterMap.LASER_DATA_TRANSFER, 1
            )
            if result != "OK":
                return None

            # Generate barcode data
            barcode_data = await self.generate_barcode_data()
            if not barcode_data:
                return None

            # Update current record with serial number
            if self.current_record:
                self.current_record.SerialNumber = barcode_data["serialNo"]

            # Write barcode to file for laser system
            await self.write_barcode_to_file(barcode_data["text"])

            # Confirm OCR read
            await self.plc.write_bit(*PLCRegisterMap.OCR_READ_CONFIRMATION, True)

            self._notify_data_update(
                {
                    "barcode_data": barcode_data["text"],
                    "serial_number": barcode_data["serialNo"],
                }
            )

            return barcode_data

        except Exception as e:
            self.logger.error(f"Error generating barcode: {e}")
            return None

    async def handle_middle_scan(self) -> ScanResult:
        """Handle middle scanner operation"""
        try:
            # Wait for scanner read trigger
            result = await self.check_reset_or_bit(
                *PLCRegisterMap.SCANNER_READ_TRIGGER, 1
            )
            if result == "RESET":
                return ScanResult(False, "", "RESET")
            elif result == "TIMEOUT":
                return ScanResult(False, "", "Timeout waiting for scanner trigger")

            # Trigger middle scanner
            scanner_data = await self.scanner_service.fetch_scanner_data(
                ScannerType.MIDDLE, *PLCRegisterMap.MIDDLE_SCANNER_TRIGGER, timeout=30.0
            )

            if scanner_data == "RESET":
                return ScanResult(False, "", "RESET")
            elif scanner_data == "NG":
                return ScanResult(False, "", "Middle scanner timeout")

            # Update current record
            if self.current_record:
                self.current_record.MiddleScanData = scanner_data

            self._notify_data_update(
                {"middle_scan_data": scanner_data, "middle_scan_result": "OK"}
            )

            return ScanResult(True, scanner_data)

        except Exception as e:
            self.logger.error(f"Error in middle scan: {e}")
            return ScanResult(False, "", str(e))

    async def handle_verification_scan(self) -> ScanResult:
        """Handle verification scanner operation"""
        try:
            # Trigger verification scanner
            scanner_data = await self.scanner_service.fetch_scanner_data(
                ScannerType.VERIFICATION,
                *PLCRegisterMap.VERIFICATION_SCANNER_TRIGGER,
                timeout=30.0,
            )

            if scanner_data == "RESET":
                return ScanResult(False, "", "RESET")
            elif scanner_data == "NG":
                return ScanResult(False, "", "Verification scanner timeout")

            # Compare with expected data
            comparison_result = await self.compare_scanner_data_with_code(scanner_data)

            # Update current record
            if self.current_record:
                self.current_record.VerificationScanData = scanner_data
                self.current_record.Result = "OK" if comparison_result else "NG"

            # Set PLC status bits
            if comparison_result:
                await self.plc.write_bit(*PLCRegisterMap.DATA_MATCH_OK, True)
                self.stats["ok_results"] += 1
            else:
                await self.plc.write_bit(*PLCRegisterMap.DATA_MATCH_NG, True)
                self.stats["ng_results"] += 1

            self._notify_data_update(
                {
                    "verification_scan_data": scanner_data,
                    "verification_result": "OK" if comparison_result else "NG",
                }
            )

            return ScanResult(True, scanner_data)

        except Exception as e:
            self.logger.error(f"Error in verification scan: {e}")
            return ScanResult(False, "", str(e))

    async def perform_final_checks(self):
        """Perform final cycle checks and save data"""
        try:
            # Calculate processing time
            if self.current_record:
                self.current_record.ProcessingTime = time.time() - self.cycle_start_time

                # Save record to database
                success = await self.database.insert_record(self.current_record)
                if not success:
                    self.logger.error("Failed to save record to database")

            # Wait for cycle completion signal
            await self.check_reset_or_bit(*PLCRegisterMap.CYCLE_COMPLETION, 1)

            # Clear code file
            await self.clear_code_file()

            self.logger.info("Cycle completed successfully")

        except Exception as e:
            self.logger.error(f"Error in final checks: {e}")

    async def handle_reset_or_error(self, reason: str):
        """Handle reset signal or error condition"""
        self.logger.warning(f"Handling reset/error: {reason}")
        self._notify_state_change(CycleState.RESET)

        if reason == "RESET":
            self.stats["reset_count"] += 1
        else:
            self.stats["cycles_failed"] += 1

        # Reset PLC bits
        await self.plc.reset_all_bits()

        # Clear code file
        await self.clear_code_file()

        # Reset current record
        self.current_record = None

        # Brief delay before continuing
        await asyncio.sleep(1.0)

    async def handle_error(self, error_message: str):
        """Handle general error condition"""
        self.logger.error(f"Handling error: {error_message}")
        self._notify_error(error_message)
        self._notify_state_change(CycleState.ERROR)

        self.stats["cycles_failed"] += 1

        # Brief delay before continuing
        await asyncio.sleep(2.0)

    # File operation methods
    async def write_ocr_data_to_file(self, data: str):
        """Write OCR data to code file"""
        code_file_path = self.config.get("code_file_path", "./data/code.txt")
        with open(code_file_path, "w", encoding="utf-8") as f:
            f.write(data)

    async def write_barcode_to_file(self, data: str):
        """Write barcode data to file for laser system"""
        barcode_file_path = self.config.get("barcode_file_path", "./data/barcode.txt")
        with open(barcode_file_path, "w", encoding="utf-8") as f:
            f.write(data)

    async def clear_code_file(self):
        """Clear the code file"""
        code_file_path = self.config.get("code_file_path", "./data/code.txt")
        with open(code_file_path, "w", encoding="utf-8") as f:
            f.write("")

    async def compare_scanner_data_with_code(self, scanner_data: str) -> bool:
        """Compare scanner data with code file content"""
        try:
            code_file_path = self.config.get("code_file_path", "./data/code.txt")
            with open(code_file_path, "r", encoding="utf-8") as f:
                code_data = f.read().strip()
            return scanner_data.strip() == code_data
        except:
            return False

    async def generate_barcode_data(self) -> Optional[Dict[str, str]]:
        """Generate barcode data with serial number"""
        try:
            from ..utils.barcode_generator import BarcodeGenerator

            generator = BarcodeGenerator(self.config)
            return await generator.generate_barcode()
        except Exception as e:
            self.logger.error(f"Error generating barcode: {e}")
            return None

    def get_current_status(self) -> Dict[str, Any]:
        """Get current controller status"""
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "current_state": self.current_state.value,
            "current_record": (
                self.current_record.to_dict() if self.current_record else None
            ),
            "stats": self.stats.copy(),
            "uptime": time.time() - self.stats["uptime_start"],
        }
