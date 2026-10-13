#!/usr/bin/env node
/**
 * chatgpt-proxy.js — Local OpenAI-compatible proxy at port 3040.
 * Đọc AUTH_KEY và OPENAI_API_KEY từ file .env trong thư mục này.
 * Nhận POST /v1/chat/completions với header Authorization: Bearer <AUTH_KEY>
 * rồi chuyển tiếp tới OpenAI API. Tự thử lại một lần nếu upstream trả 502/503/504.
 *
 * Cài Node.js (node.org), đặt file .env cạnh file này, rồi chạy:
 *   node chatgpt-proxy.js
 */

import http from 'http';
import https from 'https';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const DIR = path.dirname(fileURLToPath(import.meta.url));

// --- load .env ---
function loadEnv() {
  const envPath = path.join(DIR, '.env');
  const result = {};
  if (!fs.existsSync(envPath)) return result;
  for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*"?(.*?)"?\s*$/);
    if (m) result[m[1]] = m[2];
  }
  return result;
}

const env = loadEnv();
const PORT       = parseInt(env.PORT || '3040', 10);
const AUTH_KEY   = (env.AUTH_KEY || '').trim();
const OPENAI_KEY = (env.OPENAI_API_KEY || '').trim();
const UPSTREAM   = (env.OPENAI_BASE_URL || 'https://api.openai.com').replace(/\/$/, '');

if (!AUTH_KEY)   { console.error('[proxy] LỖI: AUTH_KEY chưa đặt trong .env'); process.exit(1); }
if (!OPENAI_KEY) { console.error('[proxy] LỖI: OPENAI_API_KEY chưa đặt trong .env'); process.exit(1); }

// --- upstream fetch with retry ---
async function callUpstream(endpoint, body, retries = 1) {
  const url = new URL(UPSTREAM + endpoint);
  const data = Buffer.from(body, 'utf8');
  return new Promise((resolve, reject) => {
    function attempt(remaining) {
      const req = https.request({
        hostname: url.hostname,
        port: url.port || 443,
        path: url.pathname + url.search,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': data.length,
          'Authorization': 'Bearer ' + OPENAI_KEY,
        },
      }, res => {
        let chunks = [];
        res.on('data', c => chunks.push(c));
        res.on('end', () => {
          const text = Buffer.concat(chunks).toString('utf8');
          if ([502, 503, 504].includes(res.statusCode) && remaining > 0) {
            console.warn(`[proxy] Upstream HTTP ${res.statusCode}, thử lại sau 2s… (${remaining} lần còn lại)`);
            setTimeout(() => attempt(remaining - 1), 2000);
          } else {
            resolve({ status: res.statusCode, headers: res.headers, body: text });
          }
        });
      });
      req.on('error', err => {
        if (remaining > 0) {
          console.warn(`[proxy] Lỗi kết nối upstream: ${err.message}, thử lại sau 2s…`);
          setTimeout(() => attempt(remaining - 1), 2000);
        } else {
          reject(err);
        }
      });
      req.write(data);
      req.end();
    }
    attempt(retries);
  });
}

// --- HTTP server ---
const server = http.createServer(async (req, res) => {
  // CORS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Authorization,Content-Type', 'Access-Control-Allow-Methods': 'POST,OPTIONS' });
    res.end(); return;
  }

  // Auth
  const auth = (req.headers['authorization'] || '').trim();
  if (AUTH_KEY && auth !== 'Bearer ' + AUTH_KEY) {
    res.writeHead(401, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: { message: 'Xác thực thất bại. Kiểm tra AUTH_KEY trong .env và khóa đã nhập trong ứng dụng.', type: 'auth_error' } }));
    return;
  }

  // Only proxy /v1/chat/completions
  if (req.method !== 'POST' || !req.url.startsWith('/v1/chat/completions')) {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: { message: 'Endpoint không hỗ trợ. Chỉ hỗ trợ POST /v1/chat/completions.', type: 'not_found' } }));
    return;
  }

  // Collect body
  let body = '';
  for await (const chunk of req) body += chunk;

  // Validate JSON
  let parsed;
  try { parsed = JSON.parse(body); }
  catch {
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: { message: 'Body không phải JSON hợp lệ.', type: 'invalid_request_error' } }));
    return;
  }

  try {
    const upstream = await callUpstream('/v1/chat/completions', body);
    res.writeHead(upstream.status, {
      'Content-Type': upstream.headers['content-type'] || 'application/json',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(upstream.body);

    if (upstream.status >= 400) {
      let hint = '';
      if (upstream.status === 401) hint = ' — OPENAI_API_KEY không hợp lệ.';
      else if (upstream.status === 429) hint = ' — OpenAI đang giới hạn yêu cầu hoặc hết hạn mức.';
      else if (upstream.status === 404) hint = ' — Model không tồn tại hoặc chưa được phép.';
      else if (upstream.status === 502) hint = ' — OpenAI upstream lỗi tạm thời; đã thử lại nhưng vẫn thất bại.';
      console.warn(`[proxy] Upstream trả ${upstream.status}${hint}`);
    }
  } catch (err) {
    const msg = `Không kết nối được OpenAI: ${err.message}. Kiểm tra mạng và OPENAI_API_KEY.`;
    console.error('[proxy]', msg);
    res.writeHead(502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: { message: msg, type: 'proxy_error' } }));
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[proxy] Đang chạy tại http://127.0.0.1:${PORT} — upstream: ${UPSTREAM}`);
});

server.on('error', err => {
  if (err.code === 'EADDRINUSE') {
    console.error(`[proxy] Cổng ${PORT} đã được dùng. Đặt PORT=<khác> trong .env hoặc đóng ứng dụng đang chiếm cổng.`);
  } else {
    console.error('[proxy] Lỗi server:', err.message);
  }
  process.exit(1);
});
