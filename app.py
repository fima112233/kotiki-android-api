from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
import sqlite3
import random

app = Flask(__name__)

api = Api(app, version='1.0', title='Котики — Твоё будущее API',
          description='API для котиков: регистрация, лайки, друзья, достижения',
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

# Инициализация базы данных (БЕЗ ТЕСТОВЫХ ДАННЫХ)
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

    conn.commit()
    conn.close()
    print("База данных инициализирована (пустая)")

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

# Регистрация котика
@ns.route('/register')
class RegisterCat(Resource):
    @api.expect(cat_model)
    @api.response(201, 'Котик зарегистрирован')
    def post(self):
        data = request.json
        required = ['name', 'type', 'gender', 'age']
        for field in required:
            if field not in data:
                return {'error': f'Поле {field} обязательно'}, 400

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO cats (name, type, gender, age, breed, description)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['name'], data['type'], data['gender'], data['age'],
              data.get('breed'), data.get('description')))
        cat_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO achievements (cat_id, achievement_type)
            VALUES (?, ?)
        ''', (cat_id, 'first_registration'))

        conn.commit()
        conn.close()

        return {'message': 'Котик зарегистрирован', 'id': cat_id}, 201

# Список котиков с фильтрацией
@ns.route('/cats')
class CatsList(Resource):
    def get(self):
        type_filter = request.args.get('type')
        gender = request.args.get('gender')
        min_age = request.args.get('min_age')
        max_age = request.args.get('max_age')
        search = request.args.get('search')

        query = 'SELECT * FROM cats WHERE 1=1'
        params = []

        if type_filter:
            query += ' AND type = ?'
            params.append(type_filter)
        if gender:
            query += ' AND gender = ?'
            params.append(gender)
        if min_age:
            query += ' AND age >= ?'
            params.append(int(min_age))
        if max_age:
            query += ' AND age <= ?'
            params.append(int(max_age))
        if search:
            query += ' AND name LIKE ?'
            params.append(f'%{search}%')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(query, params)
        cats = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {'cats': cats, 'count': len(cats)}

# Получить котика по ID
@ns.route('/cats/<int:cat_id>')
class CatDetail(Resource):
    def get(self, cat_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM cats WHERE id = ?', (cat_id,))
        cat = cursor.fetchone()
        conn.close()

        if not cat:
            return {'error': 'Котик не найден'}, 404

        return dict(cat)

    def put(self, cat_id):
        if not cat_exists(cat_id):
            return {'error': 'Котик не найден'}, 404

        data = request.json
        conn = get_db()
        cursor = conn.cursor()

        updates = []
        params = []
        for field in ['name', 'type', 'gender', 'age', 'breed', 'description']:
            if field in data:
                updates.append(f'{field} = ?')
                params.append(data[field])

        if not updates:
            return {'error': 'Нет данных для обновления'}, 400

        params.append(cat_id)
        cursor.execute(f'UPDATE cats SET {", ".join(updates)} WHERE id = ?', params)
        conn.commit()
        conn.close()

        return {'message': 'Котик обновлён'}

    def delete(self, cat_id):
        if not cat_exists(cat_id):
            return {'error': 'Котик не найден'}, 404

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM cats WHERE id = ?', (cat_id,))
        cursor.execute('DELETE FROM likes WHERE from_id = ? OR to_id = ?', (cat_id, cat_id))
        cursor.execute('DELETE FROM friends WHERE cat1_id = ? OR cat2_id = ?', (cat_id, cat_id))
        cursor.execute('DELETE FROM achievements WHERE cat_id = ?', (cat_id,))
        conn.commit()
        conn.close()

        return {'message': 'Котик удалён'}

# Поставить лайк
@ns.route('/like')
class LikeCat(Resource):
    @api.expect(like_model)
    def post(self):
        data = request.json
        from_id = data.get('from_id')
        to_id = data.get('to_id')

        if not cat_exists(from_id) or not cat_exists(to_id):
            return {'error': 'Котик не найден'}, 404

        if from_id == to_id:
            return {'error': 'Нельзя лайкать самого себя'}, 400

        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute('INSERT INTO likes (from_id, to_id) VALUES (?, ?)', (from_id, to_id))
            cursor.execute('UPDATE cats SET rating = rating + 1 WHERE id = ?', (to_id,))

            cursor.execute('SELECT COUNT(*) FROM likes WHERE to_id = ?', (to_id,))
            likes_count = cursor.fetchone()[0]
            if likes_count == 1:
                cursor.execute('INSERT INTO achievements (cat_id, achievement_type) VALUES (?, ?)',
                             (to_id, 'first_like'))
            if likes_count == 10:
                cursor.execute('INSERT INTO achievements (cat_id, achievement_type) VALUES (?, ?)',
                             (to_id, 'ten_likes'))

            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return {'error': 'Вы уже лайкали этого котика'}, 400

        conn.close()
        return {'message': 'Лайк поставлен'}

# Получить лайки котика
@ns.route('/cats/<int:cat_id>/likes')
class CatLikes(Resource):
    def get(self, cat_id):
        if not cat_exists(cat_id):
            return {'error': 'Котик не найден'}, 404

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, l.created_at
            FROM likes l
            JOIN cats c ON l.from_id = c.id
            WHERE l.to_id = ?
        ''', (cat_id,))
        likes = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {'likes': likes, 'count': len(likes)}

