# boot.py -- run on boot-up
import bluetooth
import network
import machine
import time
import json
import os
from machine import Pin, SPI
import urequests as requests

# Configuration settings
# Bluetooth settings
BLE_DEVICE_NAME = "RaceBox Micro 3242704435"  # Name of the device to connect to
SCAN_TIMEOUT = 10  # Seconds to scan for devices

# WiFi AP settings
AP_SSID = "wongcw"
AP_PASSWORD = "12345678"
AP_CHANNEL = 1
AP_AUTH_MODE = network.AUTH_WPA2_PSK  # 指定安全认证模式: WPA2-PSK

# 使用正确的蓝牙处理方式
_IRQ_SCAN_RESULT = const(1 << 4)
_IRQ_SCAN_DONE = const(1 << 5)
_IRQ_PERIPHERAL_CONNECT = const(1 << 6)
_IRQ_PERIPHERAL_DISCONNECT = const(1 << 7)

# 全局变量
found_devices = []
is_scanning = False
connected = False

class DataManager:
    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self.ble_irq)
        self.wlan = network.WLAN(network.AP_IF)
        self.sim = machine.UART(1, baudrate=115200)  # SIM7670G UART
        
    def ble_irq(self, event, data):
        global found_devices, is_scanning, connected
        
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            name = None
            
            # 尝试从广播数据中获取设备名称
            for i in range(0, len(adv_data), 2):
                if adv_data[i] == 0x09:  # Complete Local Name
                    name = adv_data[i+1:].decode()
                    break
            
            # 检查是否是我们要找的设备
            if name == BLE_DEVICE_NAME:
                print("找到目标设备:", name, "地址:", addr)
                found_devices.append((addr_type, addr, name))
        
        elif event == _IRQ_SCAN_DONE:
            is_scanning = False
            print("扫描完成")
            
        elif event == _IRQ_PERIPHERAL_CONNECT:
            conn_handle, addr_type, addr = data
            print("已连接到设备:", addr)
            connected = True
            
        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            conn_handle, addr_type, addr = data
            print("设备断开连接:", addr)
            connected = False
    
    def scan_ble_devices(self):
        global found_devices, is_scanning
        found_devices = []
        is_scanning = True
        
        # 开始扫描
        self.ble.gap_scan(SCAN_TIMEOUT * 1000, 30000, 30000)
        
        # 等待扫描完成
        timeout = time.time() + SCAN_TIMEOUT
        while is_scanning and time.time() < timeout:
            time.sleep(0.1)
        
        # 返回找到的设备地址
        if found_devices:
            return found_devices[0][1]  # 返回第一个匹配设备的地址
        return None
    
    def connect_ble_device(self, addr):
        try:
            # 在某些固件中是gap_connect，在其他固件中可能是connect
            try:
                self.ble.gap_connect(addr)
            except AttributeError:
                try:
                    self.ble.connect(addr)
                except:
                    print("连接方法不可用")
                    return False
            
            # 等待连接成功
            timeout = time.time() + 5  # 5秒超时
            while not connected and time.time() < timeout:
                time.sleep(0.1)
                
            return connected
        except Exception as e:
            print("连接错误:", e)
            return False
    
    def setup_wifi_ap(self):
        try:
            self.wlan.active(False)  # 先停用，防止配置冲突
            time.sleep(1)
            self.wlan.active(True)
            
            # 配置AP参数时确保指定认证模式
            config_params = {
                'essid': AP_SSID,
                'password': AP_PASSWORD,
                'authmode': AP_AUTH_MODE,  # 明确设置认证模式
                'channel': AP_CHANNEL
            }
            self.wlan.config(**config_params)  # 使用解包操作符设置所有参数
            
            # 等待AP启动
            time.sleep(2)
            
            # 获取并打印AP信息
            ap_info = self.wlan.ifconfig()
            print(f"WiFi AP已启动")
            print(f"SSID: {AP_SSID}, 认证模式: WPA2-PSK")
            print(f"IP地址: {ap_info[0]}, 网络掩码: {ap_info[1]}")
            print(f"网关: {ap_info[2]}, DNS: {ap_info[3]}")
        except Exception as e:
            print("WiFi AP启动失败:", e)
    
    def check_4g_connection(self):
        try:
            self.sim.write('AT+CREG?\r\n')
            time.sleep(1)
            if self.sim.any():
                response = self.sim.read()
                return b'+CREG: 0,1' in response
            return False
        except Exception as e:
            print("4G连接检查失败:", e)
            return False

def main():
    print("初始化...")
    data_manager = DataManager()
    
    # Setup WiFi AP
    print("设置WiFi AP...")
    data_manager.setup_wifi_ap()
    
    print("开始主循环...")
    while True:
        # Check for BLE devices
        print("扫描BLE设备...")
        device_addr = data_manager.scan_ble_devices()
        if device_addr:
            print('找到设备地址: ', device_addr)
            if data_manager.connect_ble_device(device_addr):
                print('设备连接成功: ', device_addr)
                # Handle BLE data here
        
        time.sleep(1)

# 启动程序
print('Boot sequence completed')
main()
