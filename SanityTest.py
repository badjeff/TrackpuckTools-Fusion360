import hid
import time
import struct

VENDOR_ID = 0x1d50
PRODUCT_ID = 0x615e
hid_device_path = None
running = True

def hid_loop():
    global VENDOR_ID, PRODUCT_ID, hid_device_path, running, hid

    if hid_device_path:

        device = hid.device()
        try:
            device.open(VENDOR_ID, PRODUCT_ID)
            device.set_nonblocking(True)
        except Exception as e:
            print(f"HID device not found!\n\nError: {type(e).__name__}: {e}")
            running = False

        try:
            while running:
                data = device.read(64)
                if data:
                    # Parse as signed 8-bit integers (range: -127 to +127)
                    tx = struct.unpack('b', bytes([data[1]]))[0]
                    ty = struct.unpack('b', bytes([data[2]]))[0]
                    tz = struct.unpack('b', bytes([data[3]]))[0]
                    rx = struct.unpack('b', bytes([data[4]]))[0]
                    ry = struct.unpack('b', bytes([data[5]]))[0]
                    rz = struct.unpack('b', bytes([data[6]]))[0]
                    btns = data[7]
                    print(f"{tx}, {ty}, {tz}, {rx}, {ry}, {rz}, {btns:08x}b")
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\nInterrupted by user. Closing device...")
        finally:
            device.close()

def main():
  global hid_device_path

  for dev in hid.enumerate():
      if dev['vendor_id'] == VENDOR_ID and dev['product_id'] == PRODUCT_ID:
          if dev['usage'] == 0x4:
            print(f"Device: {dev['product_string']}")
            print(f"  VID: {hex(dev['vendor_id'])} | PID: {hex(dev['product_id'])}")
            print(f"  Usage Page: {hex(dev['usage_page'])} | Usage: {hex(dev['usage'])}")
            try:
                device = hid.device()
                device.open_path(dev['path'])
                print("Device connected.")
                hid_device_path = dev['path']
                device.close()
            except IOError as e:
                print(f"Couldn't connect to device: {e}")
            break

  if hid_device_path == None:
    print("No HID device detected.")
    return

  hid_loop()

main()
