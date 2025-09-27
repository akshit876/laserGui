#!/usr/bin/env python3
"""
Test PLC Signal Reading
Direct test to check if we can read signals from the actual PLC
"""

import asyncio
import sys
import os
sys.path.insert(0, './src')
from src.communication.plc_client import PLCClient, PLCRegisterMap

async def test_plc_signals():
    plc = PLCClient('192.168.3.146', 502)
    print('🔗 Connecting to PLC at 192.168.3.146:502...')
    
    try:
        if await plc.connect():
            print('✅ Connected to PLC successfully')
            
            # Test key signals
            signals_to_test = [
                ("START_SIGNAL (1410.0)", 1410, 0),
                ("OCR_READ_TRIGGER (1410.1)", 1410, 1),
                ("LASER_DATA_TRANSFER (1410.2)", 1410, 2), 
                ("SCANNER_READ_TRIGGER (1410.3)", 1410, 3),
                ("RESET_SIGNAL (1600.0)", 1600, 0),
            ]
            
            print("\n📊 Reading PLC signals:")
            print("-" * 50)
            
            for signal_name, register, bit in signals_to_test:
                try:
                    value = await plc.read_bit(register, bit)
                    status = "🟢 TRUE" if value else "🔴 FALSE"
                    print(f"{signal_name:<25} = {status}")
                except Exception as e:
                    print(f"{signal_name:<25} = ❌ ERROR: {e}")
            
            print("-" * 50)
            
            # Test reading entire register 1410
            print("\n📋 Reading entire register 1410:")
            try:
                result = await plc.client.read_holding_registers(address=1410, count=1)
                if not result.isError():
                    register_value = result.registers[0]
                    print(f"Register 1410 raw value: {register_value} (0x{register_value:04X})")
                    print("Bit breakdown:")
                    for bit in range(16):
                        bit_value = bool(register_value & (1 << bit))
                        print(f"  Bit {bit}: {'1' if bit_value else '0'}")
                else:
                    print(f"❌ Error reading register 1410: {result}")
            except Exception as e:
                print(f"❌ Error reading register 1410: {e}")
                
            await plc.disconnect()
            
        else:
            print('❌ Failed to connect to PLC')
            print('💡 Possible issues:')
            print('   - PLC not powered on')
            print('   - Wrong IP address (expecting 192.168.3.146)')
            print('   - Network connectivity issue')
            print('   - PLC not configured for Modbus TCP on port 502')
            
    except Exception as e:
        print(f'❌ Connection error: {e}')

if __name__ == "__main__":
    asyncio.run(test_plc_signals())