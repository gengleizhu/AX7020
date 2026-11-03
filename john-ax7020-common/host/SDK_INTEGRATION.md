# AX7020 Python SDK integration guide

## Public entry point

```python
from john_fpga_client import JohnFpgaClient, prepare_batch

prepared = prepare_batch(
    "md5crypt",
    ["123456", "password"],
    target="$1$salt1234$HJCsv4hSeVLHo3hVyl4nh0",
    task_id=1001,
    shard_id=0,
    batch_id=1,
)

with JohnFpgaClient("169.254.173.138") as client:
    result = client.execute(prepared)
```

`prepare_batch()` is the only task builder required by the upper-layer
software.  It selects the native codec, validates the target and candidate
lengths, pads fixed-size hardware batches, assigns native job IDs and wraps the
payload in the common DMA header.

## Algorithm limits

| Algorithm | ID | Candidates per batch | Required input |
|---|---:|---:|---|
| bcrypt8 | 1 | 1..170 | full `$2a$/$2b$/$2x$/$2y$` target |
| descrypt8 | 2 | 1..128 | full 13-character DES-crypt target |
| md5crypt8 | 3 | 1..96 | full `$1$` target, or `salt=` |
| sha256crypt8 | 4 | 1..96 | full `$5$` target, or `salt=` and `rounds=` |
| sha512crypt4 | 5 | 1..64 | full `$6$` target, or `salt=` and `rounds=` |

Fixed-size native batches are padded internally.  Padding records are removed
before results are returned.  DES hardware comparison is provisional; the SDK
uses `passlib` for full verification before setting `matched=True`.

## Result dictionary

`execute()` returns:

- `algorithm`, `algorithm_name`;
- `task_id`, `shard_id`, `batch_id`;
- final `status` (ABI, loaded algorithm, PL status, completed count and cycles);
- `records`, in the same order as the submitted valid candidates;
- `matches`, containing only fully verified records.

The API intentionally returns only final task status.  Heartbeat and board
health remain separate calls:

```python
client.heartbeat()
client.health()
client.capabilities()
```

The low-level transport also exposes `submit`, `wait`, `fetch`, `release` and
`cancel` for a scheduler that needs explicit queue ownership.

## Authenticated remote Bitstream switching

The management plane uses UDP port `42001`; task data stays on port `42000`.
It is a separate daemon, so it remains available while `john-node` and the DMA
driver are restarted.  Requests and responses use HMAC-SHA256, timestamps and
single-use nonces.  The caller supplies only an algorithm ID/name; the board
resolves it to a validated manifest under `/etc/john/bitstreams`.  Arbitrary
firmware paths are not accepted.

Generate a different 256-bit key for each deployment:

```sh
openssl rand -hex 32 > john-management.key
chmod 600 john-management.key
# Copy it to /media/sd-mmcblk0p1/john-management.key on the board.
/etc/init.d/john-manage restart
```

Then the upper layer can explicitly switch or let `execute()` switch when the
loaded algorithm differs:

```python
with JohnFpgaClient(board_ip, management_key="john-management.key") as client:
    client.switch_algorithm("sha512crypt")
    result = client.execute(prepared, auto_switch=True)
```

After a failed transition, normal admission remains closed.  An operator can
request the existing explicit recovery path with
`switch_algorithm(name, recover=True)`.  Full failure details remain in
`john-manage.log`/`john-node.log`; the remote API returns only a stable error
code.

## Dependencies and examples

- Python 3.8 or newer is recommended on the upper computer.
- `passlib` is required for final DES-crypt verification.
- Complete runnable examples are under `host/examples/`.
- The current protocol is IPv4 UDP and does not encrypt task contents.  Use an
  isolated or otherwise trusted network; HMAC protects management commands,
  not the data-plane payload.
