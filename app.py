# Прототип корпоративного портала — тестовое задание Platformix
# Backend: Flask + SQLite

import os
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request, render_template, g

app = Flask(__name__)
# Путь к базе можно задать через переменную окружения (для Docker),
# иначе база создаётся рядом с app.py
DB_PATH = os.environ.get("DB_PATH", "portal.db")


# ---------- Работа с базой ----------

def get_db():
    """Возвращает соединение с базой. Одно на запрос."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row  # чтобы получать строки как словари
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Создаёт таблицу и наполняет тестовыми данными при первом запуске."""
    # Если база лежит в подпапке (как в Docker) — создаём папку
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Если таблица пустая — добавляем mock-данные
    count = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    if count == 0:
        mock_docs = [
            ("Регламент удалённой работы", "Регламенты", "Иванова А.П.",
             "Порядок оформления удалённого формата работы: заявка руководителю, "
             "настройка VPN, правила доступности в рабочие часы с 10:00 до 18:00.",
             "2025-11-12"),
            ("Инструкция по работе с СЭД", "Инструкции", "Петров С.В.",
             "Пошаговая инструкция по системе электронного документооборота: "
             "создание документа, согласование, подписание, архивирование.",
             "2025-10-03"),
            ("Положение об отпусках", "Кадровые документы", "Сидорова М.И.",
             "График отпусков утверждается до 15 декабря. Заявление подаётся "
             "за 2 недели. Отпуск делится на части, одна из которых не менее 14 дней.",
             "2025-09-20"),
            ("Шаблон коммерческого предложения", "Шаблоны", "Козлов Д.А.",
             "Корпоративный шаблон КП: титульный лист, описание решения, "
             "смета, сроки внедрения, контакты менеджера.",
             "2026-01-15"),
            ("Регламент информационной безопасности", "Регламенты", "Волкова Е.Н.",
             "Правила работы с корпоративными данными: пароли не короче 12 символов, "
             "двухфакторная аутентификация, запрет передачи учётных данных.",
             "2026-02-01"),
            ("Инструкция по заведению заявок в HelpDesk", "Инструкции", "Морозов П.К.",
             "Заявки в техподдержку создаются через портал HelpDesk. Указывается "
             "категория, приоритет и описание проблемы. SLA — 4 рабочих часа.",
             "2026-03-10"),
        ]
        db.executemany(
            "INSERT INTO documents (title, category, author, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            mock_docs
        )
        db.commit()
    db.close()


# ---------- Страница ----------

@app.route("/")
def index():
    return render_template("index.html")


# ---------- API ----------

@app.route("/documents", methods=["GET"])
def get_documents():
    """Список документов. Поддерживает поиск: /documents?q=текст"""
    q = request.args.get("q", "").strip().lower()
    db = get_db()

    rows = db.execute(
        "SELECT id, title, category, author, content, created_at FROM documents "
        "ORDER BY created_at DESC"
    ).fetchall()

    docs = [dict(r) for r in rows]

    # Поиск делаем на Python: LIKE в SQLite не понимает регистр кириллицы
    if q:
        docs = [
            d for d in docs
            if q in d["title"].lower()
            or q in d["content"].lower()
            or q in d["category"].lower()
        ]

    # content в списке не нужен — он только для карточки
    for d in docs:
        d.pop("content")

    return jsonify(docs)


@app.route("/documents/<int:doc_id>", methods=["GET"])
def get_document(doc_id):
    """Карточка одного документа."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()

    if row is None:
        return jsonify({"error": "Документ не найден"}), 404

    return jsonify(dict(row))


@app.route("/documents", methods=["POST"])
def create_document():
    """Создание нового документа."""
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Нужен JSON в теле запроса"}), 400

    # Проверяем обязательные поля
    for field in ("title", "category", "author", "content"):
        if not data.get(field, "").strip():
            return jsonify({"error": f"Поле '{field}' обязательно"}), 400

    db = get_db()
    cursor = db.execute(
        "INSERT INTO documents (title, category, author, content, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            data["title"].strip(),
            data["category"].strip(),
            data["author"].strip(),
            data["content"].strip(),
            datetime.now().strftime("%Y-%m-%d"),
        )
    )
    db.commit()

    new_doc = db.execute(
        "SELECT * FROM documents WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()

    return jsonify(dict(new_doc)), 201


if __name__ == "__main__":
    init_db()
    # host="0.0.0.0" нужен чтобы приложение было доступно из Docker-контейнера
    app.run(host="0.0.0.0", debug=True, port=8080)
