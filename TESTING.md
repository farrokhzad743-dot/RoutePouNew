# Real-device checklist

A green CI run proves the code compiles and the unit tests pass. It does **not** prove that traffic flows. Run these on a physical Android phone (hotspot on) and a Windows 10/11 PC before calling a release stable. Never share screenshots or logs that contain QR contents, tokens or keys.

## A. Proxy mode
1. Phone: **Start sharing** (شروع اشتراک‌گذاری). Windows: scan the QR. Status turns green.
2. Open a website in a browser on Windows. Check the public IP (e.g. any "what is my IP" page): it must be the phone's (or the phone VPN's) address, not the Windows network's.
3. Phone: turn its VPN on, reload: the IP must become the VPN's.
4. **Disconnect proxy.** Windows Settings → Network → Proxy must be back to what it was.
5. Phone: **New pairing key**, then try the old QR: it must be rejected.

## B. Full tunnel (experimental; run Windows as Administrator when prompted)
1. Phone: Advanced → **Start Full Tunnel**. Windows: scan the QR within 5 minutes (an older QR must be refused).
2. Windows reports *READY* only after a WireGuard handshake. A created adapter alone is not success.
3. TCP: browse several sites. UDP/DNS: `nslookup example.com` and a video call or speed test.
4. Public IPv4 = the phone's egress. IPv6: either routed via a verified path or blocked (no leak): test at a DNS/IPv6 leak-test site.
5. **Fail closed:** stop the tunnel on the phone while connected. Windows traffic must stop, not fall back to its own Wi-Fi.
6. Restore the phone side: the tunnel must recover without manual cleanup.
7. **Disconnect** normally, then repeat and force-kill the worker (`relaywg-client.exe`) in Task Manager. `route print`, DNS settings and the firewall must return to normal after Disconnect/restart.
8. Repeat after: hotspot reconnect, phone screen off for 10 minutes, Windows sleep/resume.

## C. What to report
App versions, which step failed, and the worker status lines (STARTING, HANDSHAKE, READY, PEER-LOST, PEER-BACK). Do not include secrets.
