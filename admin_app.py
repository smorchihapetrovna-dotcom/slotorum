#!/usr/bin/env python3
"""Админка: список на стрим + пройденные игры с ссылками на плейлисты."""

import json
import os
import secrets
from functools import wraps
from flask import Flask, request, jsonify, session, redirect, url_for, render_template_string

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# === НАСТРОЙКИ ===
ADMIN_PASSWORD = "changeme123"  # свой пароль
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
STREAM_FILE = os.path.join(DATA_DIR, "data.json")
COMPLETED_FILE = os.path.join(DATA_DIR, "completed-games.json")
# =================


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Админка — Вход</title>
<style>
  body { font-family: system-ui, sans-serif; background: #0f0a1a; color: #eee; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
  .box { background: #1a1025; padding: 40px; border-radius: 16px; border: 1px solid #ff66cc55; width: 100%; max-width: 360px; }
  h1 { margin: 0 0 24px; font-size: 1.4rem; color: #ff66cc; text-align: center; }
  input { width: 100%; padding: 12px; margin-bottom: 16px; border-radius: 8px; border: 1px solid #555; background: #0a0a15; color: #fff; font-size: 1rem; box-sizing: border-box; }
  button { width: 100%; padding: 12px; border: none; border-radius: 8px; background: linear-gradient(90deg, #6b0f9c, #c41a7a); color: white; font-size: 1rem; cursor: pointer; font-weight: 600; }
  button:hover { opacity: 0.9; }
  .error { color: #ff6b6b; margin-bottom: 12px; text-align: center; }
</style>
</head>
<body>
  <div class="box">
    <h1>Админка Слоторум</h1>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post">
      <input type="password" name="password" placeholder="Пароль" required autofocus>
      <button type="submit">Войти</button>
    </form>
  </div>
</body>
</html>
"""

ADMIN_HTML = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Админка — Слоторум</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: system-ui, sans-serif; background: #0f0a1a; color: #eee; margin: 0; padding: 20px; }
  .container { max-width: 1200px; margin: 0 auto; }
  h1 { color: #ff66cc; margin-bottom: 8px; }
  .tabs { display: flex; gap: 8px; margin: 16px 0 20px; flex-wrap: wrap; }
  .tab { padding: 10px 18px; border-radius: 999px; border: 1px solid #444; background: #1a1025; color: #ccc; cursor: pointer; font-weight: 600; }
  .tab.active { background: linear-gradient(90deg, #6b0f9c, #c41a7a); color: #fff; border-color: transparent; }
  .tab.archive.active { background: linear-gradient(90deg, #1e4a3a, #3d9b78); }
  .panel { display: none; }
  .panel.active { display: block; }
  .top-bar { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; align-items: center; }
  .btn { padding: 10px 18px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.95rem; }
  .btn-primary { background: linear-gradient(90deg, #6b0f9c, #c41a7a); color: white; }
  .btn-archive { background: linear-gradient(90deg, #1e4a3a, #3d9b78); color: white; }
  .btn-secondary { background: #333; color: #fff; }
  .btn-danger { background: #a22; color: white; }
  .btn-success { background: #2a6; color: white; }
  .btn:hover { opacity: 0.9; }
  table { width: 100%; border-collapse: collapse; background: #1a1025; border-radius: 12px; overflow: hidden; }
  th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #333; vertical-align: middle; }
  th { background: #2a1a3a; color: #ff99dd; }
  #panel-archive th { background: #1a2e26; color: #8fd9b8; }
  tr:hover { background: #251530; }
  input[type="text"], input[type="number"], input[type="url"], select {
    width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #555; background: #0a0a15; color: #fff;
  }
  .amount-input { width: 80px; text-align: center; }
  .actions { display: flex; gap: 8px; }
  .msg { padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; }
  .msg-ok { background: #1a3a2a; color: #6f6; }
  .msg-err { background: #3a1a1a; color: #f66; }
  .stats { color: #aaa; margin-bottom: 12px; }
  a { color: #ff99dd; }
  .hint { color: #888; font-size: 0.9rem; margin-bottom: 12px; }
  .cat-select { min-width: 140px; }
</style>
</head>
<body>
  <div class="container">
    <h1>Админка Слоторум</h1>
    <div class="stats">
      <a href="/" target="_blank">Открыть сайт</a> ·
      <a href="{{ url_for('logout') }}">Выйти</a>
    </div>

    <div class="tabs">
      <button type="button" class="tab active" data-tab="stream">Игры на стрим</button>
      <button type="button" class="tab archive" data-tab="archive">Пройденные игры</button>
    </div>

    <div id="message"></div>

    <!-- STREAM -->
    <div class="panel active" id="panel-stream">
      <p class="hint">Список для слот-машины. После сохранения сайт подхватит data.json.</p>
      <div class="top-bar">
        <button class="btn btn-success" type="button" onclick="addStreamRow()">+ Добавить игру</button>
        <button class="btn btn-primary" type="button" onclick="saveStream()">Сохранить</button>
        <button class="btn btn-secondary" type="button" onclick="document.getElementById('importStream').click()">Импорт JSON</button>
        <input type="file" id="importStream" accept=".json" style="display:none" onchange="importStream(event)">
      </div>
      <table>
        <thead>
          <tr>
            <th style="width:50px">#</th>
            <th>Название</th>
            <th style="width:110px">Баллы</th>
            <th style="width:90px"></th>
          </tr>
        </thead>
        <tbody id="stream-body"></tbody>
      </table>
    </div>

    <!-- ARCHIVE -->
    <div class="panel" id="panel-archive">
      <p class="hint">Архив прохождений. Колонка «Порядок» — позиция в хронологии (меньше = раньше). Новая игра получает следующий номер и становится последней. После сохранения — completed-games.json.</p>
      <div class="top-bar">
        <button class="btn btn-success" type="button" onclick="addArchiveRow()">+ Добавить игру</button>
        <button class="btn btn-archive" type="button" onclick="saveArchive()">Сохранить</button>
        <button class="btn btn-secondary" type="button" onclick="document.getElementById('importArchive').click()">Импорт JSON</button>
        <input type="file" id="importArchive" accept=".json" style="display:none" onchange="importArchive(event)">
      </div>
      <table>
        <thead>
          <tr>
            <th style="width:70px">Порядок</th>
            <th>Название</th>
            <th style="width:160px">Жанр</th>
            <th>Ссылка на плейлист</th>
            <th style="width:90px"></th>
          </tr>
        </thead>
        <tbody id="archive-body"></tbody>
      </table>
      <div class="top-bar" style="margin-top:16px">
        <button class="btn btn-success" type="button" onclick="addArchiveRow()">+ Добавить игру</button>
        <button class="btn btn-archive" type="button" onclick="saveArchive()">Сохранить</button>
      </div>
    </div>
  </div>

<script>
const CATEGORIES = {{ categories_json|safe }};
let streamLots = {{ stream_json|safe }};
let archiveFlat = {{ archive_json|safe }};

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
  });
});

function showMsg(text, isError) {
  const el = document.getElementById('message');
  el.className = 'msg ' + (isError ? 'msg-err' : 'msg-ok');
  el.textContent = text;
  setTimeout(() => { el.textContent = ''; el.className = ''; }, 4000);
}

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
}

/* ---- Stream ---- */
function renderStream() {
  const body = document.getElementById('stream-body');
  body.innerHTML = streamLots.map((g, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><input type="text" class="name-input" value="${esc(g.name)}"></td>
      <td><input type="number" class="amount-input" value="${Number(g.amount) || 0}" min="0"></td>
      <td class="actions"><button type="button" class="btn btn-danger" onclick="this.closest('tr').remove(); renumber('stream-body')">✕</button></td>
    </tr>
  `).join('');
}
function collectStream() {
  return [...document.querySelectorAll('#stream-body tr')].map(row => ({
    name: row.querySelector('.name-input').value.trim(),
    amount: parseInt(row.querySelector('.amount-input').value, 10) || 0,
    contributors: []
  })).filter(g => g.name);
}
function addStreamRow() {
  streamLots = collectStream();
  streamLots.push({ name: '', amount: 1, contributors: [] });
  renderStream();
  const inputs = document.querySelectorAll('#stream-body .name-input');
  if (inputs.length) inputs[inputs.length - 1].focus();
}
async function saveStream() {
  const lots = collectStream();
  const res = await fetch('/api/save-stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lots })
  });
  const data = await res.json();
  if (data.ok) {
    streamLots = lots;
    renderStream();
    showMsg('Список на стрим сохранён. Игр: ' + data.count);
  } else showMsg(data.error || 'Ошибка', true);
}
function importStream(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      const lots = data.lots || data;
      if (!Array.isArray(lots)) throw new Error('Нужен массив или {lots:[]}');
      streamLots = lots.map(g => ({
        name: g.name || '',
        amount: parseInt(g.amount, 10) || 0,
        contributors: g.contributors || []
      }));
      renderStream();
      showMsg('Импорт: ' + streamLots.length + ' игр. Нажми «Сохранить».');
    } catch (err) {
      showMsg('Ошибка JSON: ' + err.message, true);
    }
  };
  reader.readAsText(file);
  e.target.value = '';
}

/* ---- Archive ---- */
function categoryOptions(selected) {
  const set = new Set(CATEGORIES.concat(archiveFlat.map(g => g.category).filter(Boolean)));
  return [...set].map(c =>
    `<option value="${esc(c)}"${c === selected ? ' selected' : ''}>${esc(c)}</option>`
  ).join('');
}
function maxOrder() {
  let m = 0;
  archiveFlat.forEach(g => {
    const o = parseInt(g.order, 10);
    if (!isNaN(o) && o > m) m = o;
  });
  return m;
}
function renderArchive() {
  archiveFlat = [...archiveFlat].sort((a, b) => {
    const oa = parseInt(a.order, 10); const ob = parseInt(b.order, 10);
    const na = isNaN(oa) ? 99999 : oa; const nb = isNaN(ob) ? 99999 : ob;
    return na - nb || String(a.name || '').localeCompare(String(b.name || ''), 'ru');
  });
  const body = document.getElementById('archive-body');
  body.innerHTML = archiveFlat.map((g) => `
    <tr>
      <td><input type="number" class="order-input amount-input" value="${parseInt(g.order, 10) || 0}" min="1" title="Позиция в хронологии"></td>
      <td><input type="text" class="name-input" value="${esc(g.name)}"></td>
      <td>
        <select class="cat-select">
          ${categoryOptions(g.category || CATEGORIES[0] || '')}
          <option value="__new__">+ Новый жанр…</option>
        </select>
      </td>
      <td><input type="url" class="url-input" placeholder="https://youtube.com/playlist?list=…" value="${esc(g.url || '')}"></td>
      <td class="actions"><button type="button" class="btn btn-danger" onclick="this.closest('tr').remove()">✕</button></td>
    </tr>
  `).join('');
  body.querySelectorAll('.cat-select').forEach(sel => {
    sel.addEventListener('change', () => {
      if (sel.value === '__new__') {
        const name = prompt('Название нового жанра:');
        if (name && name.trim()) {
          const opt = document.createElement('option');
          opt.value = name.trim();
          opt.textContent = name.trim();
          sel.insertBefore(opt, sel.lastElementChild);
          sel.value = name.trim();
        } else {
          sel.value = CATEGORIES[0] || '';
        }
      }
    });
  });
}
function collectArchive() {
  return [...document.querySelectorAll('#archive-body tr')].map(row => ({
    name: row.querySelector('.name-input').value.trim(),
    category: row.querySelector('.cat-select').value,
    url: row.querySelector('.url-input').value.trim() || null,
    order: parseInt(row.querySelector('.order-input').value, 10) || 0
  })).filter(g => g.name && g.category && g.category !== '__new__');
}
function addArchiveRow() {
  archiveFlat = collectArchive();
  const next = maxOrder() + 1;
  archiveFlat.push({ name: '', category: CATEGORIES[0] || 'Бродилки', url: '', order: next });
  renderArchive();
  const inputs = document.querySelectorAll('#archive-body .name-input');
  if (inputs.length) inputs[inputs.length - 1].focus();
}
async function saveArchive() {
  const flat = collectArchive();
  const res = await fetch('/api/save-archive', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ games: flat })
  });
  const data = await res.json();
  if (data.ok) {
    archiveFlat = flat;
    renderArchive();
    showMsg('Архив сохранён. Игр: ' + data.count);
  } else showMsg(data.error || 'Ошибка', true);
}
function importArchive(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      let flat = [];
      if (Array.isArray(data) && data.length && data[0].games) {
        data.forEach(cat => {
          (cat.games || []).forEach(g => {
            flat.push({
              name: g.name || '',
              category: cat.category || '',
              url: g.url || '',
              order: parseInt(g.order, 10) || 0
            });
          });
        });
      } else if (Array.isArray(data)) {
        flat = data.map((g, i) => ({
          name: g.name || '',
          category: g.category || CATEGORIES[0] || '',
          url: g.url || '',
          order: parseInt(g.order, 10) || (i + 1)
        }));
      } else throw new Error('Неверный формат');
      // fill missing orders at the end
      let m = 0;
      flat.forEach(g => { if (g.order > m) m = g.order; });
      flat.forEach(g => { if (!g.order) { m += 1; g.order = m; } });
      archiveFlat = flat;
      renderArchive();
      showMsg('Импорт: ' + flat.length + ' игр. Нажми «Сохранить».');
    } catch (err) {
      showMsg('Ошибка JSON: ' + err.message, true);
    }
  };
  reader.readAsText(file);
  e.target.value = '';
}

function renumber(tbodyId) {
  document.querySelectorAll('#' + tbodyId + ' tr').forEach((row, i) => {
    row.cells[0].textContent = i + 1;
  });
}

renderStream();
renderArchive();
</script>
</body>
</html>
"""


def flatten_archive(cats):
    flat = []
    for c in cats or []:
        for g in c.get("games") or []:
            try:
                ord_ = int(g.get("order") or 0)
            except (TypeError, ValueError):
                ord_ = 0
            flat.append({
                "name": g.get("name") or "",
                "category": c.get("category") or "",
                "url": g.get("url") or "",
                "order": ord_,
            })
    flat.sort(key=lambda x: (x.get("order") or 99999, (x.get("name") or "").casefold()))
    return flat


def nest_archive(flat):
    # Preserve chronology order on each game; group by category for storage
    order = []
    buckets = {}
    for g in flat:
        cat = (g.get("category") or "").strip() or "Без категории"
        if cat not in buckets:
            buckets[cat] = []
            order.append(cat)
        try:
            ord_ = int(g.get("order") or 0)
        except (TypeError, ValueError):
            ord_ = 0
        buckets[cat].append({
            "name": (g.get("name") or "").strip(),
            "url": (g.get("url") or "").strip() or None,
            "order": ord_,
        })
    # Within category keep chronological order (not alphabetical)
    for cat in buckets:
        buckets[cat].sort(key=lambda x: (x.get("order") or 99999, (x.get("name") or "").casefold()))
    return [{"category": c, "games": buckets[c]} for c in order]


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("admin"))
        error = "Неверный пароль"
    return render_template_string(LOGIN_HTML, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@app.route("/admin")
@login_required
def admin():
    stream = load_json(STREAM_FILE, {"lots": []})
    lots = stream.get("lots", [])
    lots = sorted(lots, key=lambda x: (-int(x.get("amount") or 0), str(x.get("name", "")).lower()))
    completed = load_json(COMPLETED_FILE, [])
    flat = flatten_archive(completed)
    categories = [c.get("category") for c in completed if c.get("category")]
    if not categories:
        categories = [
            "Стратегии", "Бродилки", "Стрелялки", "Гонки", "Страшилки",
            "Головоломки", "Бегалки", "Прыгалки", "Симуляторы", "Рогулики",
            "Читалки", "Драчки", "Киноигоры", "Выживалки",
        ]
    return render_template_string(
        ADMIN_HTML,
        stream_json=json.dumps(lots, ensure_ascii=False),
        archive_json=json.dumps(flat, ensure_ascii=False),
        categories_json=json.dumps(categories, ensure_ascii=False),
    )


@app.route("/api/save-stream", methods=["POST"])
@app.route("/api/save", methods=["POST"])  # backward compatible
@login_required
def api_save_stream():
    try:
        data = request.get_json() or {}
        lots_in = data.get("lots") or []
        clean = []
        for g in lots_in:
            name = str(g.get("name", "")).strip()
            if not name:
                continue
            clean.append({
                "name": name,
                "amount": max(0, int(g.get("amount", 0) or 0)),
                "contributors": g.get("contributors") or [],
            })
        save_json(STREAM_FILE, {"lots": clean})
        return jsonify({"ok": True, "count": len(clean)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/save-archive", methods=["POST"])
@login_required
def api_save_archive():
    try:
        data = request.get_json() or {}
        flat = data.get("games") or []
        clean = []
        for g in flat:
            name = str(g.get("name", "")).strip()
            cat = str(g.get("category", "")).strip()
            if not name or not cat:
                continue
            url = str(g.get("url") or "").strip() or None
            try:
                ord_ = int(g.get("order") or 0)
            except (TypeError, ValueError):
                ord_ = 0
            clean.append({"name": name, "category": cat, "url": url, "order": ord_})
        # New games without order go to the end
        max_ord = max((x["order"] for x in clean if x["order"] > 0), default=0)
        for x in clean:
            if x["order"] <= 0:
                max_ord += 1
                x["order"] = max_ord
        nested = nest_archive(clean)
        save_json(COMPLETED_FILE, nested)
        return jsonify({"ok": True, "count": len(clean)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
