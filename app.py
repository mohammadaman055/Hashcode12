import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
import os
from pymongo import MongoClient
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key' 
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
@app.route('/home')
def home():
    if 'user_id' in session:
        return render_template('userpg.html', username=session['username'])
    else:
        return redirect(url_for('login'))


UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

client = MongoClient('mongodb://localhost:27017/')
db = client['HashCode12']
collection = db['PrintJobs']

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def create_upload_folder():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

def delete_file_after_delay(filename, delay):
    time.sleep(delay)
    try:
        os.remove(filename)
    except FileNotFoundError:
        pass

@app.route('/upload', methods=['POST'])
def upload_and_store_file():
    if 'username' in session:
        create_upload_folder()
        if request.method == 'POST':
            file = request.files['file']
            if file:
                filename = file.filename
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                threading.Thread(target=delete_file_after_delay, args=(file_path, 30)).start()

        if request.method == 'POST':
            name = request.form['name']
            fileType = request.form['fileType']
            blackWhitePrint = request.form.get('blackWhitePrint', False) == 'on'
            colorPrint = request.form.get('colorPrint', False) == 'on'
            twoside = request.form.get('twoside', False) == 'on'
            quantity = request.form['quantity']

            data = {
                'name': name,
                'fileType': fileType,
                'blackWhitePrint': blackWhitePrint,
                'colorPrint': colorPrint,
                'twoside': twoside,
                'quantity': quantity,
                'filepath': file_path
            }
            collection.insert_one(data)
            return redirect(url_for('success'))

        return render_template('userpg.html', username=session['username'])
    else:
        return redirect(url_for('login'))

@app.route('/success')
def success():
    return 'Data successfully stored in MongoDB!'

if __name__ == "__main__":
    app.run(debug=True)
