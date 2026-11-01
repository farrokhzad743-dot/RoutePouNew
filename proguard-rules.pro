# Relay WireGuard is accessed through reflection from WireGuardEngine.
-keep class relaywg.** { *; }
# gomobile runtime support classes (Seq, Universe, ...).
-keep class go.** { *; }
