#!/usr/bin/env python3
"""
GitHub Webhook — Auto-deploy for tr-ar + tr-ar-ai
"""
import hashlib, hmac, json, os, subprocess, threading, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

WEBHOOK_SECRET = os.environ["GITHUB_WEBHOOK_SECRET"].encode()
BOT_TOKEN      = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID        = os.environ["TELEGRAM_CHAT_ID"]
DEPLOY_BRANCH  = os.environ.get("DEPLOY_BRANCH", "main")
PORT           = int(os.environ.get("WEBHOOK_PORT", "8765"))

# مشاريع مدعومة: repo_name -> deploy_script
PROJECTS = {
    "TR_AR":       "/opt/scripts/deploy-tr-ar.sh",
    "TR_AR_AI":    "/opt/scripts/deploy-tr-ar-ai.sh",
    "LLM-Council":     "/opt/scripts/deploy-llm-council.sh",
    "Analytics_Morad": "/opt/scripts/deploy-analytics-morad.sh",
}

def tg(text: str):
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
    req  = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[tg error] {e}")

def deploy(repo: str, ref: str, sha: str, msg: str, pusher: str):
    branch = ref.split("/")[-1]
    if branch != DEPLOY_BRANCH:
        print(f"[webhook] skipping branch {branch}")
        return

    script = PROJECTS.get(repo)
    if not script:
        print(f"[webhook] unknown repo: {repo}")
        return

    short = sha[:7]
    tg(f"🚀 <b>Deploy بدأ</b>\n📦 {repo} @ <code>{short}</code>\n💬 {msg}\n👤 {pusher}")
    try:
        r = subprocess.run(
            ["bash", script],
            capture_output=True, text=True, timeout=600
        )
        if r.returncode == 0:
            tg(f"✅ <b>Deploy نجح</b>\n📦 {repo} @ <code>{short}</code>")
        else:
            err = (r.stderr or r.stdout)[:500]
            tg(f"❌ <b>Deploy فشل</b>\n📦 {repo} @ <code>{short}</code>\n<code>{err}</code>")
    except subprocess.TimeoutExpired:
        tg(f"⚠️ <b>Deploy انتهى وقته (10 دقائق)</b>\n📦 {repo} @ <code>{short}</code>")
    except Exception as e:
        tg(f"⚠️ <b>خطأ في Deploy</b>: {e}")

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        sig      = self.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            self.send_response(401); self.end_headers()
            return

        try:
            payload = json.loads(body)
        except Exception:
            self.send_response(400); self.end_headers()
            return

        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

        repo    = payload.get("repository", {}).get("name", "")
        ref     = payload.get("ref", "")
        commit  = payload.get("head_commit", {})
        sha     = commit.get("id", "")
        msg     = commit.get("message", "").split("\n")[0][:80]
        pusher  = payload.get("pusher", {}).get("name", "unknown")

        threading.Thread(target=deploy, args=(repo, ref, sha, msg, pusher), daemon=True).start()

    def log_message(self, fmt, *args):
        print(f"[webhook] {fmt % args}")

if __name__ == "__main__":
    print(f"[webhook] listening on :{PORT}  branch={DEPLOY_BRANCH}")
    print(f"[webhook] projects: {list(PROJECTS.keys())}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
