"""RoutePou Windows companion: authenticated HTTP and SOCKS5 TCP bridges."""
import atexit, socket, ssl, hashlib, hmac, threading, tkinter as tk, sys
from pathlib import Path
from pairing import parse_pairing_payload, describe_connect_error
from proxy_headers import rewrite_request_head
from wg_provision import parse_qr_to_windows_ipc
from wg_supervisor import WindowsWireGuardSession, WorkerError
from tkinter import messagebox
import winreg
from tkinter import filedialog

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
LOCAL_HOST, LOCAL_HTTP_PORT, LOCAL_SOCKS_PORT = "127.0.0.1", 17878, 17879
PHONE_PORT_DEFAULT = "8788"
APP_VERSION = "0.27.0-beta"
http_server = None
socks_server = None
wg_session = None
full_tunnel_ipc = None
full_tunnel_meta = None
stop_event = threading.Event()
previous = {}
active_sockets = set()
socket_lock = threading.Lock()




def read_reg(name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH) as k:
            return winreg.QueryValueEx(k, name)
    except OSError:
        return None


def write_reg(name, value, typ):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH) as k:
        winreg.SetValueEx(k, name, 0, typ, value)


def refresh_windows():
    try:
        import ctypes
        ctypes.windll.Wininet.InternetSetOptionW(0, 39, 0, 0)
        ctypes.windll.Wininet.InternetSetOptionW(0, 37, 0, 0)
    except Exception:
        pass


def track(sock):
    with socket_lock:
        active_sockets.add(sock)


def untrack(sock):
    with socket_lock:
        active_sockets.discard(sock)


def relay(a, b):
    def cp(src, dst):
        try:
            while not stop_event.is_set():
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass
    t1 = threading.Thread(target=cp, args=(a, b), daemon=True)
    t2 = threading.Thread(target=cp, args=(b, a), daemon=True)
    t1.start(); t2.start(); t1.join(); t2.join()


def recv_exact(sock, count):
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise ConnectionError("Unexpected end of SOCKS5 handshake")
        data.extend(chunk)
    return bytes(data)


def tls_phone_socket(phone, port, fingerprint):
    raw = socket.create_connection((phone, int(port)), timeout=12)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # Trust is established by the explicit SHA-256 pin below.
    wrapped = context.wrap_socket(raw, server_hostname="routepou.local")
    actual = hashlib.sha256(wrapped.getpeercert(binary_form=True)).hexdigest().upper()
    expected = "".join(ch for ch in fingerprint.upper() if ch in "0123456789ABCDEF")
    if len(expected) != 64 or not hmac.compare_digest(actual, expected):
        wrapped.close()
        raise ssl.SSLError("TLS certificate fingerprint mismatch. Verify the fingerprint shown by the Android app.")
    return wrapped


def handle_http_client(client, phone, port, token, fingerprint):
    upstream = None
    track(client)
    try:
        client.settimeout(30)
        data = bytearray()
        while b"\r\n\r\n" not in data and len(data) < 32768:
            part = client.recv(4096)
            if not part:
                return
            data.extend(part)
        if b"\r\n\r\n" not in data:
            return
        head, rest = bytes(data).split(b"\r\n\r\n", 1)
        rewritten = rewrite_request_head(head, token)
        upstream = tls_phone_socket(phone, port, fingerprint)
        track(upstream)
        upstream.sendall(rewritten + b"\r\n\r\n" + rest)
        client.settimeout(None); upstream.settimeout(None)
        relay(client, upstream)
    except OSError:
        pass
    finally:
        for s in (client, upstream):
            if s:
                untrack(s)
                try: s.close()
                except OSError: pass


