# Прототип корпоративного портала — тестовое задание Platformix
# Backend: Flask + SQLite + JWT-авторизация + Swagger (OpenAPI)

import os
import sqlite3
import datetime
import jwt  # PyJWT — для токенов авторизации
from functools import wraps
from flask import Flask, jsonify, request, render_template, g
from werkzeug.security import generate_password_hash, check_password_hash
from flasgger import Swagger  # Swagger UI — авто-документация API

app = Flask(__name__)

# Секретный ключ для подписи JWT-токенов.
# В реальном проекте берётся из переменных окружения, не хранится в коде.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

# Путь к базе можно задать через переменную окружения (для Docker)
DB_PATH = os.environ.get("DB_PATH", "portal.db")

# ---------- Настройка Swagger ----------
app.config["SWAGGER"] = {
    "title": "Корпоративный портал — API",
    "uiversion": 3,
}
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Корпоративный портал — API",
        "description": "REST API прототипа корпоративного портала. "
                       "Часть эндпоинтов защищена JWT-токеном.",
        "version": "1.0.0",
    },
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT-токен. Формат: Bearer <токен>. "
                           "Токен получается через POST /login.",
        }
    },
}
swagger = Swagger(app, template=swagger_template)


# ---------- Работа с базой ----------

def get_db():
    """Возвращает соединение с базой. Одно на запрос."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Создаёт таблицы и наполняет тестовыми данными при первом запуске."""
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

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123"))
        )

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


# ---------- Авторизация (JWT) ----------

def token_required(f):
    """
    Декоратор: пускает дальше только с правильным JWT-токеном.
    Токен ожидается в заголовке: Authorization: Bearer <токен>
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

        if not token:
            return jsonify({"error": "Требуется токен авторизации"}), 401

        try:
            jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Токен просрочен"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Неверный токен"}), 401

        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["POST"])
def login():
    """
    Авторизация и получение JWT-токена.
    ---
    tags:
      - Авторизация
    parameters:
      - in: body
        name: credentials
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
              example: admin
            password:
              type: string
              example: admin123
    responses:
      200:
        description: Токен успешно выдан
      401:
        description: Неверный логин или пароль
    """
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Неверный логин или пароль"}), 401

    token = jwt.encode(
        {
            "username": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8),
        },
        app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    return jsonify({"token": token})


# ---------- Страница ----------

@app.route("/")
def index():
    return render_template("index.html")


# ---------- API документов ----------

@app.route("/documents", methods=["GET"])
def get_documents():
    """
    Список документов (с поиском).
    ---
    tags:
      - Документы
    parameters:
      - in: query
        name: q
        type: string
        required: false
        description: Поисковый запрос (по названию, тексту, категории)
    responses:
      200:
        description: Список документов
    """
    q = request.args.get("q", "").strip().lower()
    db = get_db()

    rows = db.execute(
        "SELECT id, title, category, author, content, created_at FROM documents "
        "ORDER BY created_at DESC"
    ).fetchall()

    docs = [dict(r) for r in rows]

    if q:
        docs = [
            d for d in docs
            if q in d["title"].lower()
            or q in d["content"].lower()
            or q in d["category"].lower()
        ]

    for d in docs:
        d.pop("content")

    return jsonify(docs)


@app.route("/documents/<int:doc_id>", methods=["GET"])
def get_document(doc_id):
    """
    Карточка одного документа.
    ---
    tags:
      - Документы
    parameters:
      - in: path
        name: doc_id
        type: integer
        required: true
        description: ID документа
    responses:
      200:
        description: Документ найден
      404:
        description: Документ не найден
    """
    db = get_db()
    row = db.execute(
        "SELECT * FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()

    if row is None:
        return jsonify({"error": "Документ не найден"}), 404

    return jsonify(dict(row))


@app.route("/documents", methods=["POST"])
@token_required
def create_document():
    """
    Создание нового документа (требует авторизации).
    ---
    tags:
      - Документы
    security:
      - Bearer: []
    parameters:
      - in: body
        name: document
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
              example: Регламент использования корпоративной почты
            category:
              type: string
              example: Регламенты
            author:
              type: string
              example: Тишаков Д.А.
            content:
              type: string
              example: Текст документа
    responses:
      201:
        description: Документ создан
      400:
        description: Не заполнены обязательные поля
      401:
        description: Требуется авторизация
    """
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Нужен JSON в теле запроса"}), 400

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
            datetime.datetime.now().strftime("%Y-%m-%d"),
        )
    )
    db.commit()

    new_doc = db.execute(
        "SELECT * FROM documents WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()

    return jsonify(dict(new_doc)), 201


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", debug=True, port=8080)
