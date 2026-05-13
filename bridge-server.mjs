import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const PORT     = 7823;
const BASE     = path.dirname(fileURLToPath(import.meta.url));
const REQ_FILE = path.join(BASE, 'data', 'fill-request.json');
const RES_FILE = path.join(BASE, 'data', 'fill-response.json');
const POLL_MS  = 500;
const TIMEOUT  = 60_000;

function waitForResponse() {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const timer = setInterval(() => {
      if (fs.existsSync(RES_FILE)) {
        clearInterval(timer);
        try {
          const data = JSON.parse(fs.readFileSync(RES_FILE, 'utf8'));
          fs.rmSync(RES_FILE);
          resolve(data);
        } catch (e) { reject(e); }
      } else if (Date.now() - start > TIMEOUT) {
        clearInterval(timer);
        reject(new Error('timeout'));
      }
    }, POLL_MS);
  });
}

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method === 'POST' && req.url === '/fill') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
      try {
        const payload = JSON.parse(body);
        if (fs.existsSync(RES_FILE)) fs.rmSync(RES_FILE);
        fs.writeFileSync(REQ_FILE, JSON.stringify(payload, null, 2));
        console.log(`[bridge] request written — ${payload.fields?.length ?? 0} fields from ${payload.url}`);
        const response = await waitForResponse();
        console.log(`[bridge] response ready — ${response.fields?.length ?? 0} answers`);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(response));
      } catch (err) {
        console.error(`[bridge] error: ${err.message}`);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end();
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Claude Apply bridge listening on http://localhost:${PORT}`);
  console.log(`Waiting for /jobhunter apply session to handle requests…`);
});