def handle_socks_client(client, phone, port, token, fingerprint):
    """Local unauthenticated SOCKS5 endpoint; authenticates to phone using RFC1929."""
    upstream = None
    track(client)
    try:
        client.settimeout(30)
        ver, nmethods = recv_exact(client, 2)
        if ver != 5 or nmethods < 1:
            return
        recv_exact(client, nmethods)
        # Local apps connect to loopback only; the bridge performs phone-side auth.
        client.sendall(b"\x05\x00")
        upstream = tls_phone_socket(phone, port, fingerprint)
        track(upstream); upstream.settimeout(30)
        upstream.sendall(b"\x05\x01\x02")
        if recv_exact(upstream, 2) != b"\x05\x02":
            client.sendall(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")
            return
        user = b"routepou"; pwd = token.encode("ascii")
        upstream.sendall(b"\x01" + bytes([len(user)]) + user + bytes([len(pwd)]) + pwd)
        if recv_exact(upstream, 2) != b"\x01\x00":
            client.sendall(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")
            return
        request_head = recv_exact(client, 4)
        atyp = request_head[3]
        if atyp == 1:
            address = recv_exact(client, 4)
        elif atyp == 3:
            size = recv_exact(client, 1)
            address = size + recv_exact(client, size[0])
        elif atyp == 4:
            address = recv_exact(client, 16)
        else:
            client.sendall(b"\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00")
            return
        request = request_head + address + recv_exact(client, 2)
        upstream.sendall(request)
        reply = recv_exact(upstream, 4)
        atyp_reply = reply[3]
        if atyp_reply == 1:
            reply += recv_exact(upstream, 6)
        elif atyp_reply == 4:
            reply += recv_exact(upstream, 18)
        elif atyp_reply == 3:
            n = recv_exact(upstream, 1); reply += n + recv_exact(upstream, n[0] + 2)
        client.sendall(reply)
        if reply[1] == 0:
            client.settimeout(None); upstream.settimeout(None)
            relay(client, upstream)
    except (OSError, ConnectionError, IndexError):
        pass
    finally:
        for s in (client, upstream):
            if s:
                untrack(s)
                try: s.close()
                except OSError: pass


def server_loop(host, local_port, handler, phone, phone_port, token, fingerprint):
    global http_server, socks_server
    server = socket.socket(); server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, local_port)); server.listen(64); server.settimeout(1)
    if local_port == LOCAL_HTTP_PORT: http_server = server
    else: socks_server = server
    while not stop_event.is_set():
        try: client, _ = server.accept()
        except socket.timeout: continue
        except OSError: break
        threading.Thread(target=handler, args=(client, phone, phone_port, token, fingerprint), daemon=True).start()
    try: server.close()
    except OSError: pass
    if local_port == LOCAL_HTTP_PORT: http_server = None
    else: socks_server = None


def start_bridges(phone, port, token, fingerprint):
    stop_event.clear()
    threading.Thread(target=server_loop, args=(LOCAL_HOST, LOCAL_HTTP_PORT, handle_http_client, phone, port, token, fingerprint), daemon=True).start()
    threading.Thread(target=server_loop, args=(LOCAL_HOST, LOCAL_SOCKS_PORT, handle_socks_client, phone, port, token, fingerprint), daemon=True).start()


def connect():
    if http_server or socks_server or getattr(connect, "busy", False):
        return
    phone = ip.get().strip(); token = key_var.get().strip(); port = port_var.get().strip(); fingerprint = fingerprint_var.get().strip()
    try:
        if not phone:
            raise ValueError("ابتدا QR را اسکن کنید یا IP گوشی را وارد کنید.")
        socket.inet_aton(phone)
        if not token or len(token) < 16 or not port.isdigit() or not 1 <= int(port) <= 65535 or len("".join(c for c in fingerprint if c in "0123456789abcdefABCDEF")) != 64:
            raise ValueError("اطلاعات Pairing ناقص یا نامعتبر است. کد اتصال را دوباره وارد کنید.")
    except Exception as exc:
        messagebox.showerror("اطلاعات اتصال", str(exc))
        return

    connect.busy = True
    connect_button.configure(state="disabled")
    set_status("در حال بررسی اتصال به گوشی…", "working")

    def worker():
        try:
            test = tls_phone_socket(phone, port, fingerprint)
            test.close()
            start_bridges(phone, port, token, fingerprint)
            for name in ("ProxyEnable", "ProxyServer", "ProxyOverride"):
                previous[name] = read_reg(name)
            write_reg("ProxyEnable", 1, winreg.REG_DWORD)
            write_reg("ProxyServer", f"http={LOCAL_HOST}:{LOCAL_HTTP_PORT};https={LOCAL_HOST}:{LOCAL_HTTP_PORT}", winreg.REG_SZ)
            write_reg("ProxyOverride", "localhost;127.*;<local>", winreg.REG_SZ)
            refresh_windows()
            root.after(0, lambda: set_status("متصل به گوشی · پراکسی ویندوز فعال است", "connected"))
        except Exception as exc:
            stop_event.set()
            root.after(0, lambda err=describe_connect_error(exc): (set_status("اتصال برقرار نشد", "error"), messagebox.showerror("RoutePou", err)))
        finally:
            connect.busy = False
            root.after(0, lambda: connect_button.configure(state="normal"))
    threading.Thread(target=worker, daemon=True).start()


