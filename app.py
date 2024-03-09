from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
from pymongo import MongoClient
app = Flask(__name__)

# ----------------------------------------------------------Authentication--------------------------------------------------------
app.config['SECRET_KEY'] = 'your_secret_key' 
app.config['DATABASE'] = 'database.db'
def connect_db():
    return sqlite3.connect(app.config['DATABASE'], detect_types=sqlite3.PARSE_DECLTYPES)

def create_table():
    with connect_db() as db:
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL
            )
        ''')

        users_data = [('admin', 'admin'), ('user1', 'password1'), ('user2', 'password2')]
        for username, password in users_data:
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            if not user:
                hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))

        db.commit()

create_table()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with connect_db() as db:
            cursor = db.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]

            return redirect(url_for('home'))
        else:
            return render_template('login.html', message='Invalid username or password')

    return render_template('login.html', message='')

# ----------------------------------------------------------Authentication--------------------------------------------------------
# Home route (after successful login)
@app.route('/home')
def home():
    if 'user_id' in session:
        return render_template('userpg.html', username=session['username'])
    else:
        return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)
