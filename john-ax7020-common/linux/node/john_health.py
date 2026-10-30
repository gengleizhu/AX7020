#!/usr/bin/env python3
"""Low-rate Linux, network, and XADC health sampling for john-node."""

from __future__ import annotations

import glob
from pathlib import Path
import threading
import time


def _text(path, default=""):
    try:
        return Path(path).read_text(encoding="ascii").strip()
    except (OSError, ValueError):
        return default


def _integer(path, default=-1):
    try:
        return int(_text(path))
    except ValueError:
        return default


def _number(path):
    try:
        return float(_text(path))
    except ValueError:
        return None


def _network(interface):
    base = Path("/sys/class/net") / interface
    stats = base / "statistics"
    return {
        "interface": interface,
        "carrier": _integer(base / "carrier", 0),
        "operstate": _text(base / "operstate", "unknown"),
        "speed_mbps": _integer(base / "speed"),
        "duplex": _text(base / "duplex", "unknown").lower(),
        "mtu": _integer(base / "mtu"),
        "rx_bytes": _integer(stats / "rx_bytes", 0),
        "tx_bytes": _integer(stats / "tx_bytes", 0),
        "rx_errors": _integer(stats / "rx_errors", 0),
        "tx_errors": _integer(stats / "tx_errors", 0),
        "rx_dropped": _integer(stats / "rx_dropped", 0),
        "tx_dropped": _integer(stats / "tx_dropped", 0),
    }


def _hwmon_sensors():
    result = {
        "temperature_millic": -1,
        "vccint_uv": -1,
        "vccaux_uv": -1,
        "vccbram_uv": -1,
    }
    for directory in glob.glob("/sys/class/hwmon/hwmon*"):
        name = _text(Path(directory) / "name").lower()
        if "xadc" not in name:
            continue
        temperature = _integer(Path(directory) / "temp1_input")
        if temperature >= 0:
            result["temperature_millic"] = temperature
        for index in range(1, 9):
            label = _text(Path(directory) / f"in{index}_label").lower()
            value = _integer(Path(directory) / f"in{index}_input")
            if value < 0:
                continue
            microvolts = value * 1000
            if "vccint" in label:
                result["vccint_uv"] = microvolts
            elif "vccaux" in label:
                result["vccaux_uv"] = microvolts
            elif "vccbram" in label:
                result["vccbram_uv"] = microvolts
    return result


def _iio_sensors(result):
    for directory in glob.glob("/sys/bus/iio/devices/iio:device*"):
        base = Path(directory)
        if "xadc" not in _text(base / "name").lower():
            continue
        raw = _number(base / "in_temp0_raw")
        scale = _number(base / "in_temp0_scale")
        offset = _number(base / "in_temp0_offset")
        if result["temperature_millic"] < 0 and raw is not None and scale is not None:
            result["temperature_millic"] = int(
                (raw + (offset or 0.0)) * scale
            )
        for label in ("vccint", "vccaux", "vccbram"):
            if result[label + "_uv"] >= 0:
                continue
            raw_paths = glob.glob(str(base / f"in_voltage*_{label}_raw"))
            if not raw_paths:
                continue
            raw_path = Path(raw_paths[0])
            raw_value = _number(raw_path)
            scale_path = Path(str(raw_path).replace("_raw", "_scale"))
            scale_value = _number(scale_path)
            if raw_value is not None and scale_value is not None:
                scaled = raw_value * scale_value
                # IIO drivers commonly expose XADC voltage scale in mV;
                # tolerate a driver exposing it directly in microvolts.
                result[label + "_uv"] = int(
                    scaled * 1000 if scale_value < 10 else scaled
                )


def _sensors():
    result = _hwmon_sensors()
    _iio_sensors(result)
    return result


class HealthMonitor:
    def __init__(self, interface="eth0", interval=5.0):
        self.interface = interface
        self.interval = max(1.0, interval)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.data = {}
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _sample(self):
        try:
            uptime = int(float(_text("/proc/uptime", "0 0").split()[0]))
        except (ValueError, IndexError):
            uptime = 0
        try:
            loads = [
                int(float(value) * 1000)
                for value in _text("/proc/loadavg", "").split()[:3]
            ]
            if len(loads) != 3:
                raise ValueError
        except ValueError:
            loads = [-1, -1, -1]
        return {
            "sample_time": int(time.time()),
            "linux_uptime_s": uptime,
            "load_milli": loads,
            "network": _network(self.interface),
            "sensors": _sensors(),
        }

    def _run(self):
        while not self.stop_event.is_set():
            sample = self._sample()
            with self.lock:
                self.data = sample
            self.stop_event.wait(self.interval)

    def snapshot(self):
        with self.lock:
            return dict(self.data)

    def close(self):
        self.stop_event.set()
        self.thread.join(timeout=2)
