from datetime import timedelta  # Aggiungi questa riga agli import
import os
from dotenv import load_dotenv  # Import dotenv for local development

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import random
import plotly
import plotly.graph_objs as go
import json
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from contextlib import contextmanager
import re
import smtplib
from random import randint
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_session import Session

load_dotenv()  # Load variables from .env file

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Email credentials (use environment variables)
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
# Configura Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'  # Memorizza la sessione nel filesystem
Session(app)

@contextmanager
def get_db_connection():
    conn = sqlite3.connect('database.db', timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def create_db():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                is_verified BOOLEAN NOT NULL DEFAULT 0
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                creator_id INTEGER,
                FOREIGN KEY (creator_id) REFERENCES users(id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS quiz (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,  -- Contiene le risposte corrette separate da virgola
                option1 TEXT NOT NULL,
                option2 TEXT NOT NULL,
                option3 TEXT,  -- Opzionale
                option4 TEXT,  -- Opzionale
                option5 TEXT,  -- Opzionale
                FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question_id INTEGER,
                user_answer TEXT NOT NULL,  -- Risposte utente separate da virgola
                is_correct BOOLEAN NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (question_id) REFERENCES quiz (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS shared_quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER,
                shared_with_user_id INTEGER,
                FOREIGN KEY (quiz_id) REFERENCES quizzes (id),
                FOREIGN KEY (shared_with_user_id) REFERENCES users (id)
            )
        ''')
        conn.commit()

def update_db_structure():
    with get_db_connection() as conn:
        try:
            conn.execute('ALTER TABLE quiz ADD COLUMN option5 TEXT')
            conn.commit()
            print("Colonna option5 aggiunta con successo alla tabella quiz.")
        except sqlite3.OperationalError:
            print("La colonna option5 esiste già nella tabella quiz.")

create_db()
update_db_structure()

def process_quiz_file(filepath, creator_id):
    with open(filepath, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    quiz_name = lines[0].strip()
    print(f"Quiz Name: {quiz_name}")  # Debugging

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('BEGIN IMMEDIATE')

        try:
            cursor.execute('INSERT INTO quizzes (name, creator_id) VALUES (?, ?)', (quiz_name, creator_id))
            quiz_id = cursor.lastrowid
            conn.commit()
            session['selected_quiz_id'] = quiz_id
        except sqlite3.IntegrityError:
            flash(f'Quiz "{quiz_name}" already exists. Try a new quiz.', 'error')
            return

        i = 1
        while i < len(lines):
            question = lines[i].strip()
            i += 1
            print(f"Processing question: {question}")  # Debugging

            if i >= len(lines) or not lines[i].strip().isdigit():
                flash(f"Error in file format for question: '{question}'", 'error')
                print(f"Expected number of answers after question: '{question}', found: '{lines[i]}'")  # Debugging
                return

            num_answers = int(lines[i].strip())
            print(f"Number of answers: {num_answers}")  # Debugging

            if num_answers < 2:
                flash(f"Question '{question}' must have at least 2 answers.", 'error')
                return

            i += 1

            correct_answers = []
            options = []

            for j in range(num_answers):
                if i < len(lines):
                    line = lines[i].strip()
                    print(f"Reading answer: {line}")  # Debugging
                    if line.startswith('*'):
                        correct_answers.append(line.lstrip('*'))  # Remove '*' for correct answer
                    options.append(line.lstrip('*'))  # Add the answer option
                    i += 1

            while len(options) < 5:
                options.append("")  # Fill with empty strings to make sure we have 5 columns

            correct_answer_str = ','.join(correct_answers)
            print(f"Inserting question: {question}, options: {options}, correct answers: {correct_answer_str}")  # Debugging

            cursor.execute(
                'INSERT INTO quiz (quiz_id, question, answer, option1, option2, option3, option4, option5) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (quiz_id, question, correct_answer_str, options[0], options[1], options[2], options[3], options[4])
            )

        conn.commit()
        print("Quiz uploaded successfully!")  # Debugging





def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    user_quizzes = []
    if 'user_id' in session:
        user_id = session['user_id']
        with get_db_connection() as conn:
            user_quizzes = conn.execute('SELECT * FROM quizzes WHERE creator_id = ?', (user_id,)).fetchall()
    
    return render_template('index.html', user_quizzes=user_quizzes)

@app.route('/upload_quiz', methods=['POST'])
def upload_quiz():
    if 'user_id' not in session:
        flash('Please log in to upload a quiz', 'danger')
        return redirect(url_for('login'))

    if 'quiz_file' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('index'))

    file = request.files['quiz_file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        if len(file.read()) > 2 * 1024 * 1024:  # Limit file size to 2 MB
            flash('File size exceeds the 2MB limit', 'danger')
            return redirect(url_for('index'))

        file.seek(0)  # Reset file pointer after checking size

        # Assicurati che la directory esista
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        process_quiz_file(filepath, session['user_id'])
        os.remove(filepath)  # Remove file after processing

        # Ensure the selected quiz id is set after processing the file
        if 'selected_quiz_id' in session:
            flash('Quiz uploaded successfully!', 'success')
            return redirect(url_for('quiz'))
        else:
            flash('Failed to process the quiz.', 'danger')
            return redirect(url_for('index'))

    flash('Unsupported file type', 'danger')
    return redirect(url_for('index'))


def row_to_dict(row):
    return {key: row[key] for key in row.keys()}

@app.route('/quiz', methods=['GET'])
def quiz():
    if 'selected_quiz_id' not in session:
        flash('No quiz selected.', 'warning')
        return redirect(url_for('select_quiz'))

    # Fetch the quiz and its questions
    with get_db_connection() as conn:
        quiz_id = session.get('selected_quiz_id')
        quiz_questions = conn.execute('SELECT * FROM quiz WHERE quiz_id = ? ORDER BY id', (quiz_id,)).fetchall()

    if not quiz_questions:
        flash('The selected quiz has no questions.', 'warning')
        return redirect(url_for('select_quiz'))

    # Initialize session variables if this is the start of the quiz
    if 'questions' not in session or 'current_question' not in session:
        shuffled_questions = [row_to_dict(q) for q in quiz_questions]
        random.shuffle(shuffled_questions)  # Mescola le domande
        
        for question in shuffled_questions:
            options = [question['option1'], question['option2'], question.get('option3'), question.get('option4'), question.get('option5')]
            options = [opt for opt in options if opt]  # Filtra le opzioni vuote
            correct_answers = set(question['answer'].split(','))  # Risposte corrette originali
            random.shuffle(options)  # Mescola le opzioni

            # Mantieni traccia delle risposte corrette nell'ordine mescolato
            shuffled_correct_answers = [opt for opt in options if opt in correct_answers]
            
            question['shuffled_options'] = options
            question['shuffled_correct_answers'] = shuffled_correct_answers
        
        session['questions'] = shuffled_questions  # Carica le domande mescolate nella sessione
        session['current_question'] = 0  # Inizia dalla prima domanda
        session['correct_answers'] = 0  # Reset della conta delle risposte corrette

    current_question_index = session['current_question']

    # Se tutte le domande sono completate, reindirizza alla pagina di completamento
    if current_question_index >= len(session['questions']):
        return redirect(url_for('quiz_completed'))

    question = session['questions'][current_question_index]

    # Passa la domanda mescolata e l'ordine delle risposte al template
    return render_template('quiz.html',
                           question=question,
                           question_number=current_question_index + 1,
                           total_questions=len(session['questions']),
                           options=question['shuffled_options'])




@app.route('/next_question', methods=['POST'])
def next_question():
    if 'feedback' in session:
        session.pop('feedback')  # Remove feedback before moving to the next question

    # La domanda verrà già avanzata in `submit_answer`, quindi rimuovi l'incremento qui
    # session['current_question'] = session.get('current_question', 0) + 1

    # Se tutte le domande sono state risposte, vai alla pagina di completamento del quiz
    if session['current_question'] >= len(session['questions']):
        return redirect(url_for('quiz_completed'))

    return redirect(url_for('quiz'))

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    if 'selected_quiz_id' not in session or 'current_question' not in session:
        flash('Invalid quiz or session expired. Please try again.', 'warning')
        return redirect(url_for('take_quiz', quiz_id=session.get('selected_quiz_id')))

    quiz_id = session['selected_quiz_id']
    current_question_index = session['current_question']

    # Recupera la domanda corrente dalla sessione
    if 'questions' not in session or current_question_index >= len(session['questions']):
        flash('Invalid quiz or session expired. Please try again.', 'warning')
        return redirect(url_for('take_quiz', quiz_id=quiz_id))

    question = session['questions'][current_question_index]

    # Filtra le risposte vuote e raccogli le risposte selezionate dall'utente
    user_answers = set(answer.strip() for answer in request.form.getlist('answer') if answer.strip())
    
    # Confronta con le risposte corrette
    correct_answers = set(question['answer'].split(','))

    # Verifica se l'utente ha risposto correttamente
    is_correct = user_answers == correct_answers

    # Salva il feedback nella sessione
    session['feedback'] = {
        'is_correct': is_correct,
        'correct_answers': ', '.join(correct_answers)  # Mostra le risposte corrette all'utente
    }

    if is_correct:
        session['correct_answers'] += 1

    # Passa alla prossima domanda
    session['current_question'] += 1

    # Reindirizza alla prossima domanda o al feedback
    if session['current_question'] >= len(session['questions']):
        return redirect(url_for('quiz_completed'))

    return redirect(url_for('quiz_feedback'))










@app.route('/quiz_feedback', methods=['GET'])
def quiz_feedback():
    # Verifica che il feedback e le domande siano ancora presenti nella sessione
    if 'feedback' not in session or 'selected_quiz_id' not in session:
        flash('Invalid quiz or session expired.', 'warning')
        return redirect(url_for('take_quiz', quiz_id=session.get('selected_quiz_id')))

    feedback = session.pop('feedback', None)
    question_number = session['current_question']
    total_questions = len(session['questions'])

    # Se tutte le domande sono completate, gestisci il termine del quiz
    if question_number >= total_questions:
        return redirect(url_for('quiz_completed'))

    return render_template('quiz_feedback.html',
                           feedback=feedback,
                           question_number=question_number,
                           total_questions=total_questions)







@app.route('/quiz_completed')
def quiz_completed():
    if 'questions' not in session or 'correct_answers' not in session:
        flash('No quiz in progress.', 'warning')
        return redirect(url_for('select_quiz'))

    total_questions = len(session['questions'])
    correct_answers = session['correct_answers']
    score = (correct_answers / total_questions) * 100

    # Pulisci le variabili di sessione una volta completato il quiz
    session.pop('current_question', None)
    session.pop('correct_answers', None)
    session.pop('questions', None)
    session.pop('selected_quiz_id', None)

    return render_template('quiz_completed.html', score=score, total=total_questions, correct=correct_answers)



# Fix 5: Avoid division by zero in 'statistics'
@app.route('/statistics')
def statistics():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    with get_db_connection() as conn:
        total_answers = conn.execute('SELECT COUNT(*) FROM user_answers WHERE user_id = ?', (user_id,)).fetchone()[0]
        correct_answers = conn.execute('SELECT COUNT(*) FROM user_answers WHERE user_id = ? AND is_correct = 1', (user_id,)).fetchone()[0]

        accuracy = (correct_answers / total_answers) * 100 if total_answers > 0 else 0

        most_difficult = conn.execute('''
            SELECT q.question, COUNT(*) as incorrect_count
            FROM user_answers ua
            JOIN quiz q ON ua.question_id = q.id
            WHERE ua.is_correct = 0 AND ua.user_id = ?
            GROUP BY ua.question_id
            ORDER BY incorrect_count DESC
            LIMIT 1
        ''', (user_id,)).fetchone()

        question_stats = conn.execute('''
            SELECT q.question, 
                   SUM(CASE WHEN ua.is_correct THEN 1 ELSE 0 END) as correct,
                   SUM(CASE WHEN ua.is_correct THEN 0 ELSE 1 END) as incorrect
            FROM quiz q
            LEFT JOIN user_answers ua ON q.id = ua.question_id AND ua.user_id = ?
            GROUP BY q.id
        ''', (user_id,)).fetchall()

    questions = [stat['question'] for stat in question_stats]
    correct = [stat['correct'] for stat in question_stats]
    incorrect = [stat['incorrect'] for stat in question_stats]

    trace1 = go.Bar(x=questions, y=correct, name='Correct Answers')
    trace2 = go.Bar(x=questions, y=incorrect, name='Incorrect Answers')

    data = [trace1, trace2]
    layout = go.Layout(barmode='stack', title='Question Statistics')
    fig = go.Figure(data=data, layout=layout)

    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return render_template('statistics.html',
                           total_answers=total_answers,
                           correct_answers=correct_answers,
                           accuracy=accuracy,
                           most_difficult=most_difficult,
                           graphJSON=graphJSON)

def send_verification_email(recipient_email, code):
    sender_email = EMAIL_USER
    sender_password = EMAIL_PASSWORD
    subject = "Il tuo codice di verifica"
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    body = f"Il tuo codice di verifica è: {code}"
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.close()
    except Exception as e:
        print(f"Impossibile inviare l'email: {e}")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        if not re.match(r'^[\w\.-]+@gmail\.com$', email):
            flash('Sono consentiti solo indirizzi Gmail', 'error')
            return redirect(url_for('register'))

        verification_code = randint(100000, 999999)
        session['verification_code'] = verification_code
        session['temp_user'] = {'username': username, 'password': generate_password_hash(password), 'email': email}
        
        send_verification_email(email, verification_code)
        flash('Un codice di verifica è stato inviato al tuo Gmail', 'success')
        return redirect(url_for('verify_email'))
    
    return render_template('register.html')

@app.route('/verify_email', methods=['GET', 'POST'])
def verify_email():
    if request.method == 'POST':
        input_code = request.form['verification_code']
        if input_code == str(session.get('verification_code')):
            with get_db_connection() as conn:
                user = session.pop('temp_user', None)
                conn.execute('INSERT INTO users (username, password, email, is_verified) VALUES (?, ?, ?, ?)', 
                             (user['username'], user['password'], user['email'], 1))
                conn.commit()
            flash('Registrazione completata con successo!', 'success')
            return redirect(url_for('login'))
        else:
            flash('Codice di verifica non valido', 'error')
    
    return render_template('verify_email.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with get_db_connection() as conn:
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                return redirect(url_for('index'))
        flash('Username o password non validi', 'error')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('index'))

def insert_question(quiz_id, question, answer, option1, option2, option3, option4, option5):
    with get_db_connection() as conn:
        conn.execute('INSERT INTO quiz (quiz_id, question, answer, option1, option2, option3, option4, option5) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                     (quiz_id, question, answer, option1, option2, option3, option4, option5))
        conn.commit()

@app.route('/add_quiz', methods=['GET', 'POST'])
def add_quiz():
    if 'user_id' not in session:
        flash('Devi effettuare il login per creare un quiz', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        quiz_name = request.form.get('quiz_name')
        if not quiz_name:
            flash('Il nome del quiz è obbligatorio', 'danger')
            return redirect(url_for('add_quiz'))
        
        creator_id = session['user_id']
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('BEGIN IMMEDIATE')
            try:
                cursor.execute('INSERT INTO quizzes (name, creator_id) VALUES (?, ?)', (quiz_name, creator_id))
                quiz_id = cursor.lastrowid
                conn.commit()
                flash('Quiz creato con successo!', 'success')
                return redirect(url_for('add_question', quiz_name=quiz_name))
            except sqlite3.Error as e:
                conn.rollback()
                flash(f'Errore durante l\'aggiunta del quiz: {str(e)}', 'error')
                return redirect(url_for('add_quiz'))
    
    return render_template('add_quiz.html')


@app.route('/add_question/<quiz_name>', methods=['GET', 'POST'])
def add_question(quiz_name):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with get_db_connection() as conn:
        quiz = conn.execute('SELECT * FROM quizzes WHERE name = ? AND creator_id = ?', (quiz_name, session['user_id'])).fetchone()

    if not quiz:
        flash('Non hai il permesso di modificare questo quiz', 'danger')
        return redirect(url_for('my_quizzes'))

    if request.method == 'POST':
        question = request.form['question']
        answer = request.form['answer']
        option1 = request.form['option1']
        option2 = request.form['option2']

        if not option1 or not option2:
            flash('At least two options are required.', 'danger')
            return redirect(url_for('add_question', quiz_name=quiz_name))

        option3 = request.form.get('option3', '')
        option4 = request.form.get('option4', '')
        option5 = request.form.get('option5', '')

        insert_question(quiz['id'], question, answer, option1, option2, option3, option4, option5)
        flash('Domanda aggiunta con successo', 'success')
        return redirect(url_for('add_question', quiz_name=quiz_name))

    return render_template('add_question.html', quiz_name=quiz_name)

@app.route('/select_quiz', methods=['GET', 'POST'])
def select_quiz():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    with get_db_connection() as conn:
        own_quizzes = conn.execute('SELECT id, name FROM quizzes WHERE creator_id = ?', (user_id,)).fetchall()
        shared_quizzes = conn.execute('''
            SELECT q.id, q.name 
            FROM quizzes q
            JOIN shared_quizzes sq ON q.id = sq.quiz_id
            WHERE sq.shared_with_user_id = ?
        ''', (user_id,)).fetchall()

        all_quizzes = own_quizzes + shared_quizzes

    if request.method == 'POST':
        selected_quiz_id = request.form['quiz_id']
        session['selected_quiz_id'] = selected_quiz_id

        # Resetta la sessione per il nuovo quiz
        session.pop('questions', None)
        session.pop('current_question', None)
        session.pop('correct_answers', None)

        return redirect(url_for('quiz'))

    return render_template('select_quiz.html', quizzes=all_quizzes)



@app.route('/my_quizzes')
def my_quizzes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    with get_db_connection() as conn:
        quizzes = conn.execute('SELECT * FROM quizzes WHERE creator_id = ?', (user_id,)).fetchall()
    
    return render_template('my_quizzes.html', quizzes=quizzes)

@app.route('/edit_quiz/<int:quiz_id>', methods=['GET', 'POST'])
def edit_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with get_db_connection() as conn:
        quiz = conn.execute('SELECT * FROM quizzes WHERE id = ? AND creator_id = ?', (quiz_id, session['user_id'])).fetchone()
    
        if not quiz:
            flash('Non hai il permesso di modificare questo quiz', 'danger')
            return redirect(url_for('my_quizzes'))

        questions = conn.execute('SELECT * FROM quiz WHERE quiz_id = ?', (quiz_id,)).fetchall()
    
        if request.method == 'POST':
            question_id = request.form['question_id']
            question_text = request.form['question']
            option1 = request.form['option1']
            option2 = request.form['option2']
            option3 = request.form['option3']
            option4 = request.form['option4']
            option5 = request.form['option5']
            correct_answers = request.form.getlist('correct_answers')

            correct_answer_str = ','.join(correct_answers)

            conn.execute('''
                UPDATE quiz SET question = ?, answer = ?, option1 = ?, option2 = ?, option3 = ?, option4 = ?, option5 = ?
                WHERE id = ? AND quiz_id = ?
            ''', (question_text, correct_answer_str, option1, option2, option3, option4, option5, question_id, quiz_id))

            conn.commit()
            flash('Domanda aggiornata con successo', 'success')
            return redirect(url_for('edit_quiz', quiz_id=quiz_id))

    return render_template('edit_quiz.html', quiz=quiz, questions=questions)

@app.route('/share_quiz/<int:quiz_id>', methods=['GET', 'POST'])
def share_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with get_db_connection() as conn:
        quiz = conn.execute('SELECT * FROM quizzes WHERE id = ? AND creator_id = ?', 
                            (quiz_id, session['user_id'])).fetchone()
        if not quiz:
            flash('Non hai il permesso di condividere questo quiz', 'danger')
            return redirect(url_for('my_quizzes'))

        if request.method == 'POST':
            username = request.form['username']
            user_to_share = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            if user_to_share:
                conn.execute('INSERT INTO shared_quizzes (quiz_id, shared_with_user_id) VALUES (?, ?)',
                             (quiz_id, user_to_share['id']))
                conn.commit()
                flash(f'Quiz condiviso con successo con {username}', 'success')
            else:
                flash('Utente non trovato', 'danger')

    share_link = url_for('take_quiz', quiz_id=quiz_id, _external=True)
    return render_template('share_quiz.html', share_link=share_link, quiz_id=quiz_id)

@app.route('/take_quiz/<int:quiz_id>')
def take_quiz(quiz_id):
    with get_db_connection() as conn:
        # Recupera il quiz dal database
        quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
        if not quiz:
            return "Quiz non trovato", 404

        quiz_questions = conn.execute('SELECT * FROM quiz WHERE quiz_id = ? ORDER BY id', (quiz_id,)).fetchall()
        if not quiz_questions:
            return "Questo quiz non ha domande", 404

    # Inizializza la sessione se non esiste già
    if 'questions' not in session or session.get('selected_quiz_id') != quiz_id:
        session['selected_quiz_id'] = quiz_id
        session['current_question'] = 0
        session['correct_answers'] = 0
        session['questions'] = [dict(q) for q in quiz_questions]  # Carica le domande nella sessione

        # Mescola le opzioni per ogni domanda, se non già mescolate
        for question in session['questions']:
            if 'shuffled_options' not in question:
                options = [question['option1'], question['option2'], question.get('option3'), question.get('option4'), question.get('option5')]
                options = [opt for opt in options if opt]  # Filtra le opzioni vuote
                random.shuffle(options)  # Mescola le opzioni
                question['shuffled_options'] = options  # Salva le opzioni mescolate

    current_question_index = session['current_question']

    # Recupera la domanda corrente
    if current_question_index >= len(session['questions']):
        return redirect(url_for('quiz_completed'))

    question = session['questions'][current_question_index]

    # Visualizza il quiz con le domande e opzioni mescolate
    return render_template('quiz.html',
                           quiz_name=quiz['name'],
                           question=question,
                           question_number=current_question_index + 1,
                           total_questions=len(session['questions']),
                           options=question['shuffled_options'])

@app.route('/delete_quiz/<int:quiz_id>', methods=['POST', 'GET'])
def delete_quiz(quiz_id):
    if 'user_id' not in session:
        flash('Devi essere loggato per eliminare un quiz.', 'danger')
        return redirect(url_for('login'))

    with get_db_connection() as conn:
        # Verifica che il quiz appartenga all'utente
        quiz = conn.execute('SELECT * FROM quizzes WHERE id = ? AND creator_id = ?', (quiz_id, session['user_id'])).fetchone()
        if quiz:
            # Elimina tutte le domande associate al quiz
            conn.execute('DELETE FROM quiz WHERE quiz_id = ?', (quiz_id,))
            # Elimina il quiz stesso
            conn.execute('DELETE FROM quizzes WHERE id = ?', (quiz_id,))
            conn.commit()
            flash('Quiz eliminato con successo!', 'success')
        else:
            flash('Non hai il permesso di eliminare questo quiz.', 'danger')

    return redirect(url_for('my_quizzes'))







if __name__ == '__main__':
    # Crea il database se non esiste
    create_db()
    
    # Verifica se la variabile di ambiente "PORT" è impostata (di solito presente su Railway)
    port = int(os.environ.get("PORT", 5000))  # Usa la porta da variabile di ambiente su Railway, o 5000 in locale
    
    # Esegui l'applicazione
    if os.environ.get("RAILWAY_ENVIRONMENT"):  # Railway imposta la variabile "RAILWAY_ENVIRONMENT"
        app.run(host="0.0.0.0", port=port)
    else:
        app.run(debug=True, port=port)


