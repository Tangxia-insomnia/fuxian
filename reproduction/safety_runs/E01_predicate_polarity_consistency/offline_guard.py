"""Fail closed on network, model imports, subprocesses or writes outside E01.

Python audit hooks are a runtime tripwire, not an OS sandbox or a C proof.
The experiment never executes saved model-generated Python.
"""
import os
from pathlib import Path
import sys

VIOLATIONS = []


def install(directory):
    allowed = Path(directory).resolve()
    blocked_imports = {'completion', 'openai', 'requests', 'httpx', 'aiohttp', 'litellm'}

    def deny(event, reason):
        VIOLATIONS.append({'event': event, 'reason': reason})
        raise RuntimeError('E01_OFFLINE_GUARD:' + reason)

    def permitted_write(value):
        if isinstance(value, int) or value is None:
            return
        path = Path(os.fsdecode(value)).resolve()
        if path != allowed and allowed not in path.parents:
            deny('filesystem_mutation', 'write_outside_experiment_directory')

    def hook(event, args):
        if event.startswith('socket.') or event in ('http.client.connect', 'urllib.Request'):
            deny(event, 'network_forbidden')
        if event.startswith('subprocess.') or event in ('os.system', 'os.spawn', 'os.exec'):
            deny(event, 'subprocess_forbidden')
        if event == 'import' and args[0].split('.')[0] in blocked_imports:
            deny(event, 'model_or_online_client_import_forbidden')
        if event == 'open':
            path, mode, flags = args
            if not isinstance(path, int) and Path(os.fsdecode(path)).name == '.env':
                deny(event, 'credential_file_read_forbidden')
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                    isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                permitted_write(path)
        if event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.utime'):
            permitted_write(args[0])
        if event in ('os.rename', 'os.link', 'os.symlink'):
            permitted_write(args[0])
            permitted_write(args[1])

    sys.addaudithook(hook)
    return VIOLATIONS
