from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
import sqlite3
import random
from datetime import datetime

app = Flask(__name__)

api = Api(app, version='1.0', title='Котики — Твоё будущее API',
          description='API для котиков: регистрация, лайки, друзья, достижения, чат',
          doc='/api/docs')

ns = api.namespace('api', description='Операции с котиками')

# Модели для Swagger
cat_model = api.model('Cat', {
    'name': fields.String(required=True, description='Имя котика'),
    'type': fields.String(required=True, description='Тип (cat, dog, hamster и т.д.)'),
    'gender': fields.String(required=True, description='Пол (male/female)'),
    'age': fields.Integer(required=True, description='Возраст (в годах)'),
    'breed': fields.String(description='Порода'),
    'description': fields.String(description='Описание')
})

like_model = api.model('Like', {
    'from_id': fields.Integer(required=True, description='Кто лайкает'),
    'to_id': fields.Integer(required=True, description='Кого лайкают')
})

friend_request_model = api.model('FriendRequest', {
    'from_id': fields.Integer(required=True, description='Кто отправляет'),
    'to_id': fields.Integer(required=True, description='Кому отправляют')
})

message_model = api.model('Message', {
    'from_id': fields.Integer(required=True, description='Кто пишет'),
    'to_id': fields.Integer(required=True, description='Кому пишут'),
    'text': fields.String(required=True, description='Текст сообщения')
})

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('cats.db')
    cursor = conn.cursor()

    # Таблица котиков
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            gender TEXT NOT NULL,
            age INTEGER NOT NULL,
            breed TEXT,
            description TEXT,
            rating INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица лайков
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id INTEGER NOT NULL,
            to_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(from_id, to_id)
        )
    ''')

    # Таблица друзей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cat1_id INTEGER NOT NULL,
            cat2_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(cat1_id, cat2_id)
        )
    ''')

    # Таблица достижений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cat_id INTEGER NOT NULL,
            achievement_type TEXT NOT NULL,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # НОВОЕ: Таблица сообщений (чат)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id INTEGER NOT NULL,
            to_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("База данных инициализирована (с чатом)")

def get_db():
    conn = sqlite3.connect('cats.db')
    conn.row_factory = sqlite3.Row
    return conn

def cat_exists(cat_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM cats WHERE id = ?', (cat_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

# ---------- ОСТАЛЬНЫЕ ЭНДПОИНТЫ (лайки, друзья, достижения) ЗДЕСЬ БЫЛИ, НО ДЛЯ КРАТКОСТИ ОПУЩЕНЫ ----------
# (они такие же, как в прошлой версии)

# ========== НОВЫЙ РАЗДЕЛ: ЧАТ (МЕССЕНДЖЕР) ==========

# Отправить сообщение
@ns.route('/messages/send')
class SendMessage(Resource):
    @api.expect(message_model)
    def post(self):
        data = request.json
        from_id = data.get('from_id')
        to_id = data.get('to_id')
        text = data.get('text')

        if not cat_exists(from_id) or not cat_exists(to_id):
            return {'error': 'Котик не найден'}, 404

        if not text or len(text.strip()) == 0:
            return {'error': 'Текст сообщения не может быть пустым'}, 400

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (from_id, to_id, text)
            VALUES (?, ?, ?)
        ''', (from_id, to_id, text))
        message_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {'message': 'Сообщение отправлено', 'id': message_id}, 201

# Получить все сообщения для котика
@ns.route('/messages/<int:cat_id>')
class GetMessages(Resource):
    def get(self, cat_id):
        if not cat_exists(cat_id):
            return {'error': 'Котик не найден'}, 404

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.*, 
                   sender.name as sender_name, 
                   receiver.name as receiver_name
            FROM messages m
            JOIN cats sender ON m.from_id = sender.id
            JOIN cats receiver ON m.to_id = receiver.id
            WHERE m.to_id = ?
            ORDER BY m.created_at DESC
        ''', (cat_id,))
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {'messages': messages, 'count': len(messages)}

# Переписка между двумя котиками
@ns.route('/messages/conversation/<int:cat1_id>/<int:cat2_id>')
class Conversation(Resource):
    def get(self, cat1_id, cat2_id):
        if not cat_exists(cat1_id) or not cat_exists(cat2_id):
            return {'error': 'Котик не найден'}, 404

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.*, 
                   sender.name as sender_name, 
                   receiver.name as receiver_name
            FROM messages m
            JOIN cats sender ON m.from_id = sender.id
            JOIN cats receiver ON m.to_id = receiver.id
            WHERE (m.from_id = ? AND m.to_id = ?) OR (m.from_id = ? AND m.to_id = ?)
            ORDER BY m.created_at ASC
        ''', (cat1_id, cat2_id, cat2_id, cat1_id))
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {'conversation': messages, 'count': len(messages)}

# Пометить сообщение как прочитанное
@ns.route('/messages/read/<int:message_id>')
class MarkAsRead(Resource):
    def put(self, message_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE messages SET is_read = 1 WHERE id = ?', (message_id,))
        conn.commit()
        conn.close()

        return {'message': 'Сообщение помечено как прочитанное'}

# Вызываем init_db() при старте приложения
init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
