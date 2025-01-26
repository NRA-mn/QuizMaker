from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
import random
import os
from dotenv import load_dotenv
import json
import tempfile

app = Flask(__name__)

# Session configuration
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(tempfile.gettempdir(), 'flask_session')
app.config['SESSION_PERMANENT'] = False
Session(app)

load_dotenv()

def get_sheet_data(spreadsheet_id, tab_name):
    print(f"\n=== LOADING SHEET DATA ===")
    print(f"Loading sheet data for spreadsheet {spreadsheet_id}, tab {tab_name}")
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = None
    
    try:
        google_creds = os.environ.get('GOOGLE_CREDENTIALS')
        if google_creds:
            print("Found GOOGLE_CREDENTIALS in environment, loading...")
            creds_dict = json.loads(google_creds)
            creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        elif os.path.exists('credentials.json'):
            print("Found credentials.json, loading...")
            creds = service_account.Credentials.from_service_account_file(
                'credentials.json', scopes=SCOPES)
        else:
            print("ERROR: No credentials found!")
            raise ValueError("No credentials found")

        print("Building sheets service...")
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        # Get all data from the specified tab
        range_name = f'{tab_name}!A1:F'
        print(f"Fetching range: {range_name}")
        
        result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                  range=range_name).execute()
        values = result.get('values', [])
        
        print("\n=== RAW SPREADSHEET DATA ===")
        for i, row in enumerate(values):
            print(f"Row {i+1}: {row}")
        print("=== END RAW DATA ===\n")
        
        if not values:
            print("ERROR: No data found in spreadsheet")
            raise ValueError("No data found in spreadsheet")
        
        # Skip header rows
        if len(values) > 2:
            values = values[2:]  # Skip first two rows
            print(f"Skipped 2 header rows, processing {len(values)} content rows")
        
        questions = []
        for i, row in enumerate(values, start=3):
            try:
                print(f"\nProcessing row {i}: {row}")
                
                # Skip empty rows
                if not row:
                    print(f"Skipping empty row {i}")
                    continue
                    
                # Get question text (column B)
                if len(row) <= 1:
                    print(f"Skipping row {i}: No question text column")
                    continue
                    
                question_text = row[1].strip() if len(row) > 1 else ""
                if not question_text:
                    print(f"Skipping row {i}: Empty question text")
                    continue
                
                # Get answers (starting from column C)
                answers = []
                for j in range(2, min(len(row), 6)):  # Only look at columns C through F
                    if j < len(row) and row[j].strip():
                        answers.append(row[j].strip())
                
                print(f"Row {i} - Found {len(answers)} answers: {answers}")
                
                if len(answers) < 2:
                    print(f"Skipping row {i}: Not enough answers (need at least 2, got {len(answers)})")
                    continue
                
                question = {
                    'question': question_text,
                    'correct_answer': answers[0],
                    'answers': answers.copy()  # Make a copy to avoid reference issues
                }
                
                questions.append(question)
                print(f"Added question {len(questions)}: {question}")
                
            except Exception as row_error:
                print(f"Error processing row {i}: {str(row_error)}")
                continue
        
        print(f"\nSuccessfully loaded {len(questions)} questions")
        if not questions:
            raise ValueError("No valid questions found. Each question must have question text and at least 2 answers.")
        
        return questions
        
    except Exception as e:
        print(f"\nERROR loading sheet data: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise ValueError(f"Failed to load questions: {str(e)}")

def shuffle_multiple_times(items, times=5):
    """Shuffle a list multiple times"""
    for _ in range(times):
        random.shuffle(items)
    return items

@app.route('/')
def index():
    return render_template('admin.html')

@app.route('/get_tabs/<spreadsheet_id>')
def get_tabs(spreadsheet_id):
    try:
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = None
        
        google_creds = os.environ.get('GOOGLE_CREDENTIALS')
        if google_creds:
            print("Found GOOGLE_CREDENTIALS in environment, loading...")
            creds_dict = json.loads(google_creds)
            creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        elif os.path.exists('credentials.json'):
            print("Found credentials.json, loading...")
            creds = service_account.Credentials.from_service_account_file(
                'credentials.json', scopes=SCOPES)
        else:
            print("ERROR: No credentials found!")
            raise ValueError("No credentials found")

        print("Building sheets service...")
        service = build('sheets', 'v4', credentials=creds)
        sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = sheet_metadata.get('sheets', '')
        titles = [sheet['properties']['title'] for sheet in sheets]
        
        return jsonify(titles)
    except Exception as e:
        print(f"Error in get_tabs: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/quiz/<spreadsheet_id>/<tab_name>')
def quiz(spreadsheet_id, tab_name):
    try:
        print(f"\n=== QUIZ ROUTE ===")
        print(f"Starting quiz for spreadsheet {spreadsheet_id}, tab {tab_name}")
        
        # Clear any existing session data
        print("Clearing session...")
        session.clear()
        print(f"Session after clear: {dict(session)}")
        
        # Get questions
        print("Getting questions from spreadsheet...")
        try:
            questions = get_sheet_data(spreadsheet_id, tab_name)
            print(f"Successfully loaded {len(questions)} questions")
            
            # Shuffle questions multiple times
            questions = shuffle_multiple_times(questions)
            print("Shuffled questions")
            
            # Shuffle answers for each question multiple times
            for q in questions:
                q['answers'] = shuffle_multiple_times(q['answers'])
            print("Shuffled answers")
            
        except Exception as e:
            print(f"Error getting sheet data: {str(e)}")
            import traceback
            debug_info = f"""
Spreadsheet ID: {spreadsheet_id}
Tab Name: {tab_name}
Error Type: {type(e).__name__}
Error Message: {str(e)}
Traceback:
{traceback.format_exc()}
"""
            return render_template('quiz.html', error=f"Error loading questions: {str(e)}", debug_info=debug_info)
        
        if not questions:
            return render_template('quiz.html', error="No questions found in the spreadsheet.")
        
        # Store in session
        try:
            print("Storing questions in session...")
            session['questions'] = questions
            session['current_question'] = 0
            session['score'] = 0
            session['total_questions'] = len(questions)
            session['wrong_answers'] = []  # Initialize wrong answers list
            print(f"Session after storing: {dict(session)}")
            
            # Get first question ready
            current_q = questions[0]
            first_question = {
                'question': current_q['question'],
                'answers': current_q['answers'],
                'current': 1,
                'total': len(questions)
            }
            print(f"First question: {first_question}")
            
            return render_template('quiz.html', question=first_question)
            
        except Exception as se:
            print(f"Session error: {str(se)}")
            return render_template('quiz.html', error="Failed to initialize quiz session.")
        
    except Exception as e:
        print(f"ERROR in quiz route: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return render_template('quiz.html', error=str(e))

@app.route('/get_question')
def get_question():
    try:
        questions = session.get('questions', [])
        current = session.get('current_question', 0)
        wrong_answers = session.get('wrong_answers', [])
        
        if not questions or current >= len(questions):
            score = session.get('score', 0)
            total = session.get('total_questions', 1)
            percentage = int((score / total) * 100)
            return jsonify({
                'complete': True, 
                'score': percentage,
                'wrong_answers': wrong_answers
            })
            
        current_q = questions[current]
        return jsonify({
            'complete': False,
            'question': current_q['question'],
            'answers': current_q['answers'],
            'current': current + 1,
            'total': len(questions),
            'wrong_answers': wrong_answers
        })
        
    except Exception as e:
        print(f"Error in get_question: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/check_answer', methods=['POST'])
def check_answer():
    try:
        data = request.get_json()
        answer = data.get('answer')
        
        questions = session.get('questions', [])
        current = session.get('current_question', 0)
        wrong_answers = session.get('wrong_answers', [])
        
        if not questions or current >= len(questions):
            return jsonify({'error': 'No question to check'}), 400
            
        current_q = questions[current]
        is_correct = answer == current_q['correct_answer']
        
        if is_correct:
            session['score'] = session.get('score', 0) + 1
        else:
            # Store wrong answer
            wrong_answers.append({
                'question': current_q['question'],
                'yourAnswer': answer,
                'correctAnswer': current_q['correct_answer']
            })
            session['wrong_answers'] = wrong_answers
            
        session['current_question'] = current + 1
        
        return jsonify({
            'correct': is_correct,
            'correct_answer': current_q['correct_answer'],
            'wrong_answers': wrong_answers
        })
        
    except Exception as e:
        print(f"Error in check_answer: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/test_sheet/<spreadsheet_id>/<tab_name>')
def test_sheet(spreadsheet_id, tab_name):
    try:
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        print("\n=== TESTING SHEET ACCESS ===")
        
        if not os.path.exists('credentials.json'):
            return jsonify({"error": "credentials.json not found"})
            
        print("Loading credentials...")
        creds = service_account.Credentials.from_service_account_file(
            'credentials.json', scopes=SCOPES)
            
        print("Building service...")
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        print(f"Attempting to read {tab_name}!A1:F")
        result = sheet.values().get(
            spreadsheetId=spreadsheet_id,
            range=f'{tab_name}!A1:F'
        ).execute()
        
        values = result.get('values', [])
        return jsonify({
            "success": True,
            "rows_found": len(values),
            "first_few_rows": values[:3] if values else []
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port)
