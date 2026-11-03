# AX7020 five-algorithm Python examples

All five examples use the same public API:

```python
prepared = prepare_batch("sha256crypt", candidates, target=target_hash)
with JohnFpgaClient(board_ip, management_key="john-management.key") as client:
    result = client.execute(prepared, auto_switch=True)
```

Data-plane UDP uses port `42000`.  Authenticated Bitstream management uses the
independent port `42001`; it is optional when the required algorithm is already
loaded.

Before enabling remote switching, generate a unique key and place the same file
on the SD card and trusted host:

```sh
openssl rand -hex 32 > john-management.key
# board path: /media/sd-mmcblk0p1/john-management.key
/etc/init.d/john-manage restart
```

Run an example from this directory:

```sh
python run_md5crypt.py --host 169.254.173.138
python run_sha256crypt.py --host 169.254.173.138 --management-key john-management.key
python switch_algorithm.py bcrypt --host 169.254.173.138 --key john-management.key
```

The returned dictionary contains task identity, final hardware status, all
decoded records and a `matches` list.  DES provisional matches are never
reported as final matches until full `passlib` verification succeeds.