# Отправить заявку в друзья
@ns.route('/friend/request')
class FriendRequest(Resource):
    @api.expect(friend_request_model)
    def post(self):
        data = request.json
        from_id = data.get('from_id')
        to_id = data.get('to_id')

        if not cat_exists(from_id) or not cat_exists(to_id):
            return {'error': 'Котик не найден'}, 404

        if from_id == to_id:
            return {'error': 'Нельзя дружить с самим собой'}, 400

        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute('INSERT INTO friends (cat1_id, cat2_id, status) VALUES (?, ?, ?)',
                          (min(from_id, to_id), max(from_id, to_id), 'pending'))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return {'error': 'Заявка уже существует'}, 400

        conn.close()
        return {'message': 'Заявка отправлена'}

# Принять/отклонить заявку
@ns.route('/friend/request/<int:request_id>')
class FriendRequestAction(Resource):
    def put(self, request_id):
        data = request.json
        status = data.get('status')

        if status not in ['accepted', 'rejected']:
            return {'error': 'Статус должен быть accepted или rejected'}, 400

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('UPDATE friends SET status = ? WHERE id = ?', (status, request_id))

        if status == 'accepted':
            cursor.execute('SELECT cat1_id, cat2_id FROM friends WHERE id = ?', (request_id,))
            row = cursor.fetchone()
            if row:
                for cat_id in [row['cat1_id'], row['cat2_id']]:
                    cursor.execute('SELECT COUNT(*) FROM friends WHERE (cat1_id = ? OR cat2_id = ?) AND status = "accepted"',
                                  (cat_id, cat_id))
                    friends_count = cursor.fetchone()[0]
                    if friends_count == 1:
                        cursor.execute('INSERT INTO achievements (cat_id, achievement_type) VALUES (?, ?)',
                                      (cat_id, 'first_friend'))

        conn.commit()
        conn.close()

        return {'message': f'Заявка {status}'}

# Список друзей котика
@ns.route('/cats/<int:cat_id>/friends')
class CatFriends(Resource):
    def get(self, cat_id):
        if not cat_exists(cat_id):
            return {'error': 'Котик не найден'}, 404

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, f.status, f.created_at
            FROM friends f
            JOIN cats c ON (c.id = f.cat1_id OR c.id = f.cat2_id)
            WHERE (f.cat1_id = ? OR f.cat2_id = ?) AND c.id != ? AND f.status = 'accepted'
        ''', (cat_id, cat_id, cat_id))
        friends = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {'friends': friends, 'count': len(friends)}

# Достижения котика
@ns.route('/cats/<int:cat_id>/achievements')
class CatAchievements(Resource):
    def get(self, cat_id):
        if not cat_exists(cat_id):
            return {'error': 'Котик не найден'}, 404

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT achievement_type, earned_at FROM achievements WHERE cat_id = ?', (cat_id,))
        achievements = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {'achievements': achievements}

# Котик дня
@ns.route('/cat-of-the-day')
class CatOfTheDay(Resource):
    def get(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM cats ORDER BY rating DESC, RANDOM() LIMIT 1')
        cat = cursor.fetchone()
        conn.close()

        if not cat:
            return {'error': 'Нет котиков'}, 404

        return dict(cat)

# Совместимость между двумя котиками
@ns.route('/match/<int:id1>/<int:id2>')
class Compatibility(Resource):
    def get(self, id1, id2):
        if not cat_exists(id1) or not cat_exists(id2):
            return {'error': 'Котик не найден'}, 404

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM cats WHERE id IN (?, ?)', (id1, id2))
        cats = {row['id']: dict(row) for row in cursor.fetchall()}
        conn.close()

        cat1 = cats[id1]
        cat2 = cats[id2]

        compatibility = 50

        if cat1['type'] == cat2['type']:
            compatibility += 20
        if cat1['gender'] != cat2['gender']:
            compatibility += 10
        if abs(cat1['age'] - cat2['age']) <= 2:
            compatibility += 15
        if cat1.get('breed') and cat2.get('breed') and cat1['breed'] == cat2['breed']:
            compatibility += 15

        compatibility = min(100, compatibility)

        message = "Отличная пара!" if compatibility >= 70 else "Неплохая совместимость" if compatibility >= 50 else "Есть над чем поработать"

        return {
            'cat1': cat1['name'],
            'cat2': cat2['name'],
            'compatibility': compatibility,
            'message': message
        }

# ВАЖНО: вызываем init_db() при старте приложения
init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
