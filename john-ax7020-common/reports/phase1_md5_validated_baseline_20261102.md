# Phase 1 MD5 validated baseline (2026-11-02)

This manifest freezes the MD5 artifacts that were used for the completed AX7020
Linux/DMA/UDP board validation before rebuilding the repository deliverables for
the unified five-algorithm platform audit.

## Board-validated artifacts

| Artifact | Size (bytes) | SHA-256 |
|---|---:|---|
| `D:\Documents\ChatGPT\john\output\ax7020_board_dma_20261030\boot_health_queue_v4\image.ub` | 22587668 | `8F78380F43A3564CD2DE8966838CA96E1F11B2FB2518C338B5A7557232A05F33` |
| `D:\Documents\ChatGPT\john\output\diagnostics\md5crypt8_startup_reset\john_ax7020_md5crypt8_startup_reset.bit` | 4045672 | `FFE0AC6A258DA7D22DC5BF30BB1A97C57083F0DCC3D9655C01C0DD154BE6AADF` |
| `D:\Documents\ChatGPT\john\output\diagnostics\md5crypt8_startup_reset\john_ax7020_md5crypt8_startup_reset.xsa` | 1104182 | `DFF4C4DE05681B9F8E92B592C4CF0CE27323ADD310058E934116980647A2E9A8` |

## Validation status

- AX7020 Linux boot: passed.
- AXI-Lite common register access: passed.
- AXI DMA MM2S/S2MM and interrupt path: passed.
- MD5-crypt batch result: 96/96 candidates matched the software reference.
- UDP node service, queue, result cache, heartbeat and health reporting: passed.

The hashes above are the rollback reference. Rebuilding repository deliverables
does not replace or invalidate this already validated image.