def disconnect():
    global http_server, socks_server
    stop_event.set()
    for srv in (http_server, socks_server):
        if srv:
            try: srv.close()
            except OSError: pass
    with socket_lock:
        sockets = list(active_sockets)
    for sock in sockets:
        try: sock.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        try: sock.close()
        except OSError: pass
    for name, old in previous.items():
        try:
            if old is None:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.DeleteValue(k, name)
            else:
                write_reg(name, old[0], old[1])
        except OSError:
            pass
    previous.clear(); refresh_windows()
    set_status("قطع اتصال · تنظیمات قبلی ویندوز بازیابی شد", "idle")


# ---------------------------------------------------------------------------
# RoutePou Windows companion UI — redesigned for clarity and everyday use.
# This client currently provides the authenticated TLS HTTP/SOCKS5 proxy bridge;
# it does not claim to provide a full-device WireGuard tunnel yet.
# ---------------------------------------------------------------------------
root = tk.Tk()
root.title("RoutePou | اتصال گوشی به ویندوز")
root.geometry("780x820")
root.minsize(700, 740)
root.configure(bg="#0d0a0f")
root.resizable(True, True)

DARK_COLORS = {
    "bg": "#0d0a0f", "panel": "#1f141c", "panel2": "#2b1924",
    "text": "#fff7fb", "muted": "#bea6b4", "accent": "#961941",
    "accent_hover": "#b52b58", "green": "#36c995", "yellow": "#e7b75b",
    "red": "#ff6b7d", "border": "#513044", "input": "#170e14"
}
LIGHT_COLORS = {
    "bg": "#f8f4f7", "panel": "#ffffff", "panel2": "#f0e5eb",
    "text": "#291923", "muted": "#705363", "accent": "#851238",
    "accent_hover": "#a51e4d", "green": "#167a56", "yellow": "#916000",
    "red": "#b5223e", "border": "#ddc7d2", "input": "#fffafd"
}
DARK_MODE = True
COLORS = dict(DARK_COLORS)
FONT = "Segoe UI"

style = __import__("tkinter.ttk", fromlist=["ttk"]).Style(root)
try:
    style.theme_use("clam")
except Exception:
    pass
style.configure("Route.TEntry", fieldbackground=COLORS["input"], foreground=COLORS["text"],
                insertcolor=COLORS["text"], bordercolor=COLORS["border"], padding=10)

outer = tk.Frame(root, bg=COLORS["bg"])
outer.pack(fill="both", expand=True, padx=28, pady=24)

