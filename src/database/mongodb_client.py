"""
Database Interface for Laser Marking System
Handles MongoDB operations for storing and retrieving scan records
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError
import json


@dataclass
class ScanRecord:
    """Data model for scan records"""

    SerialNumber: str
    MarkingData: str
    ScannerData: str
    Result: str  # "OK" or "NG"
    Grading: str  # "A", "B", "C", or "N/A"
    ModelNumber: str
    Timestamp: str  # ISO format
    User: str
    CurrentId: int

    # Additional fields for tracking
    FirstScanData: str = ""
    MiddleScanData: str = ""
    VerificationScanData: str = ""
    ProcessingTime: float = 0.0
    ErrorMessages: List[str] = None

    def __post_init__(self):
        if self.ErrorMessages is None:
            self.ErrorMessages = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScanRecord":
        """Create instance from dictionary"""
        return cls(**data)


class DatabaseClient:
    """
    MongoDB client for laser marking system
    Manages all database operations for scan records
    """

    def __init__(
        self,
        connection_string: str = "mongodb://localhost:27017/",
        database_name: str = "main-data",
        collection_name: str = "records",
    ):
        """
        Initialize database client

        Args:
            connection_string: MongoDB connection string
            database_name: Name of the database
            collection_name: Name of the collection
        """
        self.connection_string = connection_string
        self.database_name = database_name
        self.collection_name = collection_name
        self.client = None
        self.database = None
        self.collection = None
        self.logger = logging.getLogger(__name__)
        self.is_connected = False
        self._current_id_counter = 0

    async def connect(self) -> bool:
        """
        Establish connection to MongoDB

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.client = AsyncIOMotorClient(self.connection_string)

            # Test the connection
            await self.client.admin.command("ping")

            self.database = self.client[self.database_name]
            self.collection = self.database[self.collection_name]

            # Initialize current ID counter
            await self._initialize_current_id()

            self.is_connected = True
            self.logger.info(
                f"Connected to MongoDB: {self.database_name}.{self.collection_name}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to MongoDB: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            self.is_connected = False
            self.logger.info("Disconnected from MongoDB")

    async def _ensure_connection(self) -> bool:
        """Ensure database connection is active"""
        if not self.is_connected:
            return await self.connect()

        try:
            # Test connection with a ping
            await self.client.admin.command("ping")
            return True
        except:
            self.is_connected = False
            return await self.connect()

    async def _initialize_current_id(self):
        """Initialize the current ID counter from database"""
        try:
            # Find the highest CurrentId in the database
            result = (
                await self.collection.find().sort("CurrentId", -1).limit(1).to_list(1)
            )

            if result:
                self._current_id_counter = result[0].get("CurrentId", 0)
            else:
                self._current_id_counter = 0

            self.logger.info(
                f"Initialized CurrentId counter to: {self._current_id_counter}"
            )

        except Exception as e:
            self.logger.error(f"Error initializing CurrentId counter: {e}")
            self._current_id_counter = 0

    def _get_next_current_id(self) -> int:
        """Get the next CurrentId value"""
        self._current_id_counter += 1
        return self._current_id_counter

    async def insert_record(self, record: ScanRecord) -> bool:
        """
        Insert a new scan record

        Args:
            record: ScanRecord instance to insert

        Returns:
            bool: True if successful, False otherwise
        """
        if not await self._ensure_connection():
            return False

        try:
            # Set CurrentId if not already set
            if record.CurrentId == 0:
                record.CurrentId = self._get_next_current_id()

            # Ensure timestamp is set
            if not record.Timestamp:
                record.Timestamp = datetime.now(timezone.utc).isoformat()

            # Insert the record
            result = await self.collection.insert_one(record.to_dict())

            if result.inserted_id:
                self.logger.info(f"Inserted record with CurrentId: {record.CurrentId}")
                return True
            else:
                self.logger.error("Failed to insert record - no ID returned")
                return False

        except PyMongoError as e:
            self.logger.error(f"MongoDB error inserting record: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error inserting record: {e}")
            return False

    async def update_record(self, current_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update an existing record

        Args:
            current_id: CurrentId of the record to update
            updates: Dictionary of fields to update

        Returns:
            bool: True if successful, False otherwise
        """
        if not await self._ensure_connection():
            return False

        try:
            result = await self.collection.update_one(
                {"CurrentId": current_id}, {"$set": updates}
            )

            if result.modified_count > 0:
                self.logger.info(f"Updated record with CurrentId: {current_id}")
                return True
            else:
                self.logger.warning(f"No record found with CurrentId: {current_id}")
                return False

        except PyMongoError as e:
            self.logger.error(f"MongoDB error updating record: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error updating record: {e}")
            return False

    async def find_record_by_current_id(self, current_id: int) -> Optional[ScanRecord]:
        """
        Find a record by CurrentId

        Args:
            current_id: CurrentId to search for

        Returns:
            ScanRecord instance or None if not found
        """
        if not await self._ensure_connection():
            return None

        try:
            result = await self.collection.find_one({"CurrentId": current_id})

            if result:
                # Remove MongoDB's _id field
                result.pop("_id", None)
                return ScanRecord.from_dict(result)
            else:
                return None

        except PyMongoError as e:
            self.logger.error(f"MongoDB error finding record: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error finding record: {e}")
            return None

    async def find_records_by_serial(self, serial_number: str) -> List[ScanRecord]:
        """
        Find records by serial number

        Args:
            serial_number: Serial number to search for

        Returns:
            List of ScanRecord instances
        """
        if not await self._ensure_connection():
            return []

        try:
            cursor = self.collection.find({"SerialNumber": serial_number})
            results = await cursor.to_list(None)

            records = []
            for result in results:
                result.pop("_id", None)
                records.append(ScanRecord.from_dict(result))

            return records

        except PyMongoError as e:
            self.logger.error(f"MongoDB error finding records: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error finding records: {e}")
            return []

    async def get_recent_records(self, limit: int = 100) -> List[ScanRecord]:
        """
        Get recent records sorted by CurrentId

        Args:
            limit: Maximum number of records to return

        Returns:
            List of ScanRecord instances
        """
        if not await self._ensure_connection():
            return []

        try:
            cursor = self.collection.find().sort("CurrentId", -1).limit(limit)
            results = await cursor.to_list(limit)

            records = []
            for result in results:
                result.pop("_id", None)
                records.append(ScanRecord.from_dict(result))

            return records

        except PyMongoError as e:
            self.logger.error(f"MongoDB error getting recent records: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error getting recent records: {e}")
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics

        Returns:
            Dictionary containing statistics
        """
        if not await self._ensure_connection():
            return {}

        try:
            # Total records
            total_records = await self.collection.count_documents({})

            # Records by result
            ok_records = await self.collection.count_documents({"Result": "OK"})
            ng_records = await self.collection.count_documents({"Result": "NG"})

            # Records by grading
            grade_a = await self.collection.count_documents({"Grading": "A"})
            grade_b = await self.collection.count_documents({"Grading": "B"})
            grade_c = await self.collection.count_documents({"Grading": "C"})
            grade_na = await self.collection.count_documents({"Grading": "N/A"})

            # Recent records (last 24 hours)
            yesterday = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            recent_records = await self.collection.count_documents(
                {"Timestamp": {"$gte": yesterday.isoformat()}}
            )

            return {
                "total_records": total_records,
                "ok_records": ok_records,
                "ng_records": ng_records,
                "success_rate": (
                    (ok_records / total_records * 100) if total_records > 0 else 0
                ),
                "grade_a": grade_a,
                "grade_b": grade_b,
                "grade_c": grade_c,
                "grade_na": grade_na,
                "recent_records": recent_records,
                "current_id_counter": self._current_id_counter,
            }

        except PyMongoError as e:
            self.logger.error(f"MongoDB error getting statistics: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}

    async def backup_to_json(self, filename: str, limit: Optional[int] = None) -> bool:
        """
        Backup records to JSON file

        Args:
            filename: Output filename
            limit: Maximum number of records to backup (None for all)

        Returns:
            bool: True if successful, False otherwise
        """
        if not await self._ensure_connection():
            return False

        try:
            cursor = self.collection.find().sort("CurrentId", -1)
            if limit:
                cursor = cursor.limit(limit)

            results = await cursor.to_list(None)

            # Remove MongoDB _id fields
            for result in results:
                result.pop("_id", None)

            # Write to JSON file
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Backed up {len(results)} records to {filename}")
            return True

        except Exception as e:
            self.logger.error(f"Error backing up to JSON: {e}")
            return False

    async def test_connection(self) -> bool:
        """
        Test database connection

        Returns:
            bool: True if connection is working, False otherwise
        """
        try:
            if not self.client:
                return False

            await self.client.admin.command("ping")
            return True

        except Exception as e:
            self.logger.error(f"Database connection test failed: {e}")
            return False
