#!/usr/bin/env python3
"""
TCP Scanner Simulator for Laser Marking System
Simulates barcode scanners to test the system without physical hardware
"""

import asyncio
import logging
import socket
import threading
import time
from datetime import datetime

class TCPScannerSimulator:
    """Simulates a TCP barcode scanner"""
    
    def __init__(self, host="0.0.0.0", port=8080, name="Scanner"):
        self.host = host
        self.port = port
        self.name = name
        self.server = None
        self.clients = []
        self.running = False
        self.scan_data = "SCANNED_BARCODE_12345"
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(f"ScannerSimulator-{name}")
        
    async def start_server(self):
        """Start the TCP server"""
        try:
            self.server = await asyncio.start_server(
                self.handle_client,
                self.host,
                self.port
            )
            self.running = True
            
            addr = self.server.sockets[0].getsockname()
            self.logger.info(f"🚀 {self.name} simulator started on {addr[0]}:{addr[1]}")
            
            async with self.server:
                await self.server.serve_forever()
                
        except Exception as e:
            self.logger.error(f"❌ Failed to start {self.name} simulator: {e}")
            
    async def handle_client(self, reader, writer):
        """Handle client connections"""
        addr = writer.get_extra_info('peername')
        self.logger.info(f"📱 Client connected from {addr}")
        
        try:
            while self.running:
                # Wait for client data or timeout
                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout=1.0)
                    if not data:
                        break
                        
                    message = data.decode().strip()
                    self.logger.info(f"📨 Received: {message}")
                    
                    # Simulate scan response
                    if "SCAN" in message.upper() or "TRIGGER" in message.upper():
                        response = f"{self.scan_data}\n"
                        writer.write(response.encode())
                        await writer.drain()
                        self.logger.info(f"📤 Sent scan data: {self.scan_data}")
                    else:
                        # Echo back the message
                        response = f"OK: {message}\n"
                        writer.write(response.encode())
                        await writer.drain()
                        self.logger.info(f"📤 Sent response: OK")
                        
                except asyncio.TimeoutError:
                    # No data received, continue listening
                    continue
                    
        except Exception as e:
            self.logger.error(f"❌ Client handler error: {e}")
        finally:
            self.logger.info(f"🔌 Client {addr} disconnected")
            writer.close()
            await writer.wait_closed()
            
    def stop(self):
        """Stop the server"""
        self.running = False
        if self.server:
            self.server.close()
            
class MultiScannerSimulator:
    """Manages multiple scanner simulators"""
    
    def __init__(self):
        self.simulators = []
        self.tasks = []
        
    def add_scanner(self, host, port, name):
        """Add a scanner simulator"""
        simulator = TCPScannerSimulator(host, port, name)
        self.simulators.append(simulator)
        return simulator
        
    async def start_all(self):
        """Start all scanner simulators"""
        print("🚀 Starting TCP Scanner Simulators")
        print("=" * 50)
        
        # Create tasks for each simulator
        for sim in self.simulators:
            task = asyncio.create_task(sim.start_server())
            self.tasks.append(task)
            
        # Wait for all tasks
        try:
            await asyncio.gather(*self.tasks)
        except KeyboardInterrupt:
            print("\n🛑 Stopping all simulators...")
            await self.stop_all()
            
    async def stop_all(self):
        """Stop all simulators"""
        for sim in self.simulators:
            sim.stop()
            
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
                
        await asyncio.gather(*self.tasks, return_exceptions=True)
        print("✅ All simulators stopped")

async def main():
    """Main function"""
    print("🔧 TCP Scanner Simulator for Laser Marking System")
    print("=" * 50)
    
    # Create scanner simulators based on config
    multi_sim = MultiScannerSimulator()
    
    # Add scanners from the configuration
    multi_sim.add_scanner("0.0.0.0", 8080, "MainScanner")  # 192.168.1.100:8080
    multi_sim.add_scanner("0.0.0.0", 8081, "MiddleScanner")  # 192.168.1.101:8080  
    multi_sim.add_scanner("0.0.0.0", 8082, "VerificationScanner")  # 192.168.1.102:8080
    
    print("\n📋 Scanner Configuration:")
    print("  Main Scanner:         localhost:8080 (simulates 192.168.1.100:8080)")
    print("  Middle Scanner:       localhost:8081 (simulates 192.168.1.101:8080)")
    print("  Verification Scanner: localhost:8082 (simulates 192.168.1.102:8080)")
    print("\n💡 Update your config.json to use localhost instead of 192.168.1.x")
    print("=" * 50)
    
    try:
        await multi_sim.start_all()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Scanner simulators stopped by user")