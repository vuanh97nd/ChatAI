"""Lựa chọn AI riêng theo tài khoản và địa chỉ dịch vụ, lưu trên máy."""
from .cloud import CLOUD_MODEL, REMOTE_MODELS
from .modules import CHAT_MODELS

DEFAULT_ACCOUNT_MODEL = CLOUD_MODEL


def valid_model(model):
    return model in REMOTE_MODELS or model in CHAT_MODELS


def owner(session):
    return (session['endpoint'].rstrip('/'), session['username'].strip().lower())


def load_model(store, session):
    if not session:
        return NVIDIA_MODEL
    with store.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS account_ai_preferences (endpoint TEXT NOT NULL, username TEXT NOT NULL, model TEXT NOT NULL, PRIMARY KEY(endpoint, username))')
        row = db.execute('SELECT model FROM account_ai_preferences WHERE endpoint=? AND username=?', owner(session)).fetchone()
    return row[0] if row and valid_model(row[0]) else DEFAULT_ACCOUNT_MODEL


def save_model(store, session, model):
    if not session:
        return
    if not valid_model(model):
        raise ValueError('AI không có trong danh mục hỗ trợ.')
    with store.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS account_ai_preferences (endpoint TEXT NOT NULL, username TEXT NOT NULL, model TEXT NOT NULL, PRIMARY KEY(endpoint, username))')
        db.execute('INSERT INTO account_ai_preferences VALUES (?,?,?) ON CONFLICT(endpoint,username) DO UPDATE SET model=excluded.model', (*owner(session), model))
