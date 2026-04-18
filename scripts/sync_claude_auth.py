#!/usr/bin/env python3
"""
ホスト側 Claude Code 認証同期スクリプト（macOS 専用）

フロー:
  1. コンテナの credentials を確認
  2. 有効期限内 → スキップ
  3. 期限切れ・リフレッシュトークンあり → リフレッシュトークンで自動更新
  4. リフレッシュ失敗 or 認証情報なし → macOS Keychain アクセス（パスワードダイアログ）
  5. コンテナへコピー

注意: claude auth login はコンテナ（Linux）で stdin を待機しないため使用不可。
     代わりにリフレッシュトークンを直接使って更新する。
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

CONTAINER = os.environ.get("TAKUMI_CONTAINER", "takumi-bot")
CONTAINER_CRED_PATH = "/home/takumi/.claude/.credentials.json"
EXPIRY_BUFFER_SEC = 300   # 期限の 5 分前から「期限切れ」とみなす
STARTUP_WAIT_SEC = 15

# Claude Code OAuth クライアント情報（バイナリから抽出）
OAUTH_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"


def wait_for_container(timeout: int = STARTUP_WAIT_SEC) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and r.stdout.strip() == "true":
            return True
        time.sleep(1)
    return False


def get_container_credentials() -> dict | None:
    r = subprocess.run(
        ["docker", "exec", CONTAINER, "cat", CONTAINER_CRED_PATH],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def is_valid(cred: dict | None) -> bool:
    if not cred:
        return False
    oauth = cred.get("claudeAiOauth", {})
    if not oauth.get("accessToken") or not oauth.get("refreshToken"):
        return False
    expires_at_ms = oauth.get("expiresAt", 0)
    now_ms = time.time() * 1000
    return expires_at_ms > now_ms + EXPIRY_BUFFER_SEC * 1000


def refresh_token(cred: dict) -> dict | None:
    """リフレッシュトークンを使ってアクセストークンを更新する。"""
    oauth = cred.get("claudeAiOauth", {})
    refresh = oauth.get("refreshToken")
    if not refresh:
        return None

    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": CLIENT_ID,
    }).encode()

    req = urllib.request.Request(
        OAUTH_TOKEN_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "claude-code/2.1.114",
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"[sync_claude_auth] リフレッシュ失敗 HTTP {e.code}: {e.read()[:200]}")
        return None
    except Exception as e:
        print(f"[sync_claude_auth] リフレッシュ失敗: {e}")
        return None

    # レスポンスを credentials 形式に変換
    new_oauth = {
        **oauth,
        "accessToken": data["access_token"],
        "expiresAt": int(time.time() * 1000) + data.get("expires_in", 3600) * 1000,
    }
    if "refresh_token" in data:
        new_oauth["refreshToken"] = data["refresh_token"]

    return {"claudeAiOauth": new_oauth}


def get_from_keychain() -> dict | None:
    """macOS Keychain からトークンを取得する（パスワード入力ダイアログが出る）。"""
    r = subprocess.run(
        ["security", "find-generic-password", "-s", "Claude Code-credentials", "-g"],
        capture_output=True, text=True,
    )
    for line in r.stderr.split("\n"):
        if line.strip().startswith("password:"):
            try:
                raw = line[line.index('"') + 1 : line.rindex('"')]
                return json.loads(raw)
            except (ValueError, json.JSONDecodeError):
                return None
    return None


def copy_to_container(cred: dict) -> bool:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(cred, f)
        tmp = f.name
    try:
        r = subprocess.run(
            ["docker", "cp", tmp, f"{CONTAINER}:{CONTAINER_CRED_PATH}"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return False
        cred_dir = CONTAINER_CRED_PATH.rsplit("/", 1)[0]
        subprocess.run(
            ["docker", "exec", "-u", "root", CONTAINER,
             "chown", "-R", "takumi:takumi", cred_dir],
            capture_output=True, text=True,
        )
        return True
    finally:
        os.unlink(tmp)


def main() -> None:
    print(f"[sync_claude_auth] コンテナ '{CONTAINER}' の認証状態を確認中…")

    if not wait_for_container():
        print(f"[sync_claude_auth] ERROR: コンテナ '{CONTAINER}' が起動しませんでした。")
        sys.exit(1)

    cred = get_container_credentials()

    if is_valid(cred):
        print("[sync_claude_auth] 認証済み・有効期限内 → スキップ")
        return

    # 期限切れだがリフレッシュトークンがある → 自動更新を試みる
    oauth = (cred or {}).get("claudeAiOauth", {})
    if oauth.get("refreshToken"):
        print("[sync_claude_auth] アクセストークン期限切れ → リフレッシュトークンで更新中…")
        refreshed = refresh_token(cred)
        if refreshed:
            if copy_to_container(refreshed):
                print("[sync_claude_auth] トークン更新完了・コンテナへコピーしました。")
                return
            else:
                print("[sync_claude_auth] コンテナへのコピーに失敗しました。Keychain にフォールバック…")
        else:
            print("[sync_claude_auth] リフレッシュ失敗。Keychain にフォールバック…")

    # リフレッシュ失敗 or 認証情報なし → Keychain から取得
    reason = "認証情報なし" if cred is None else "リフレッシュ失敗"
    print(f"[sync_claude_auth] {reason} → macOS Keychain へアクセスします（パスワード入力ダイアログが表示されます）")

    cred = get_from_keychain()
    if not cred:
        print("[sync_claude_auth] ERROR: Keychain からの取得に失敗しました。")
        sys.exit(1)

    oauth = cred.get("claudeAiOauth", {})
    if not oauth.get("accessToken"):
        print("[sync_claude_auth] ERROR: Keychain の認証情報が不正です。")
        sys.exit(1)

    # Keychain のトークンも期限切れなら、その場でリフレッシュ
    expires_at_ms = oauth.get("expiresAt", 0)
    if expires_at_ms < time.time() * 1000:
        print("[sync_claude_auth] Keychain のトークンも期限切れ → リフレッシュ中…")
        refreshed = refresh_token(cred)
        if refreshed:
            cred = refreshed
            print("[sync_claude_auth] Keychain トークンのリフレッシュ成功。")
        else:
            print("[sync_claude_auth] WARNING: リフレッシュ失敗。期限切れトークンでコピーします。")

    if not copy_to_container(cred):
        print("[sync_claude_auth] ERROR: コンテナへのコピーに失敗しました。")
        sys.exit(1)

    print("[sync_claude_auth] 認証情報をコンテナへコピーしました。")


if __name__ == "__main__":
    main()
