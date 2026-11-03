# AX7020 Python Integration Kit v3

This package contains the unified five-algorithm Python SDK, complete runnable
examples, algorithm codecs and protocol documents for upper-layer integration.

## Quick start

1. Install Python 3.8 or newer and `pip install -r requirements.txt`.
2. Open `src/john-ax7020-common/host/examples`.
3. With the matching algorithm already loaded, run:

   ```sh
   python run_md5crypt.py --host 169.254.173.138
   ```

4. To permit automatic algorithm switching, provision a unique management key
   as described in `src/john-ax7020-common/host/SDK_INTEGRATION.md`, then run:

   ```sh
   python run_sha256crypt.py --host 169.254.173.138 \
     --management-key /path/to/john-management.key
   ```

The stable public entry points are `prepare_batch()` and `JohnFpgaClient` in
`john_fpga_client.py`.  Applications do not need to construct `<16I` headers or
native FPGA payloads themselves.

## Contents

- `src/`: importable SDK and all five algorithm codecs;
- `src/john-ax7020-common/host/examples/`: five task examples plus switching;
- `docs/`: Chinese software-integration PDF documents;
- `requirements.txt`: host dependency list.

The data plane uses UDP 42000.  The authenticated management plane uses UDP
42001.  Management authentication does not encrypt task contents, so deploy the
two-node system on a trusted or isolated network.