header = tk.Frame(outer, bg=COLORS["bg"])
header.pack(fill="x", pady=(0, 20))
brand = tk.Frame(header, bg=COLORS["bg"])
brand.pack(side="left", anchor="w")
tk.Label(brand, text="RoutePou", font=(FONT, 28, "bold"), fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")
tk.Label(brand, text="PHONE  →  WINDOWS", font=(FONT, 9, "bold"), fg=COLORS["muted"], bg=COLORS["bg"]).pack(anchor="w", pady=(2, 0))

def apply_theme():
    global DARK_MODE, COLORS
    old = dict(COLORS)
    DARK_MODE = not DARK_MODE
    COLORS = dict(DARK_COLORS if DARK_MODE else LIGHT_COLORS)
    reverse = {v: COLORS[k] for k, v in old.items()}
    def recolor(widget):
        try:
            bg = widget.cget("bg")
            if bg in reverse: widget.configure(bg=reverse[bg])
        except Exception: pass
        try:
            fg = widget.cget("fg")
            if fg in reverse: widget.configure(fg=reverse[fg])
        except Exception: pass
        for child in widget.winfo_children(): recolor(child)
    recolor(root)
    theme_button.configure(text="حالت روشن" if DARK_MODE else "حالت تاریک")

theme_button = tk.Button(header, text="حالت روشن", command=apply_theme, bg=COLORS["panel2"], fg=COLORS["text"],
                         activebackground=COLORS["border"], relief="flat", padx=12, pady=8, cursor="hand2")
theme_button.pack(side="right", anchor="n", padx=(8, 0))
tk.Label(header, text="BETA " + APP_VERSION.split("-")[0], font=(FONT, 9, "bold"), fg=COLORS["accent"], bg=COLORS["panel2"], padx=12, pady=7).pack(side="right", anchor="n")

status_card = tk.Frame(outer, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["border"])
status_card.pack(fill="x", pady=(0, 16))
status_inner = tk.Frame(status_card, bg=COLORS["panel"])
status_inner.pack(fill="x", padx=18, pady=16)
status_dot = tk.Label(status_inner, text="●", font=(FONT, 18), fg=COLORS["red"], bg=COLORS["panel"])
status_dot.pack(side="left", padx=(0, 12))
status_text_frame = tk.Frame(status_inner, bg=COLORS["panel"])
status_text_frame.pack(side="left", fill="x", expand=True)
tk.Label(status_text_frame, text="وضعیت اتصال", font=(FONT, 9), fg=COLORS["muted"], bg=COLORS["panel"]).pack(anchor="w")
status = tk.Label(status_text_frame, text="آماده اتصال", font=(FONT, 12, "bold"), fg=COLORS["text"], bg=COLORS["panel"])
status.pack(anchor="w", pady=(2, 0))


def set_status(message, state="idle"):
    palette = {"idle": COLORS["red"], "working": COLORS["yellow"], "connected": COLORS["green"], "error": COLORS["red"]}
    status.configure(text=message, fg=COLORS["text"] if state == "working" else palette.get(state, COLORS["red"]))
    status_dot.configure(fg=palette.get(state, COLORS["red"]))


def card(parent, title, subtitle=None):
    box = tk.Frame(parent, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["border"])
    tk.Label(box, text=title, font=(FONT, 12, "bold"), fg=COLORS["text"], bg=COLORS["panel"]).pack(anchor="w", padx=18, pady=(15, 2))
    if subtitle:
        tk.Label(box, text=subtitle, font=(FONT, 9), fg=COLORS["muted"], bg=COLORS["panel"], wraplength=650, justify="left").pack(anchor="w", padx=18, pady=(0, 10))
    return box

pair_card = card(outer, "۱. اتصال گوشی", "گوشی و ویندوز را به یک وای‌فای وصل کنید (هات‌اسپات لازم نیست)، VPN گوشی را روشن کنید و QR داخل برنامهٔ اندروید را اسکن کنید یا تصویر QR را انتخاب کنید. وارد کردن IP لازم نیست.")
pair_card.pack(fill="x", pady=(0, 14))
form = tk.Frame(pair_card, bg=COLORS["panel"])
form.pack(fill="x", padx=18, pady=(0, 16))

ip = tk.StringVar(value="")
port_var = tk.StringVar(value=PHONE_PORT_DEFAULT)
key_var = tk.StringVar()
fingerprint_var = tk.StringVar()
qr_var = tk.StringVar()

def make_field(parent, label, variable, *, secret=False, width=30):
    wrap = tk.Frame(parent, bg=COLORS["panel"])
    tk.Label(wrap, text=label, font=(FONT, 9, "bold"), fg=COLORS["muted"], bg=COLORS["panel"]).pack(anchor="w", pady=(7, 5))
    entry = tk.Entry(wrap, textvariable=variable, show="•" if secret else "", font=(FONT, 10),
                     bg=COLORS["input"], fg=COLORS["text"], insertbackground=COLORS["text"],
                     relief="flat", highlightthickness=1, highlightbackground=COLORS["border"],
                     highlightcolor=COLORS["accent"], width=width)
    entry.pack(fill="x", ipady=9)
    return wrap, entry

qr_wrap, qr_entry = make_field(form, "کد QR (ورود خودکار پس از اسکن یا Paste)", qr_var)
qr_wrap.pack(fill="x")

def import_pairing_qr():
    global full_tunnel_ipc, full_tunnel_meta
    payload = qr_var.get().strip()
    try:
        if payload.startswith("routepou://p/"):
            full_tunnel_ipc, full_tunnel_meta = parse_qr_to_windows_ipc(payload)
            set_status("QR معتبر است · در حال اتصال تونل…", "working")
            root.after(150, connect_full_tunnel)
            return
        host, qr_port, qr_key, qr_fp = parse_pairing_payload(payload)
        full_tunnel_ipc = None; full_tunnel_meta = None
        ip.set(host); port_var.set(qr_port); key_var.set(qr_key); fingerprint_var.set(qr_fp)
        set_status("QR معتبر است · در حال اتصال خودکار…", "working")
        root.after(150, connect)
    except Exception as exc:
        full_tunnel_ipc = None; full_tunnel_meta = None
        messagebox.showerror("کد اتصال نامعتبر", str(exc))


def connect_full_tunnel():
    global wg_session
    if not full_tunnel_ipc or not full_tunnel_meta:
        messagebox.showwarning("RoutePou", "ابتدا QR تونل کامل را از برنامه اندروید وارد کنید.")
        return
    if wg_session and wg_session.connected:
        return
    connect_button.configure(state="disabled")
    set_status("در حال درخواست دسترسی و برقراری تونل WireGuard…", "working")
    ipc = full_tunnel_ipc
    dns = full_tunnel_meta["dns"]
    def worker():
        global wg_session
        try:
            worker_path = Path(__file__).resolve().parent / "relaywg-client.exe"
            if getattr(sys, "frozen", False):
                worker_path = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "relaywg-client.exe"
            def worker_status(line):
                if line == "PEER-LOST":
                    root.after(0, lambda: set_status("ارتباط گوشی قطع شده · ترافیک مسدود می‌ماند", "error"))
                elif line == "PEER-BACK":
                    root.after(0, lambda: set_status("ارتباط گوشی بازیابی شد", "connected"))
                else:
                    root.after(0, lambda msg=line: set_status(msg, "working"))
            def worker_exit(reason):
                root.after(0, lambda: set_status("تونل متوقف شد · " + reason, "error"))
            session = WindowsWireGuardSession(worker_path, on_status=worker_status, on_exit=worker_exit)
            session.start(ipc, dns=dns)
            wg_session = session
            root.after(0, lambda: set_status("تونل فعال است · Handshake تأیید شد · مانیتورینگ ارتباط روشن است", "connected"))
        except Exception as exc:
            root.after(0, lambda err=str(exc): (set_status("تونل برقرار نشد", "error"), messagebox.showerror("RoutePou WireGuard", err)))
        finally:
            root.after(0, lambda: connect_button.configure(state="normal"))
    threading.Thread(target=worker, daemon=True).start()


def disconnect_full_tunnel():
    global wg_session
    if wg_session:
        wg_session.close()
        wg_session = None
    set_status("تونل کامل قطع شد", "idle")

qr_actions = tk.Frame(form, bg=COLORS["panel"])
qr_actions.pack(fill="x", pady=(8, 4))
def paste_pairing():
    try:
        qr_var.set(root.clipboard_get())
        import_pairing_qr()
    except tk.TclError:
        messagebox.showwarning("Clipboard", "متنی در حافظه موقت ویندوز پیدا نشد.")

def scan_qr_camera():
    try:
        import cv2
        import zxingcpp
    except ImportError:
        messagebox.showerror("اسکن دوربین", "ماژول دوربین/QR در این نسخه موجود نیست.")
        return
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0)
    if not camera.isOpened():
        camera.release()
        messagebox.showerror("اسکن دوربین", "دوربین در دسترس نیست؛ از گزینه انتخاب تصویر QR استفاده کنید.")
        return
    found = None
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                break
            cv2.putText(frame, "Show RoutePou QR - press Q to cancel", (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (245, 245, 245), 2)
            cv2.imshow("RoutePou - QR Scanner", frame)
            results = zxingcpp.read_barcodes(frame)
            if results:
                found = results[0].text
                break
            if cv2.waitKey(20) & 0xFF in (ord("q"), 27):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
    if found:
        qr_var.set(found)
        import_pairing_qr()

def scan_qr_image():
    path = filedialog.askopenfilename(title="انتخاب تصویر QR گوشی", filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp")])
    if not path:
        return
    try:
        import zxingcpp
        from PIL import Image
        results = zxingcpp.read_barcodes(Image.open(path))
        if not results:
            raise ValueError("کد QR در تصویر پیدا نشد. تصویر واضح‌تری انتخاب کنید.")
        qr_var.set(results[0].text)
        import_pairing_qr()
    except ImportError:
        messagebox.showerror("اسکن QR", "ماژول اسکن QR نصب نیست. نسخه رسمی RoutePou را دوباره دریافت کنید.")
    except Exception as exc:
        messagebox.showerror("اسکن QR", str(exc))

tk.Button(qr_actions, text="اسکن با دوربین", command=scan_qr_camera, bg=COLORS["accent"], fg="white",
          activebackground=COLORS["accent_hover"], activeforeground="white", relief="flat", padx=12, pady=7, cursor="hand2").pack(side="left")
tk.Button(qr_actions, text="انتخاب تصویر QR", command=scan_qr_image, bg=COLORS["panel2"], fg=COLORS["text"],
          activebackground=COLORS["border"], activeforeground=COLORS["text"], relief="flat", padx=12, pady=7, cursor="hand2").pack(side="left", padx=8)
tk.Button(qr_actions, text="خواندن از Clipboard", command=paste_pairing, bg=COLORS["panel2"], fg=COLORS["text"],
          activebackground=COLORS["border"], activeforeground=COLORS["text"], relief="flat", padx=12, pady=7, cursor="hand2").pack(side="left", padx=8)

advanced = tk.LabelFrame(form, text=" اطلاعات اتصال (در صورت نیاز دستی تکمیل کنید) ",
                         font=(FONT, 9, "bold"), fg=COLORS["muted"], bg=COLORS["panel"],
                         bd=1, relief="solid", labelanchor="nw", padx=12, pady=7)
advanced_toggle = tk.Button(form, text="تنظیمات دستی پیشرفته", command=lambda: advanced.pack(fill="x", pady=(10, 0)) if not advanced.winfo_manager() else advanced.pack_forget(),
                             bg=COLORS["panel2"], fg=COLORS["muted"], activebackground=COLORS["border"],
                             relief="flat", padx=10, pady=6, cursor="hand2")
advanced_toggle.pack(anchor="w", pady=(8, 0))
row1 = tk.Frame(advanced, bg=COLORS["panel"]); row1.pack(fill="x")
for label, var, secret in (("IP گوشی در شبکه", ip, False), ("پورت سرویس", port_var, False)):
    w, _ = make_field(row1, label, var, secret=secret)
    w.pack(side="left", fill="x", expand=True, padx=(0, 10))
row2 = tk.Frame(advanced, bg=COLORS["panel"]); row2.pack(fill="x")
w, _ = make_field(row2, "کلید Pairing", key_var, secret=True); w.pack(side="left", fill="x", expand=True, padx=(0, 10))
w, _ = make_field(row2, "اثر انگشت TLS (SHA-256)", fingerprint_var); w.pack(side="left", fill="x", expand=True)

proxy_card = card(outer, "۲. استفاده از اتصال", "پس از اتصال، پراکسی سیستم ویندوز روی HTTP/HTTPS فعال می‌شود. برنامه‌های سازگار می‌توانند از SOCKS5 به‌صورت دستی استفاده کنند.")
proxy_card.pack(fill="x", pady=(0, 14))
proxy_grid = tk.Frame(proxy_card, bg=COLORS["panel"]); proxy_grid.pack(fill="x", padx=18, pady=(0, 15))
for title, value in (("پراکسی سیستم", "HTTP / HTTPS · 127.0.0.1:17878"), ("پراکسی برنامه‌ای", "SOCKS5 · 127.0.0.1:17879")):
    cell = tk.Frame(proxy_grid, bg=COLORS["panel2"]); cell.pack(side="left", fill="x", expand=True, padx=(0, 8))
    tk.Label(cell, text=title, font=(FONT, 9), fg=COLORS["muted"], bg=COLORS["panel2"]).pack(anchor="w", padx=12, pady=(9, 2))
    tk.Label(cell, text=value, font=(FONT, 10, "bold"), fg=COLORS["text"], bg=COLORS["panel2"]).pack(anchor="w", padx=12, pady=(0, 10))

buttons = tk.Frame(outer, bg=COLORS["bg"]); buttons.pack(fill="x", pady=(0, 14))
connect_button = tk.Button(buttons, text="اتصال پراکسی", command=connect, bg=COLORS["accent"], fg="white",
                           activebackground=COLORS["accent_hover"], activeforeground="white", relief="flat",
                           font=(FONT, 11, "bold"), padx=22, pady=12, cursor="hand2")
connect_button.pack(side="left", fill="x", expand=True, padx=(0, 8))
tk.Button(buttons, text="اتصال تونل کامل WireGuard", command=connect_full_tunnel, bg="#365fd8", fg="white",
          activebackground="#4772ec", activeforeground="white", relief="flat",
          font=(FONT, 10, "bold"), padx=16, pady=12, cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 8))
tk.Button(buttons, text="قطع تونل کامل", command=disconnect_full_tunnel, bg=COLORS["panel2"], fg=COLORS["text"],
          activebackground=COLORS["border"], activeforeground=COLORS["text"], relief="flat",
          font=(FONT, 9, "bold"), padx=12, pady=12, cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 8))
