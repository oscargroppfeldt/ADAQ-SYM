import os
from functools import lru_cache
from tkinter import N
from shutil import which

@lru_cache(maxsize=None)
def _detect():
    override = os.getenv("ADAQ_SYM_BACKEND")
    if override in ("aflow", "spglib"):
        return override
    
    if which("aflow"):
        try:
            import aflow_sym_python
            return "aflow"
        except ImportError:
            return "aflow" # Python bindingar are not used, but aflow binary is available
    
    try:
        import spglib
        return "spglib"
    except ImportError:
        return "none"
    
def backend_name():
    return _detect()

def is_aflow():
    return _detect() == "aflow"

def is_spglib():
    return _detect() == "spglib"

@lru_cache(maxsize=None)
def get_Symmetry():
    if not is_aflow():
        return None
    from aflow_sym_python import Symmetry
    return Symmetry

@lru_cache(maxsize=None)
def get_spglib():
    if not is_spglib():
        return None
    import spglib
    return spglib