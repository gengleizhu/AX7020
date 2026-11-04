"""Two real nodes execute distinct shards of one known-answer task."""
import concurrent.futures
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from john_fpga_client import JohnFpgaClient, prepare_batch

TARGET = '$1$salt1234$HJCsv4hSeVLHo3hVyl4nh0'


def run_shard(host, shard, words):
    with JohnFpgaClient(host) as client:
        prepared = prepare_batch('md5crypt', words, target=TARGET,
                                 task_id=2026110401, shard_id=shard, batch_id=1)
        result = client.execute(prepared)
        return {'host': host, 'shard': shard, 'result': result}


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_shard, '169.254.173.138', 0, ['bad', '123456']),
                   pool.submit(run_shard, '169.254.173.139', 1, ['password', 'test'])]
        results = [future.result(timeout=30) for future in futures]
    matches = [r for node in results for r in node['result']['matches']]
    assert len(matches) == 1 and matches[0]['candidate'] == 'password'
    assert sum(len(node['result']['records']) for node in results) == 4
    print(json.dumps({'passed': True, 'shards': results}, indent=2))
