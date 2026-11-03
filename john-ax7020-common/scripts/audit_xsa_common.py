#!/usr/bin/env python3
"""Audit that the five AX7020 XSA exports share one Linux-visible platform."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


ALGORITHMS = {
    "bcrypt8": (1, "john-ax7020-bcrypt8/deliverables/soc8/john_ax7020_bcrypt8.xsa"),
    "descrypt8": (2, "john-ax7020-descrypt8/deliverables/john_ax7020_descrypt8.xsa"),
    "md5crypt8": (3, "john-ax7020-md5crypt8/deliverables/john_ax7020_md5crypt8.xsa"),
    "sha256crypt8": (4, "john-ax7020-sha256crypt8/deliverables/john_ax7020_sha256crypt8.xsa"),
    "sha512crypt4": (5, "john-ax7020-sha512crypt4/deliverables/john_ax7020_sha512crypt4.xsa"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parameters(module: ET.Element) -> dict[str, str]:
    return {
        item.get("NAME", ""): item.get("VALUE", "")
        for item in module.findall("./PARAMETERS/PARAMETER")
    }


def ports(module: ET.Element) -> dict[str, dict[str, str]]:
    return {
        item.get("NAME", ""): dict(item.attrib)
        for item in module.findall("./PORTS/PORT")
    }


def canonical(element: ET.Element):
    attributes = []
    for key, value in element.attrib.items():
        if key == "TIMESTAMP":
            continue
        if element.tag == "PARAMETER" and key == "VALUE" and element.get("NAME") == "ALGORITHM":
            value = "COMMON_ALGORITHM_ID"
        attributes.append((key, value))
    return (
        element.tag,
        sorted(attributes),
        (element.text or "").strip(),
        [canonical(child) for child in element],
    )


def load_xsa(path: Path):
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise AssertionError(f"corrupt XSA member: {path}: {bad}")
        hwh_data = archive.read("system.hwh")
        root = ET.fromstring(hwh_data)
        module_map = {item.get("INSTANCE", ""): item for item in root.iter("MODULE")}
        bit_names = [name for name in archive.namelist() if name.endswith(".bit")]
        if len(bit_names) != 1:
            raise AssertionError(f"expected one embedded bitstream in {path}, got {bit_names}")
        bit_data = archive.read(bit_names[0])
        ps7_init = archive.read("ps7_init.c")
    return root, module_map, hwh_data, bit_data, ps7_init


def require_same_net(left: dict[str, str], right: dict[str, str], description: str) -> None:
    if not left.get("SIGNAME") or left.get("SIGNAME") != right.get("SIGNAME"):
        raise AssertionError(f"{description} is not connected to one net: {left} != {right}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "reports" / "xsa_common_audit_20261102.json",
    )
    args = parser.parse_args()
    repo = args.repo.resolve()
    summary = {}
    canonical_roots = []
    ps7_init_hashes = set()

    for name, (expected_algorithm, relative_path) in ALGORITHMS.items():
        xsa_path = repo / relative_path
        if not xsa_path.is_file():
            raise AssertionError(f"missing XSA: {xsa_path}")
        root, modules, hwh_data, bit_data, ps7_init = load_xsa(xsa_path)
        required = {
            "ps7_0", "dma", "status", "unified", "dma_irq_concat",
            "dma_irq_zero", "startup_reset", "result_slice",
        }
        missing = sorted(required - set(modules))
        if missing:
            raise AssertionError(f"{name}: missing modules: {missing}")

        ps_params = parameters(modules["ps7_0"])
        dma_ports = ports(modules["dma"])
        concat_ports = ports(modules["dma_irq_concat"])
        zero_ports = ports(modules["dma_irq_zero"])
        ps_ports = ports(modules["ps7_0"])
        concat_params = parameters(modules["dma_irq_concat"])
        zero_params = parameters(modules["dma_irq_zero"])
        unified_params = parameters(modules["unified"])

        if int(unified_params["ALGORITHM"], 0) != expected_algorithm:
            raise AssertionError(f"{name}: unexpected algorithm ID {unified_params['ALGORITHM']}")
        if ps_params.get("PCW_USE_FABRIC_INTERRUPT") != "1":
            raise AssertionError(f"{name}: fabric interrupt is disabled")
        if ps_params.get("PCW_IRQ_F2P_MODE") != "DIRECT":
            raise AssertionError(f"{name}: IRQ_F2P is not DIRECT")
        if (
            concat_params.get("NUM_PORTS") != "3"
            or concat_params.get("IN0_WIDTH") != "1"
            or concat_params.get("IN1_WIDTH") != "1"
            or concat_params.get("IN2_WIDTH") != "14"
        ):
            raise AssertionError(f"{name}: invalid IRQ concat configuration: {concat_params}")
        if int(zero_params.get("CONST_VAL", "-1"), 0) != 0:
            raise AssertionError(f"{name}: inactive IRQ bits are not tied low")

        require_same_net(dma_ports["mm2s_introut"], concat_ports["In0"], f"{name} MM2S IRQ")
        require_same_net(dma_ports["s2mm_introut"], concat_ports["In1"], f"{name} S2MM IRQ")
        require_same_net(zero_ports["dout"], concat_ports["In2"], f"{name} inactive IRQ bits")
        require_same_net(concat_ports["dout"], ps_ports["IRQ_F2P"], f"{name} PS IRQ_F2P")

        address_map = [dict(item.attrib) for item in root.iter("MEMRANGE")]
        expected_addresses = {
            ("dma", "0x40400000", "0x4040FFFF"),
            ("status", "0x41200000", "0x4120FFFF"),
            ("unified", "0x43C00000", "0x43C0FFFF"),
        }
        actual_addresses = {
            (item.get("INSTANCE", ""), item.get("BASEVALUE", ""), item.get("HIGHVALUE", ""))
            for item in address_map
            if item.get("INSTANCE") in {"dma", "status", "unified"}
        }
        if actual_addresses != expected_addresses:
            raise AssertionError(f"{name}: unexpected public address map: {sorted(actual_addresses)}")

        external_bit = xsa_path.with_suffix(".bit")
        external_hwh = xsa_path.with_suffix(".hwh")
        if external_bit.read_bytes() != bit_data:
            raise AssertionError(f"{name}: external and embedded bitstreams differ")
        if external_hwh.read_bytes() != hwh_data:
            raise AssertionError(f"{name}: external and embedded HWH files differ")

        canonical_roots.append(canonical(root))
        ps7_init_hashes.add(sha256(ps7_init))
        summary[name] = {
            "algorithm": expected_algorithm,
            "xsa": str(xsa_path),
            "xsa_sha256": sha256(xsa_path.read_bytes()),
            "bit_sha256": sha256(bit_data),
            "hwh_sha256": sha256(hwh_data),
            "ps7_init_sha256": sha256(ps7_init),
            "addresses": sorted(actual_addresses),
            "mm2s_irq": 29,
            "s2mm_irq": 30,
            "startup_reset_present": True,
            "embedded_exports_match": True,
        }

    if any(item != canonical_roots[0] for item in canonical_roots[1:]):
        raise AssertionError("five HWH descriptions differ beyond the allowed ALGORITHM parameter")
    if len(ps7_init_hashes) != 1:
        raise AssertionError("five PS7 initialization sources differ")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS: five XSA exports share PS, address map, DMA IRQ, startup reset and common HWH")
    print(f"report={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
