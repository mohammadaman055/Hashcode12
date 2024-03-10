import sqlite3
import win32api
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
import os
from pymongo import MongoClient
import threading
import time
from PyPDF2 import PdfReader

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
            if user[1] == 'admin':
                return redirect(url_for('admin'))  
            else:
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

num_pages=0

@app.route('/upload', methods=['POST'])
def upload():
    if 'username' in session:
        
        create_upload_folder()

        if request.method == 'POST':
            name = session['name']
            fileType = session['fileType']
            blackWhitePrint = session['blackWhitePrint']
            colorPrint = session['colorPrint']
            twoside = session['twoside']
            quantity = session['quantity']
            file_path = session['filepath']
            cost = session['cost']

            data = {
                'name': name,
                'fileType': fileType,
                'blackWhitePrint': blackWhitePrint,
                'colorPrint': colorPrint,
                'twoside': twoside,
                'quantity': quantity,
                'filepath': file_path,
                'cost': cost,
            }
            collection.insert_one(data)
            
            return redirect(url_for('printjob'))

        return render_template('userpg.html', username=session['username'])
    else:
        return redirect(url_for('login'))

@app.route('/payment',methods=['GET', 'POST'])
def payment():
    if 'username' in session:
        def analyze_file(file):
            if file and file.filename.endswith('.pdf'):
                pdf_reader = PdfReader(file)
                return len(pdf_reader.pages)
            else:
                return 0
            
        if request.method == 'POST':
            file = request.files['file']
            if file:
                filename = file.filename
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                threading.Thread(target=delete_file_after_delay, args=(file_path, 30)).start()
                
                global num_pages
                num_pages = analyze_file(file)
    
        if request.method == 'POST':
            name = request.form['name']
            fileType = request.form['fileType']
            blackWhitePrint = request.form.get('blackWhitePrint', False) == 'on'
            colorPrint = request.form.get('colorPrint', False) == 'on'
            twoside = request.form.get('twoside', False) == 'on'
            quantity = request.form['quantity']
            file = request.files['file']   

            session['name'] = name
            session['fileType'] = fileType
            session['blackWhitePrint'] = blackWhitePrint
            session['colorPrint'] = colorPrint
            session['twoside'] = twoside
            session['quantity'] = quantity
            session['filepath']=file_path

            data = {
                    'name': name,
                    'fileType': fileType,
                    'blackWhitePrint': blackWhitePrint,
                    'colorPrint': colorPrint,
                    'twoside': twoside,
                    'quantity': quantity,
                }

            cost = 0
            black_white_price_per_page = 2
            color_price_per_page = 10

            if data.get('blackWhitePrint', False):
                    cost = black_white_price_per_page * num_pages * int(data['quantity'])
            if data.get('colorPrint', False):
                    cost = color_price_per_page * num_pages* int(data['quantity'])

            if data.get('twoside', False):
                    black_white_price_per_page = 4
                    color_price_per_page = 14
                    if data.get('blackWhitePrint', False):
                        cost = black_white_price_per_page * int(num_pages/2)* int(data['quantity'])
                    if data.get('colorPrint', False):
                        cost = color_price_per_page * int(num_pages/2)* int(data['quantity'])
            
            session['cost']=cost
        return render_template('payment.html', data=data, cost=cost)
    else:
            return redirect(url_for('upload'))

def print_file(file_path, printer_name=None):
    try:
        if not os.path.exists(file_path):
            print("File not found.")
            return
        
        if printer_name is not None:
            win32api.ShellExecute(0, "printto", file_path, f'"{printer_name}"', ".", 0)
        else:
            win32api.ShellExecute(0, "print", file_path, None, ".", 0)
        
        print("Printing job started successfully.")
    except Exception as e:
        print("An error occurred:", e)


@app.route('/printjob')
def printjob():
    latest_print_job = get_latest_print_job()
    if latest_print_job:
        file_path = latest_print_job.get('filepath')
        if file_path:
            print_file(file_path)
    
    return redirect(url_for('success')) 

def get_latest_print_job():
    try:
        latest_print_job = collection.find_one(sort=[('_id', -1)])
        if latest_print_job:
            return latest_print_job
        else:
            print("No print job found.")
            return None
    except Exception as e:
        print("An error occurred while retrieving the latest print job:", e)
        return None

@app.route('/success')
def success():
    return render_template('success.html')


from flask import render_template

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'GET':
        client = MongoClient('mongodb://localhost:27017/')
        db = client['HashCode12']
        collection = db['PrintJobs']
        print_jobs = collection.find({}, {"_id": 0})  
        
        total_jobs = 0
        total_earning = 0
        
        print_jobs = list(print_jobs)
        for job in print_jobs:
            total_jobs += 1
            total_earning += job['cost']
        
        return render_template('admin.html', print_jobs=print_jobs, total_jobs=total_jobs, total_earning=total_earning)
    elif request.method == 'POST':
        pass


if __name__ == "__main__":
    app.run(debug=True)
