#!/usr/bin/env python3
"""
PLC Simulator for Laser Marking System
Simulates PLC control signals for testing the laser marking system
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.communication.plc_client import PLCClient, PLCRegisterMap

class PLCSimulator:
    def __init__(self):
        self.plc = PLCClient("192.168.3.146", 502)
        self.running = False
        
    async def connect(self):
        """Connect to the PLC"""
        await self.plc.connect()
        if not self.plc.is_connected:
            print("❌ Failed to connect to PLC")
            return False
        print("✅ Connected to PLC for simulation")
        return True
        
    async def simulate_cycle(self):
        """Simulate a complete scanning cycle"""
        print("🔄 Starting PLC simulation cycle...")
        
        try:
            # Step 1: Set START_SIGNAL (1410.0 = 1)
            print("📡 Setting START_SIGNAL (1410.0 = 1)")
            await self.plc.write_bit(*PLCRegisterMap.START_SIGNAL, True)
            await asyncio.sleep(2)
            
            # Step 2: Set OCR_READ_TRIGGER (1410.1 = 1)
            print("📡 Setting OCR_READ_TRIGGER (1410.1 = 1)")
            await self.plc.write_bit(*PLCRegisterMap.OCR_READ_TRIGGER, True)
            await asyncio.sleep(1)
            
            # Step 3: Write sample OCR data to PLC registers (1450-1469)
            sample_ocr_data = "SAMPLE_CODE_12345"
            print(f"📝 Writing OCR data: '{sample_ocr_data}'")
            await self.write_ascii_data(PLCRegisterMap.OCR_DATA_START, sample_ocr_data)
            await asyncio.sleep(1)
            
            # Step 4: Set LASER_DATA_TRANSFER (1410.2 = 1)
            print("📡 Setting LASER_DATA_TRANSFER (1410.2 = 1)")
            await self.plc.write_bit(*PLCRegisterMap.LASER_DATA_TRANSFER, True)
            await asyncio.sleep(2)
            
            # Step 5: Set SCANNER_READ_TRIGGER (1410.3 = 1) 
            print("📡 Setting SCANNER_READ_TRIGGER (1410.3 = 1)")
            await self.plc.write_bit(*PLCRegisterMap.SCANNER_READ_TRIGGER, True)
            await asyncio.sleep(2)
            
            # Step 6: Set CYCLE_COMPLETION (1410.12 = 1)
            print("📡 Setting CYCLE_COMPLETION (1410.12 = 1)")
            await self.plc.write_bit(*PLCRegisterMap.CYCLE_COMPLETION, True)
            await asyncio.sleep(1)
            
            print("✅ Simulation cycle completed!")
            
        except Exception as e:
            print(f"❌ Error during simulation: {e}")
            
    async def write_ascii_data(self, start_register, data):
        """Write ASCII data to consecutive PLC registers using PLCClient method"""
        success = await self.plc.write_ascii_data(start_register, data, 20)
        if not success:
            print("❌ Failed to write ASCII data")
        else:
            print("✅ ASCII data written successfully")
        
    async def reset_all_signals(self):
        """Reset all control signals"""
        print("🔄 Resetting all PLC control signals...")
        
        signals = [
            PLCRegisterMap.START_SIGNAL,
            PLCRegisterMap.OCR_READ_TRIGGER,
            PLCRegisterMap.LASER_DATA_TRANSFER,
            PLCRegisterMap.SCANNER_READ_TRIGGER,
            PLCRegisterMap.CYCLE_COMPLETION,
        ]
        
        for signal in signals:
            await self.plc.write_bit(*signal, False)
        
        print("✅ All signals reset")
        
    async def continuous_simulation(self, interval=30):
        """Run continuous simulation cycles"""
        print(f"🔁 Starting continuous simulation (every {interval} seconds)")
        
        while self.running:
            await self.simulate_cycle()
            print(f"⏱️  Waiting {interval} seconds before next cycle...")
            await asyncio.sleep(interval)
            
    async def single_step_mode(self):
        """Interactive single step mode"""
        print("🎮 Single Step Mode - Press Enter to trigger each step")
        
        steps = [
            ("START_SIGNAL", PLCRegisterMap.START_SIGNAL),
            ("OCR_READ_TRIGGER", PLCRegisterMap.OCR_READ_TRIGGER),
            ("LASER_DATA_TRANSFER", PLCRegisterMap.LASER_DATA_TRANSFER), 
            ("SCANNER_READ_TRIGGER", PLCRegisterMap.SCANNER_READ_TRIGGER),
            ("CYCLE_COMPLETION", PLCRegisterMap.CYCLE_COMPLETION),
        ]
        
        for step_name, signal in steps:
            input(f"Press Enter to trigger {step_name}...")
            print(f"📡 Setting {step_name}")
            await self.plc.write_bit(*signal, True)
            await asyncio.sleep(0.5)
            
        print("✅ Single step simulation completed!")
        
    async def run_interactive(self):
        """Interactive simulation menu"""
        if not await self.connect():
            return
            
        while True:
            print("\n" + "="*50)
            print("🎛️  PLC Simulator Menu")
            print("="*50)
            print("1. Single simulation cycle")
            print("2. Continuous simulation")
            print("3. Single step mode")
            print("4. Reset all signals")
            print("5. Exit")
            print("-"*50)
            
            choice = input("Choose an option (1-5): ").strip()
            
            if choice == "1":
                await self.simulate_cycle()
            elif choice == "2":
                try:
                    interval = int(input("Enter interval in seconds (default 30): ") or "30")
                    self.running = True
                    await self.continuous_simulation(interval)
                except KeyboardInterrupt:
                    self.running = False
                    print("\n🛑 Continuous simulation stopped")
            elif choice == "3":
                await self.single_step_mode()
            elif choice == "4":
                await self.reset_all_signals()
            elif choice == "5":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice, please try again")
                
        await self.plc.disconnect()

async def main():
    """Main function"""
    simulator = PLCSimulator()
    await simulator.run_interactive()

if __name__ == "__main__":
    print("🚀 PLC Simulator for Laser Marking System")
    print("This tool simulates PLC control signals to test the system")
    print("-"*50)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Simulator interrupted by user")
    except Exception as e:
        print(f"❌ Simulator error: {e}")