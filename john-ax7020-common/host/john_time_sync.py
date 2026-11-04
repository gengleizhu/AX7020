"""Set a directly connected board's UTC clock over verified OpenSSH."""
from datetime import datetime, timezone
from pathlib import Path
import subprocess


def sync_time(host, identity_file, known_hosts_file, user='root', timeout=15):
    """Requires a provisioned login key, pinned host key and noninteractive auth.

    An encrypted key must be unlocked in ssh-agent or via the deployment's
    SSH_ASKPASS mechanism. Credentials are never passed on the command line.
    """
    if not host or host.startswith('-') or not user or user.startswith('-'):
        raise ValueError('invalid SSH destination')
    identity = str(Path(identity_file).resolve(strict=True))
    known = str(Path(known_hosts_file).resolve(strict=True))
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    command = ['ssh', '-i', identity, '-o', 'IdentitiesOnly=yes',
               '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=5',
               '-o', 'HostKeyAlgorithms=+ssh-rsa',
               '-o', 'PubkeyAcceptedAlgorithms=+ssh-rsa',
               '-o', 'UserKnownHostsFile=' + known,
               user + '@' + host, "date -u -s '" + stamp + "'"]
    result = subprocess.run(command, check=True, capture_output=True,
                            text=True, timeout=timeout)
    return {'host': host, 'utc_requested': stamp,
            'board_reply': result.stdout.strip()}
