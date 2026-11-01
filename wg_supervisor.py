"""Elevated, memory-only supervisor for the RoutePou Windows WireGuard worker.

The controller creates a one-session local named pipe, launches the worker with
UAC elevation, sends its IPC config through that pipe, and keeps the handle open
until disconnect. No private key is written to disk, argv, or logs.
"""
from __future__ import annotations

import ctypes
import os
import secrets
import threading
import time
from ctypes import wintypes
from pathlib import Path

class WorkerError(RuntimeError):
    pass

class WindowsWireGuardSession:
    PIPE_ACCESS_DUPLEX = 0x00000003
    PIPE_TYPE_BYTE = 0x00000000
    PIPE_READMODE_BYTE = 0x00000000
    PIPE_WAIT = 0x00000000
    PIPE_UNLIMITED_INSTANCES = 255
    ERROR_PIPE_CONNECTED = 535
    ERROR_MORE_DATA = 234
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    def __init__(self, worker_path: str | os.PathLike, *, on_status=None, on_exit=None):
        self.worker_path = Path(worker_path)
        self.on_status = on_status or (lambda _line: None)
        self.on_exit = on_exit or (lambda _reason: None)
        self._handle = None
        self._pipe_name = None
        self._lock = threading.Lock()
        self._connected = False
        self._kernel32 = None
        self._monitor_thread = None
        self._closing = threading.Event()

    def _api(self):
        if os.name != "nt":
            raise WorkerError("تونل کامل RoutePou فقط روی Windows 10/11 قابل اجراست.")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
        self._kernel32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
            wintypes.DWORD, wintypes.LPVOID]
        self._kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
        self._kernel32.ConnectNamedPipe.restype = wintypes.BOOL
        self._kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        self._kernel32.WriteFile.restype = wintypes.BOOL
        self._kernel32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        self._kernel32.ReadFile.restype = wintypes.BOOL
        self._kernel32.PeekNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
            wintypes.DWORD, wintypes.LPVOID, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        self._kernel32.PeekNamedPipe.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    def _write(self, data: bytes):
        offset = 0
        while offset < len(data):
            written = wintypes.DWORD()
            chunk = data[offset:offset + 4096]
            buf = ctypes.create_string_buffer(chunk)
            ok = self._kernel32.WriteFile(self._handle, buf, len(chunk), ctypes.byref(written), None)
            if not ok or written.value == 0:
                raise WorkerError(f"ارسال تنظیمات به موتور WireGuard ناموفق بود (WinError {ctypes.get_last_error()}).")
            offset += written.value

    def _read_line(self, timeout_seconds=30):
        result = bytearray()
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            available = wintypes.DWORD()
            ok = self._kernel32.PeekNamedPipe(self._handle, None, 0, None, ctypes.byref(available), None)
            if not ok:
                code = ctypes.get_last_error()
                raise WorkerError(f"ارتباط با موتور WireGuard قطع شد (WinError {code}).")
            if available.value == 0:
                time.sleep(0.05)
                continue
            buf = ctypes.create_string_buffer(1)
            read = wintypes.DWORD()
            ok = self._kernel32.ReadFile(self._handle, buf, 1, ctypes.byref(read), None)
            if not ok:
                code = ctypes.get_last_error()
                if code == self.ERROR_MORE_DATA:
                    continue
                raise WorkerError(f"خواندن پاسخ موتور WireGuard ناموفق بود (WinError {code}).")
            if read.value:
                byte = buf.raw[:1]
                if byte == b"\n":
                    line = result.decode("utf-8", "replace").strip()
                    self.on_status(line)
                    return line
                if byte != b"\r":
                    result.extend(byte)
                if len(result) > 2048:
                    raise WorkerError("پاسخ موتور WireGuard بیش از حد طولانی است.")
        raise WorkerError("در زمان تعیین‌شده پاسخی از موتور WireGuard دریافت نشد.")

    def start(self, ipc_config: str, *, dns: str = "1.1.1.1"):
        if self._connected or self._handle:
            raise WorkerError("یک تونل RoutePou از قبل فعال است.")
        if not self.worker_path.is_file():
            raise WorkerError("فایل موتور ویندوز relaywg-client.exe در بسته برنامه پیدا نشد.")
        if not ipc_config.endswith("\n") or "private_key=" not in ipc_config:
            raise WorkerError("تنظیمات امن WireGuard نامعتبر است.")
        # Accept only a literal IP for DNS; never pass arbitrary shell text.
        import ipaddress
        try:
            dns = str(ipaddress.ip_address(dns))
        except ValueError as exc:
            raise WorkerError("نشانی DNS نامعتبر است.") from exc
        self._api()
        self._pipe_name = "RoutePou-" + secrets.token_hex(16)
        pipe_path = "\\\\.\\pipe\\" + self._pipe_name
        self._handle = self._kernel32.CreateNamedPipeW(
            pipe_path, self.PIPE_ACCESS_DUPLEX,
            self.PIPE_TYPE_BYTE | self.PIPE_READMODE_BYTE | self.PIPE_WAIT,
            1, 65536, 65536, 0, None)
        if self._handle == self.INVALID_HANDLE_VALUE:
            self._handle = None
            raise WorkerError(f"ساخت کانال امن ناموفق بود (WinError {ctypes.get_last_error()}).")

        # ShellExecute 'runas' is intentionally used for adapter/routes. The
        # private configuration is delivered only after elevation over the pipe.
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        shell32.ShellExecuteW.restype = wintypes.HINSTANCE
        shell32.ShellExecuteW.argtypes = [wintypes.HWND, wintypes.LPCWSTR,
            wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int]
        args = f'-name "RoutePou" -address 10.13.37.2/32 -dns {dns} -routes 0.0.0.0/0 -config-pipe={self._pipe_name} -block-leaks=true -hold-on-loss=true'
        result = shell32.ShellExecuteW(None, "runas", str(self.worker_path), args, str(self.worker_path.parent), 0)
        if ctypes.cast(result, ctypes.c_void_p).value <= 32:
            self.close()
            raise WorkerError("اجرای مدیر سیستم لغو شد یا موتور ویندوز اجرا نشد.")

        connected = self._kernel32.ConnectNamedPipe(self._handle, None)
        if not connected and ctypes.get_last_error() != self.ERROR_PIPE_CONNECTED:
            code = ctypes.get_last_error()
            self.close()
            raise WorkerError(f"اتصال موتور به کانال امن ناموفق بود (WinError {code}).")

        self._write((ipc_config + "END-CONFIG\n").encode("ascii"))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            line = self._read_line(max(1, int(deadline - time.monotonic())))
            if line == "READY":
                self._connected = True
                self._monitor_thread = threading.Thread(target=self._monitor_worker, name="RoutePou-WG-monitor", daemon=True)
                self._monitor_thread.start()
                return
            if line == "NO-HANDSHAKE":
                self.close()
                raise WorkerError("گوشی پاسخ WireGuard نداد. هات‌اسپات را بررسی و QR تازه تولید کنید.")
            if line == "LEAK-PROTECTION-FAILED":
                self.close()
                raise WorkerError("محافظت نشت ترافیک در ویندوز فعال نشد؛ برای جلوگیری از اتصال ناامن، تونل لغو شد.")
        self.close()
        raise WorkerError("تونل در مهلت مقرر Handshake انجام نداد.")

    def _monitor_worker(self):
        """Consume post-READY worker events so the UI cannot stay falsely connected."""
        reason = "worker channel closed"
        try:
            while not self._closing.is_set():
                line = self._read_line(timeout_seconds=86400)
                # _read_line already dispatches each line to on_status.
                # Keep consuming the pipe; the callback owns presentation.
                _ = line
        except WorkerError as exc:
            if not self._closing.is_set():
                reason = str(exc)
        finally:
            was_connected = self._connected
            self._connected = False
            if was_connected and not self._closing.is_set():
                self.on_exit(reason)

    def close(self):
        self._closing.set()
        with self._lock:
            handle, self._handle = self._handle, None
            self._connected = False
        if handle and self._kernel32:
            self._kernel32.CloseHandle(handle)

    @property
    def connected(self):
        return self._connected
