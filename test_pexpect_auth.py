#!/usr/bin/env python3
"""pexpect auth flow テスト v4: raw logfile で全通信を可視化
検証後に削除する。

使い方（コンテナ内）:
  python /app/test_pexpect_auth.py
"""
import os
import re
import sys
import time
import subprocess
import pathlib

try:
    import pexpect
except ImportError:
    print("ERROR: pexpect not installed")
    sys.exit(1)

INBOX = pathlib.Path("/app/inbox")
AUTH_FILE = INBOX / ".auth_code"

print("=== Step 1: pexpect (PTY) で claude auth login 起動 ===")
print("  ※ [RAW] 行はプロセスの生出力。コード送信後の反応を確認する\n")

env = {**os.environ, "DISPLAY": ""}
child = pexpect.spawn("claude auth login", env=env, timeout=10, encoding="utf-8")

# 全 I/O を stdout に流す（raw bytes の確認用）
class PrefixWriter:
    def __init__(self, prefix="[RAW] "):
        self.prefix = prefix
        self.buf = ""
    def write(self, s):
        self.buf += s
        while '\n' in self.buf:
            line, self.buf = self.buf.split('\n', 1)
            sys.stdout.write(f"{self.prefix}{repr(line)}\n")
        sys.stdout.flush()
    def flush(self):
        if self.buf:
            sys.stdout.write(f"{self.prefix}{repr(self.buf)}\n")
            self.buf = ""
            sys.stdout.flush()

child.logfile_read = PrefixWriter("[OUT] ")

print(f"  PID: {child.pid}")

# URL を待つ
i = child.expect([r"https://\S+", r"already", pexpect.EOF, pexpect.TIMEOUT])
print(f"\n  expect() index={i}")

if i == 1:
    print("  → 認証済み")
    child.close(force=True)
    sys.exit(0)
if i in (2, 3):
    print(f"  → 失敗")
    child.close(force=True)
    sys.exit(1)

url = child.match.group(0) if child.match else None
print(f"\n  ✅ URL 取得")
print(f"  {url}\n")

print("=== Step 2: URL 取得後10秒の出力を確認 ===")
child.timeout = 10
try:
    while True:
        i2 = child.expect([r".+", pexpect.EOF, pexpect.TIMEOUT])
        if i2 in (1, 2):
            break
except Exception:
    pass
print(f"  プロセス alive: {child.isalive()}\n")

print("=== Step 3: .auth_code ファイル待機 ===")
INBOX.mkdir(parents=True, exist_ok=True)
if not AUTH_FILE.exists():
    AUTH_FILE.touch()
print("  ブラウザで認証 → コードを ./inbox/.auth_code に貼り付け保存")
print("  最大5分待ちます...\n")

code = None
for i_wait in range(30):
    time.sleep(10)
    if AUTH_FILE.exists():
        text = AUTH_FILE.read_text(encoding="utf-8").strip()
        if text:
            code = text
            AUTH_FILE.unlink()
            print(f"\n  ✅ コード受け取り: {code[:12]}... ({len(code)} 文字)")
            break
    print(f"  ...(待機 {(i_wait+1)*10}秒)")

if not code:
    print("\n  ERROR: タイムアウト")
    child.close(force=True)
    sys.exit(1)

print(f"\n=== Step 4: コード送信 ===")
print(f"  プロセス alive: {child.isalive()}")
if not child.isalive():
    print("  ERROR: プロセス終了済み")
    sys.exit(1)

# raw bytes も確認
print(f"  code bytes: {repr(code[:20])}")

# write を logfile で記録
child.logfile_send = PrefixWriter("[SEND] ")
child.sendline(code)
print("  sendline 完了。30秒出力待機...\n")

child.timeout = 30
try:
    while True:
        i3 = child.expect([r".+", pexpect.EOF, pexpect.TIMEOUT])
        if i3 == 1:
            print("\n  ✅ EOF — プロセス正常終了")
            break
        if i3 == 2:
            print("\n  ⚠️  30秒 TIMEOUT")
            break
except Exception as e:
    print(f"  (例外: {e})")

print(f"  プロセス alive: {child.isalive()}")
child.close(force=True)

print("\n=== Step 5: 認証状態確認 ===")
r = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True)
print(f"  returncode: {r.returncode}")
print(f"  {r.stdout.strip()}")
cred = pathlib.Path("/root/.claude/.credentials.json")
print(f"  .credentials.json: {'✅ 存在' if cred.exists() else '❌ なし'}")
