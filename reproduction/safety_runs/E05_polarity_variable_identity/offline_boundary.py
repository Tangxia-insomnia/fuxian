"""Fail closed if an offline replay attempts network, child process or Z3 import."""
import importlib.abc
import os
import socket
import subprocess
import sys

ATTEMPTS = []


def deny(*args, **kwargs):
    ATTEMPTS.append('forbidden_runtime_operation')
    raise RuntimeError('STOP: E05 offline boundary violation')


class NoLiveModules(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'z3', 'openai', 'requests', 'httpx'} or fullname in {
                'completion.engine', 'completion.model', 'completion.solver_worker'}:
            ATTEMPTS.append('forbidden_import:' + fullname)
            raise RuntimeError('STOP: E05 forbidden live/solver import')
        return None


def install():
    if any(name.split('.')[0] in {'z3', 'openai'} for name in sys.modules):
        raise RuntimeError('STOP: solver/model already imported')
    sys.meta_path.insert(0, NoLiveModules())
    socket.socket = socket.create_connection = socket.getaddrinfo = deny
    subprocess.Popen = subprocess.run = subprocess.call = subprocess.check_call = subprocess.check_output = deny
    os.system = os.popen = deny
