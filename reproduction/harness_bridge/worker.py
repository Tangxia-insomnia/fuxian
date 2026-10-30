"""Keep original Git/context code off the live MCP stdin pipe.

Each retrieval runs in a local child with stdin=DEVNULL and a small environment.
Only validated dataset/name/position arguments cross this boundary. No model.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

from tools import BridgeError, RetrievalTools, validate


class RetrievalWorker:
    def invoke(self, name, arguments):
        try:
            validate(name, arguments)
        except BridgeError as exc:
            return exc.payload
        keep = {'PATH', 'SYSTEMROOT', 'WINDIR', 'SYSTEMDRIVE', 'COMSPEC', 'PATHEXT',
                'TEMP', 'TMP', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'APPDATA', 'LOCALAPPDATA'}
        env = {k: v for k, v in os.environ.items() if k.upper() in keep}
        env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', GIT_TERMINAL_PROMPT='0')
        try:
            result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), name,
                                     json.dumps(arguments, ensure_ascii=True)],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    cwd=Path(__file__).resolve().parent, env=env, timeout=30,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode:
                return BridgeError('WORKER_FAILED', 'Local retrieval worker exited unsuccessfully.',
                                   {'returncode': result.returncode}).payload
            payload = json.loads(result.stdout.decode('utf-8'))
            if not isinstance(payload, dict) or type(payload.get('ok')) is not bool:
                raise ValueError('invalid_worker_envelope')
            return payload
        except subprocess.TimeoutExpired:
            return BridgeError('RETRIEVAL_TIMEOUT', 'Local retrieval exceeded the 30-second limit.').payload
        except (OSError, ValueError) as exc:
            return BridgeError('WORKER_FAILED', 'Cannot start or decode local retrieval worker.',
                               {'exception_type': type(exc).__name__}).payload


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    if len(sys.argv) != 3:
        raise SystemExit('Internal worker expects a tool name and JSON arguments.')
    response = RetrievalTools().invoke(sys.argv[1], json.loads(sys.argv[2]))
    sys.stdout.write(json.dumps(response, ensure_ascii=True) + '\n')
