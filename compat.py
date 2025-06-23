# compat.py - должен быть в том же каталоге
import sys
from types import ModuleType

class FakeCGI(ModuleType):
    def __getattr__(self, name):
        return None

sys.modules['cgi'] = FakeCGI('cgi')