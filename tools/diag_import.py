import sys
import os
import importlib
print('cwd:', os.getcwd())
print('sys.path[0]:', sys.path[0])
print('is phase6 dir present?:', os.path.isdir('phase6'))
print('first 8 sys.path entries:')
for p in sys.path[:8]:
    print(' -', p)
try:
    m = importlib.import_module('phase6')
    print('imported phase6 ok; __file__=', getattr(m, '__file__', None))
except Exception as e:
    print('import failed:', type(e).__name__, e)
    # list current directory contents for debugging
    print('cwd listing:')
    print('\n'.join(os.listdir('.')))
    raise
