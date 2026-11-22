"""Public relay landing page. Connection keys and project data stay private."""

WELCOME = '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Origin Extract · PC relay</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0c0a10;color:#ece4f5;
font:16px/1.55 ui-rounded,system-ui,sans-serif;min-height:100vh;display:grid;place-items:center;padding:24px}
main{max-width:480px;padding:32px;background:#15121b;border:1px solid #392b46;border-radius:24px}
.badge{color:#cbb1ef;font-size:13px}h1{font-size:30px;letter-spacing:-1px;margin:10px 0 16px}
p{color:#baadca}strong{color:#e4d2ff}ol{padding-left:22px}li{padding:6px 0}footer{font-size:12px;color:#92849f;margin-top:24px}
</style><main>
<span class="badge">● Relay is running</span><h1>origin extract</h1>
<p>You reached the Windows PC. Connect through the <strong>Origin Extract app on your Mac</strong>.</p>
<ol><li>On the PC, open <strong>Mac ↔ PC → My Windows PC</strong> and copy the address and connection key.</li>
<li>On the Mac, paste them into <strong>Mac ↔ PC → My Mac</strong>, then choose <strong>Test connection</strong>.</li></ol>
<p>Your browser does not send a connection key. This page only confirms that the relay is reachable from this device.</p>
<footer>Created by Amir MEDDAS</footer></main></html>'''
