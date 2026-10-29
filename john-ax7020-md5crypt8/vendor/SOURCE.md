# Source provenance

`fpga-md5crypt` is a byte-for-byte copy of the pre-existing local John snapshot:
`E:/zhugenglei.work/john/john_hash_resource_eval/vendor/john/src/ztex/fpga-md5crypt`.
Upstream project: https://github.com/openwall/john/tree/bleeding-jumbo/src/ztex/fpga-md5crypt
The local snapshot does not contain Git metadata; no unverified commit ID is asserted.
Original source copyright/license notices are retained.

The original `util/asymm_bram.v` is preserved but excluded from compilation.
`rtl/asymm_bram.v` and `rtl/log2_compat.vh` are Vivado compatibility replacements
reused from the existing resource-evaluation project. They are not upstream modifications.
The project uses the original real portable RTL selected by `SIMULATION`, not ISE blackboxes.

`rtl/cpu_vivado.v` copies the original CPU with two explicit compatibility changes:
include `md5.vh` via the configured search path, and use a nonblocking assignment
for `iop_sets_cf` in the clocked instruction-decode process. The original blocking
assignment races the CPU flag update process in XSim. The original vendor CPU is
excluded from compilation, but preserved unchanged for comparison.

PYNQ PS preset provenance is separately recorded in `pynq_reference/SOURCE.md`.
Delivery audit records individual source SHA-256 hashes in `reports/summary.json`.
