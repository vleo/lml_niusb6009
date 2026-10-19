#! /bin/env python
import time
import subprocess
import usb.core

VID, PID = 0x3923, 0x717b
INTERFACE = 0  # если нужен конкретный интерфейс

def wait_for_device(vid, pid, timeout=None, poll_interval=1.0):
    start = time.time()
    while True:
        dev = usb.core.find(idVendor=vid, idProduct=pid)
        if dev is not None:
            return dev
        if timeout is not None and (time.time() - start) > timeout:
            raise TimeoutError("Устройство не появилось за отведённое время")
        time.sleep(poll_interval)

def main():
    dev = wait_for_device(VID, PID, timeout=60.0)  # ждём до 60 сек
    bus, addr = dev.bus, dev.address
    print(f"Device found: Bus {bus}, Address {addr}")

    # Собираем команду tshark. Важно: фильтр по device_address — это именно addr (не bus:addr)
    cmd = [
        "sudo", "tshark",
        "-i", "usbmon1",
        "-Y", f"usb.device_address == {addr}",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "frame.time_relative",
        "-e", "usb.src",
        "-e", "usb.dst",
        "-e", "usb.endpoint_address",
        "-e", "usb.urb_type",
        "-e", "usb.capdata",
        "-E", "header=y",
        "-E", "separator=|",
        "-E", "occurrence=a",
        "-l"
    ]

    # Запускаем сниффер. Он будет работать, пока ты его не остановишь (Ctrl+C)
    subprocess.run(cmd)

if __name__ == "__main__":
    main()
