"""Build a clean, reproducible-layout host delivery without credentials/cache."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'output' / 'AX7020_Python_Integration_Kit_20261104_v5.zip'
files = {}
common = ROOT / 'john-ax7020-common'
for name in ('john_udp_client.py', 'john_fpga_client.py', 'john_time_sync.py',
             'SDK_INTEGRATION.md', 'DEPLOYMENT_FINAL.md'):
    files['src/john-ax7020-common/host/' + name] = (common / 'host' / name).read_bytes()
for path in sorted((common / 'host/examples').iterdir()):
    if path.is_file() and path.suffix in ('.py', '.md'):
        files['src/john-ax7020-common/host/examples/' + path.name] = path.read_bytes()
for name in ('john_udp_protocol.py', 'john_management.py'):
    files['src/john-ax7020-common/linux/node/' + name] = (common / 'linux/node' / name).read_bytes()
files['src/john-ax7020-common/software/axi_protocol.py'] = (common / 'software/axi_protocol.py').read_bytes()
for project, names in {
    'bcrypt8': ['john_packet_codec.py'], 'descrypt8': ['codec.py', 'codec8.py'],
    'md5crypt8': ['codec.py'], 'sha256crypt8': ['codec.py'],
    'sha512crypt4': ['codec.py'],
}.items():
    for name in names:
        rel = 'john-ax7020-' + project + '/host/' + name
        files['src/' + rel] = (ROOT / rel).read_bytes()
files['README.md'] = (common / 'host/INTEGRATION_KIT_README.md').read_bytes().replace(b'Kit v3', b'Kit v5') + (
    '\n\n2026-11-04更新：自动授时及双节点部署请先阅读 '
    'src/john-ax7020-common/host/DEPLOYMENT_FINAL.md。\n'
    'docs中的PDF是2026-11-03历史协议资料，未覆盖新增授时参数；当前接口以随包源码和Markdown为准。\n'
).encode('utf-8')
for path in sorted((ROOT / 'output/pdf').glob('*20261103.pdf')):
    files['docs/historical/' + path.name] = path.read_bytes()
files['VERSION.txt'] = b'2026.11.04-v5 unified-sdk-auto-time-sync\n'
files['requirements.txt'] = b'passlib==1.7.4\n'
files['SHA256SUMS.json'] = json.dumps({name: hashlib.sha256(data).hexdigest()
    for name, data in sorted(files.items())}, indent=2, ensure_ascii=False).encode('utf-8')
with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED) as archive:
    for name, data in sorted(files.items()):
        archive.writestr(name, data)
with zipfile.ZipFile(OUTPUT) as archive:
    assert archive.testzip() is None
    assert not any('__pycache__' in name or name.endswith('.key') for name in archive.namelist())
print(str(OUTPUT))
print('files=%d sha256=%s' % (len(files), hashlib.sha256(OUTPUT.read_bytes()).hexdigest()))
