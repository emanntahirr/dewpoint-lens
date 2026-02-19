"""
Reads CSV from the Pico over serial and saves it.
Close Mu first or it'll hog the port.
"""

import argparse
import csv
import os
import signal
import sys
import time
from datetime import datetime

import serial

# change this if ur pico shows up on a different port
PORT = "/dev/cu.usbmodem101"
BAUD = 115200


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=0, help="seconds, 0 = until ctrl+c")
    parser.add_argument("--port", default=PORT)
    parser.add_argument("-o", "--output", default=None)
    args = parser.parse_args()

    if args.output:
        filename = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/capture_{timestamp}.csv"

    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else "data", exist_ok=True)

    try:
        ser = serial.Serial(args.port, BAUD, timeout=2)
    except serial.SerialException as e:
        print(f"can't open {args.port}: {e}")
        sys.exit(1)

    print(f"recording to {filename},ctrl+c to stop\n")

    start_time = time.time()
    row_count = 0

    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "elapsed_s", "temp_c", "humidity"])
        try:
            while True:
                if args.duration and (time.time() - start_time) >= args.duration:
                    break

                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                if line.startswith("elapsed_s"):  # pico spits out a header, skip it
                    continue

                parts = line.split(",")
                if len(parts) == 3:
                    try:
                        elapsed = int(parts[0])
                        temp = float(parts[1])
                        hum = float(parts[2])
                        now = datetime.now().isoformat()
                        writer.writerow([now, elapsed, temp, hum])
                        f.flush()
                        row_count += 1
                        print(f"  [{row_count}] {now}  T={temp}°C  RH={hum}%")
                    except ValueError:
                        pass  # garbage line, ignore
        except KeyboardInterrupt:
            pass

    ser.close()
    print(f"\n{row_count} readings saved to {filename}")


if __name__ == "__main__":
    main()
