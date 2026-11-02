"""Python audit guard for trusted R01 runners; no production offline_guard import.

Defense in depth, not an OS sandbox. AST parsing uses an existing native library.
No C compilation/runtime execution is performed.
"""
import sys

EVENTS = []


def install():
    def guard(event, args):
        forbidden = ((event.startswith('socket.') and event != 'socket.gethostname') or event.startswith('urllib.') or
                     event in {'subprocess.Popen', 'os.system', 'os.exec', 'os.spawn',
                               'os.startfile', 'webbrowser.open'})
        if forbidden:
            EVENTS.append({'event': event, 'blocked': True})
            raise RuntimeError('R01 forbidden external operation: ' + event)
    sys.addaudithook(guard)