tk.Button(buttons, text="قطع پراکسی و بازیابی تنظیمات", command=disconnect, bg=COLORS["panel2"], fg=COLORS["text"],
          activebackground=COLORS["border"], activeforeground=COLORS["text"], relief="flat",
          font=(FONT, 10, "bold"), padx=18, pady=12, cursor="hand2").pack(side="left", fill="x", expand=True)

notice = tk.Frame(outer, bg="#241d2a", highlightthickness=1, highlightbackground="#5b3448")
notice.pack(fill="x")
tk.Label(notice, text="محدودیت نسخه آلفا", font=(FONT, 9, "bold"), fg="#ffb4c4", bg="#241d2a").pack(anchor="w", padx=14, pady=(9, 2))
tk.Label(notice, text="اتصال QR در این نسخه برای جفت‌سازی سریع است. حالت پراکسی و تونل WireGuard مسیرهای جداگانه‌اند؛ قبل از استفاده روزمره، انتقال واقعی ترافیک را آزمایش کنید.",
         font=(FONT, 9), fg="#d8c4ce", bg="#241d2a", wraplength=680, justify="left").pack(anchor="w", padx=14, pady=(0, 10))

footer = tk.Label(outer, text=f"POU NETWORK TOOLS  •  ROUTEPOU {APP_VERSION.upper()}", font=(FONT, 8, "bold"), fg="#647492", bg=COLORS["bg"])
footer.pack(anchor="center", pady=(12, 0))
def _restore_proxy_on_exit():
    """Never leave the Windows system proxy pointing at a bridge that no longer exists."""
    if previous:
        try:
            disconnect()
        except Exception:
            pass


atexit.register(_restore_proxy_on_exit)
root.protocol("WM_DELETE_WINDOW", lambda: (disconnect_full_tunnel(), disconnect(), root.destroy()))
root.mainloop()
