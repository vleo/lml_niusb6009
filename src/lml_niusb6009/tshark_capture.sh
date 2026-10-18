#!/usr/bin/bash

while true; do
	USB_BUS=$(lsusb -d 3923:717b | awk -F'[ :]' '{print $2}')
	USB_DEV_ADDR=$(lsusb -d 3923:717b | awk -F'[ :]' '{print $4}')
    if [[ -n "$USB_DEV_ADDR" ]]; then
        break
    fi
    sleep 1
done

echo "$USB_BUS:$USB_DEV_ADDR"

sudo tshark -i "usbmon${USB_BUS}" \
  -Y "usb.device_address == ${USB_DEV_ADDR}" \
  -T fields \
  -e frame.number \
  -e frame.time_relative \
  -e usb.src \
  -e usb.dst \
  -e usb.endpoint_address \
  -e usb.urb_type \
  -e usb.capdata \
  -E header=y \
  -E separator='|' \
  -E occurrence=a \
  -l

