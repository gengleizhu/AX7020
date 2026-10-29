# AX7020 baseline before unified AXI integration

This repository captures the five existing AX7020 projects before implementing
the proposed hierarchical AXI register ABI. Target: xc7z020clg400-2,
Vivado/Vitis 2020.1.

Included: project RTL, vendored source and licenses, board configuration,
Vivado regeneration scripts, simulation/test sources, host codecs, reports,
existing deliverables (BIT/HWH/XSA), and register-design workbooks.
Generated Vivado work directories, caches, logs, waveform files, unrelated
boards, and upstream runtime dictionaries are excluded. No files are deleted.

Projects: bcrypt8, descrypt8, md5crypt8, sha256crypt8, sha512crypt4.
The v1.1 register workbook describes planned functionality, not functionality
implemented in these baseline bitstreams. Existing report results were not
rerun when taking this baseline; hardware testing is not implied.

## Recreate a project

```powershell
./john-ax7020-common/build_ax7020.ps1 -Project all -Mode project
./john-ax7020-common/build_ax7020.ps1 -Project all -Mode full
```

The script defaults to E:/Xilinx/Vivado/2020.1/bin/vivado.bat.
Supply -Vivado and -PythonExe when the installed paths differ.

## Recover without overwriting active work

After the baseline tag exists, create a separate checkout:

```powershell
git worktree add ../john-ax7020-baseline baseline-ax7020-before-axi-v1.1
```

The original generated Vivado build directories remain local and untracked.
Create fresh projects in the recovery checkout rather than reusing them.
