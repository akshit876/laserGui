# Check dependencies only
python main.py --check-deps

# Setup environment only  
python main.py --setup-env

# Run with debug logging
python main.py --log-level DEBUG

# Use custom configuration
python main.py --config ./config/custom_config.json

# Show help
python main.py --help# Laser Marking System

A professional industrial laser marking and barcode scanning system built with Python and Tkinter.

## Features

- **Real-time PLC Communication**: Modbus TCP communication with industrial PLCs
- **Multi-Scanner Support**: TCP communication with multiple barcode scanners
- **Database Integration**: MongoDB integration for data storage and retrieval
- **Professional GUI**: Custom Tkinter interface with real-time monitoring
- **Serial Number Generation**: Automated serial number generation with shift management
- **Comprehensive Logging**: Advanced logging and error handling
- **Configuration Management**: Flexible JSON-based configuration system

## System Requirements

- Python 3.8 or higher
- Windows/Linux/macOS
- MongoDB (for data storage)
- Network access to PLC and scanners

## Quick Start

1. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Setup environment:**

   ```bash
   python main.py --setup-env
   ```

3. **Check dependencies:**

   ```bash
   python main.py --check-deps
   ```

4. **Start the application:**

   ```bash
   python main.py
   ```

## Configuration

The system uses a JSON configuration file located at `config/config.json`. Key configuration sections:

### PLC Configuration

```json
{
  "plc": {
    "host": "192.168.3.146",
    "port": 502,
    "timeout": 5,
    "retries": 3
  }
}
```

### Scanner Configuration

```json
{
  "scanners": {
    "main": {
      "host": "192.168.1.100",
      "port": 8080,
      "timeout": 30
    },
    "middle": {
      "host": "192.168.1.101", 
      "port": 8080,
      "timeout": 30
    },
    "verification": {
      "host": "192.168.1.102",
      "port": 8080,
      "timeout": 30
    }
  }
}
```

### Database Configuration

```json
{
  "database": {
    "connection_string": "mongodb://localhost:27017/",
    "database_name": "main-data",
    "collection_name": "records"
  }
}
```

## Project Structure

```
laserGui/
├── src/
│   ├── communication/
│   │   ├── plc_client.py          # PLC Modbus TCP communication
│   │   └── tcp_scanner.py         # Scanner TCP communication
│   ├── controllers/
│   │   └── scanner_controller.py  # Main system controller
│   ├── database/
│   │   └── mongodb_client.py      # MongoDB interface
│   ├── gui/
│   │   └── main_gui.py            # Tkinter GUI application
│   └── utils/
│       ├── config_manager.py      # Configuration management
│       ├── logging_system.py      # Logging and error handling
│       └── barcode_generator.py   # Barcode generation utilities
├── config/
│   └── config.json                # Main configuration file
├── data/                          # Data files and backups
├── logs/                          # System logs
├── requirements.txt               # Python dependencies
├── main.py                        # Main entry point
└── README.md                      # This file
```

## Operating Cycle

The system implements a continuous scanning cycle with the following phases:

1. **Waiting**: Wait for start signal from PLC (register 1410.0)
2. **First Scan**: Read OCR data and perform first scanner operation
3. **Barcode Generation**: Generate serial number and barcode data
4. **Middle Scan**: Perform marking verification scan
5. **Verification Scan**: Final quality check scan
6. **Final Check**: Save data and complete cycle

## PLC Register Mapping

### Control Registers (Read)

- 1410.0: Start signal
- 1410.1: OCR read trigger
- 1410.2: Laser data transfer
- 1410.3: Scanner read trigger
- 1410.11: File transfer signal
- 1410.12: Cycle completion

### Status Registers (Write)

- 1414.3: Data match OK
- 1414.4: Data match NG
- 1414.6: First scan OK
- 1414.7: First scan NG
- 1414.15: OCR read confirmation

### Scanner Triggers (Write)

- 1415.0: First scanner trigger
- 1416.15: Verification scanner trigger
- 1418.0: Middle scanner trigger

### Data Registers

- 1450-1469: OCR data (20 registers)
- 1470-1489: Scanner data (20 registers)

### Reset Signal

- 1600.0: Reset signal

## GUI Features

- **Real-time Status Display**: Current system state and cycle progress
- **Connection Monitoring**: Status of PLC, database, and scanner connections
- **Data Visualization**: Live display of scan data and results
- **Statistics Dashboard**: Cycle counts, success rates, and performance metrics
- **System Controls**: Start/stop/pause controls with safety features
- **System Log**: Real-time log display with filtering
- **Test Functions**: Built-in connection and component testing

## Data Storage

Scan records are stored in MongoDB with the following schema:

```json
{
  "SerialNumber": "string",
  "MarkingData": "string", 
  "ScannerData": "string",
  "Result": "OK|NG",
  "Grading": "A|B|C|N/A",
  "ModelNumber": "string",
  "Timestamp": "ISO date",
  "User": "string",
  "CurrentId": "number",
  "FirstScanData": "string",
  "MiddleScanData": "string", 
  "VerificationScanData": "string",
  "ProcessingTime": "float",
  "ErrorMessages": ["array"]
}
```

## Serial Number Format

Serial numbers are generated using a configurable format:

- Default: `YYYYMMDD{shift}{counter:04d}`
- Example: `202409221001` (Sept 22, 2024, Shift 1, Counter 0001)

## Shift Management

The system supports 3 shifts:

- Shift 1: 06:00 - 14:00 (Day Shift)
- Shift 2: 14:00 - 22:00 (Evening Shift)  
- Shift 3: 22:00 - 06:00 (Night Shift)

## Error Handling

- **Automatic Retry**: Failed operations are automatically retried
- **Reset Detection**: System monitors for reset signals every 100ms
- **Recovery Strategies**: Configurable recovery mechanisms for different error types
- **Comprehensive Logging**: All errors are logged with context and stack traces

## Maintenance

### Database Backup

```bash
# Automatic backup is configured in the system
# Manual backup can be triggered through the GUI
```

### Log Management

- Logs are automatically rotated when they reach 10MB
- Last 5 log files are kept
- Logs older than 7 days are automatically cleaned

### Statistics

- Daily, shift-based, and overall statistics are available
- Performance metrics are tracked and logged
- Success rates and error patterns are monitored

## Troubleshooting

### Common Issues

1. **PLC Connection Failed**
   - Check network connectivity
   - Verify PLC IP address and port
   - Check firewall settings

2. **Scanner Timeout**
   - Verify scanner IP addresses
   - Check TCP port accessibility
   - Ensure scanners are powered and configured

3. **Database Connection Error**
   - Ensure MongoDB is running
   - Check connection string
   - Verify database permissions

4. **Serial Number Conflicts**
   - Check serial counter file integrity
   - Verify shift configuration
   - Reset counters if necessary

### Debug Mode

Run with debug logging:

```bash
python main.py --log-level DEBUG
```

### Configuration Validation

Test configuration:

```bash
python main.py --check-deps
```

## Development

### Adding New Features

1. Create feature branch
2. Add implementation in appropriate module
3. Update configuration schema if needed
4. Add logging and error handling
5. Update GUI if required
6. Test thoroughly

### Code Style

- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Add comprehensive docstrings
- Include error handling in all functions

## License

This software is proprietary and confidential. All rights reserved.

## Support

For technical support or questions, contact the development team.

---

**Laser Marking System v1.0.0**  
Industrial automation solution for laser marking and quality control.
