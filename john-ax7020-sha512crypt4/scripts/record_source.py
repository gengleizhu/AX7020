"""Record original-source provenance, checking every file against a Git tree."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent/'john-pynq-bcrypt/third_party/john'
prefix='src/ztex/fpga-sha512crypt/'
def git(*args):return subprocess.check_output(['git','-C',str(REPO),*args],text=True).strip()
# This subtree SHA was obtained from the user's GitHub URL through the connector.
remote_algorithm_tree='5ea292372b9796a31b10d9a848cbe0d0013fd4b4'
assert git('rev-parse','HEAD:'+prefix+'sha512crypt')==remote_algorithm_tree
manifest={}
for line in git('ls-tree','-r','HEAD',prefix).splitlines():
    meta,name=line.split('\t');expected=meta.split()[2]
    rel=name[len(prefix):];data=(ROOT/'vendor/fpga-sha512crypt'/rel).read_bytes()
    candidates=[data,data.replace(b'\r\n',b'\n')]
    hashes=[hashlib.sha1(b'blob '+str(len(item)).encode()+b'\0'+item).hexdigest() for item in candidates]
    assert expected in hashes,(rel,hashes,expected)
    blob=expected
    manifest[rel]=dict(git_blob_sha1=blob,sha256=hashlib.sha256(data).hexdigest())
report=dict(repository='https://github.com/gengleizhu/john',ref='bleeding-jumbo',
    cached_commit=git('rev-parse','HEAD'),algorithm_tree=remote_algorithm_tree,
    files_checked=len(manifest),files=manifest)
(ROOT/'reports/source_provenance.json').write_text(json.dumps(report,indent=2))
print('SOURCE_MATCH_PASS files='+str(len(manifest)))
