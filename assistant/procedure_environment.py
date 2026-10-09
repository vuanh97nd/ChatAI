"""Read the executable version of a local scripting listener without launching apps."""
import os


def file_version(path):
    import ctypes
    from ctypes import wintypes
    version=ctypes.WinDLL('version',use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(wintypes.DWORD)]
    version.GetFileVersionInfoSizeW.restype=wintypes.DWORD
    version.GetFileVersionInfoW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID]
    version.GetFileVersionInfoW.restype=wintypes.BOOL
    version.VerQueryValueW.argtypes=[wintypes.LPCVOID,wintypes.LPCWSTR,ctypes.POINTER(wintypes.LPVOID),ctypes.POINTER(wintypes.UINT)]
    version.VerQueryValueW.restype=wintypes.BOOL
    handle=wintypes.DWORD();size=version.GetFileVersionInfoSizeW(path,ctypes.byref(handle))
    if not size:return None
    data=ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(path,0,size,data):return None
    pointer=wintypes.LPVOID();length=wintypes.UINT()
    if not version.VerQueryValueW(data,'\\',ctypes.byref(pointer),ctypes.byref(length)) or length.value<13*4:return None
    info=ctypes.cast(pointer,ctypes.POINTER(wintypes.DWORD))
    if info[0]!=0xFEEF04BD:return None
    return '.'.join(str(n) for n in (info[2]>>16,info[2]&0xffff,info[3]>>16,info[3]&0xffff))


def plaxis_environment(version,port):
    fallback='PLAXIS '+version+' / unknown version'
    if os.name!='nt':return fallback
    try:
        import psutil
        for connection in psutil.net_connections(kind='tcp'):
            if connection.status!='LISTEN' or not connection.laddr or connection.laddr.port!=port or not connection.pid:continue
            process=psutil.Process(connection.pid);name=process.name().casefold()
            if 'plaxis' not in name:return fallback
            observed='3d' if '3d' in name else '2d' if '2d' in name else version
            executable=process.exe();number=file_version(executable)
            if number:return 'PLAXIS '+observed+' '+number
    except (OSError,ImportError,AttributeError,ValueError):pass
    except Exception:pass  # Access denied/version metadata unavailable => no cross-version assumption.
    return fallback
