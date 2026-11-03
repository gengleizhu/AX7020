"""Build FPGA Manager firmware using the installed Xilinx bootgen."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil

ROOT = Path(__file__).resolve().parents[2]
PROJECTS = ['bcrypt8', 'descrypt8', 'md5crypt8', 'sha256crypt8', 'sha512crypt4']

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bootgen', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for algorithm, project in enumerate(PROJECTS, 1):
        name = 'john_ax7020_' + project
        source = ROOT / ('john-ax7020-' + project) / 'deliverables'
        if algorithm == 1:
            source /= 'soc8'
        bit = (source / (name + '.bit')).resolve()
        staged = args.output.resolve() / bit.name
        shutil.copy2(bit, staged)
        bif = args.output / (name + '.bif')
        bif.write_text('all:\n{\n  "' + staged.as_posix() + '"\n}\n')
        # Bootgen emits beside its input; stage inputs in the package directory.
        subprocess.run([args.bootgen, '-image', str(bif.resolve()), '-arch',
                        'zynq', '-process_bitstream', 'bin', '-w'],
                       cwd=args.output, check=True)
        binary = args.output / (name + '.bit.bin')
        if not binary.exists():
            binary = args.output / (name + '.bin')
        if not binary.exists():
            raise RuntimeError('bootgen output not found for ' + name)
        manifest = dict(firmware=binary.name, algorithm=algorithm,
                        register_abi=0x10001, stream_abi=0x10000,
                        sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                        source_bit_sha256=hashlib.sha256(bit.read_bytes()).hexdigest())
        (args.output / (name + '.json')).write_text(json.dumps(manifest, indent=2))
        print(name, binary.stat().st_size, manifest['sha256'])

if __name__ == '__main__':
    main()
