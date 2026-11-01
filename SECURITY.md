# Security policy

## Reporting a vulnerability
Please do **not** open a public issue for security problems. Use GitHub's *Security → Report a vulnerability* (private advisory) on this repository. Include the version, the platform (Android/Windows) and steps to reproduce.

## Security model (what RoutePou does and does not promise)
- **Pairing QR is a secret.** It contains a per-session access token (proxy mode) or a per-session WireGuard client private key (full-tunnel mode). Anyone who photographs it while it is valid can use your phone's connection. Pairing QRs for the WireGuard mode expire after 5 minutes.
- **Proxy mode** uses TLS 1.2/1.3 to the phone. Each Android installation has its own key pair and self-signed certificate (Android Keystore); the QR carries the certificate's SHA-256 fingerprint and Windows refuses any other certificate. All requests must also carry the token.
- **Full-tunnel mode** uses WireGuard (wireguard-go). Keys are generated with the official WireGuard crypto library, held in memory, and passed to the Windows worker over a one-session named pipe — never written to disk, command lines or logs.
- Use RoutePou only on a hotspot you control. Other devices on the same hotspot are on the same network segment as the proxy port.
- This is a pre-release that has not had an independent audit.

## Supported versions
Only the latest release receives fixes.
