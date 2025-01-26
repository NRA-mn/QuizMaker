from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2 import service_account
import random
import os
from dotenv import load_dotenv
import json
import tempfile
import pathlib

app = Flask(__name__)

# Session configuration
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(tempfile.gettempdir(), 'flask_session')
app.config['SESSION_PERMANENT'] = False
Session(app)

load_dotenv()

# OAuth 2.0 configuration
CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

def get_sheet_data(spreadsheet_id, tab_name):
    print(f"\n=== LOADING SHEET DATA ===")
    print(f"Loading sheet data for spreadsheet {spreadsheet_id}, tab {tab_name}")
    
    if 'credentials' not in session:
        return redirect(url_for('login'))
    
    try:
        creds = Credentials(
            token=session['credentials']['token'],
            refresh_token=session['credentials']['refresh_token'],
            token_uri=session['credentials']['token_uri'],
            client_id=session['credentials']['client_id'],
            client_secret=session['credentials']['client_secret'],
            scopes=session['credentials']['scopes']
        )

        print("Building sheets service...")
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        # Get all data from the specified tab
        range_name = f'{tab_name}!A1:F'
        print(f"Fetching range: {range_name}")
        
        result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                  range=range_name).execute()
        values = result.get('values', [])
        
        if not values:
            print("No data found in sheet")
            return None
            
        print(f"Found {len(values)} rows of data")
        return values
        
    except Exception as e:
        print(f"Error accessing sheet: {str(e)}")
        return None

@app.route('/login')
def login():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [request.base_url + "/callback"]
            }
        },
        scopes=SCOPES
    )
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    session['state'] = state
    return redirect(authorization_url)

@app.route('/login/callback')
def callback():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [url_for('callback', _external=True)]
            }
        },
        scopes=SCOPES,
        state=session['state']
    )
    
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('admin.html')

@app.route('/get_tabs/<spreadsheet_id>')
def get_tabs(spreadsheet_id):
    try:
        print("\n=== DEBUG: GET_TABS ===")
        print(f"Spreadsheet ID: {spreadsheet_id}")
        
        if 'credentials' not in session:
            return redirect(url_for('login'))
        
        try:
            creds = Credentials(
                token=session['credentials']['token'],
                refresh_token=session['credentials']['refresh_token'],
                token_uri=session['credentials']['token_uri'],
                client_id=session['credentials']['client_id'],
                client_secret=session['credentials']['client_secret'],
                scopes=session['credentials']['scopes']
            )

            print("Building sheets service...")
            service = build('sheets', 'v4', credentials=creds)
            print("Successfully built service")
            
            print("Getting sheet metadata...")
            sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = sheet_metadata.get('sheets', '')
            titles = [sheet['properties']['title'] for sheet in sheets]
            print(f"Found sheets: {titles}")
            
            return jsonify(titles)
        except Exception as e:
            print(f"Error in get_tabs: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': str(e)}), 400
        
    except Exception as e:
        print(f"Error in get_tabs: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
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
            
            # Skip header rows
            if len(questions) > 2:
                questions = questions[2:]  # Skip first two rows
                print(f"Skipped 2 header rows, processing {len(questions)} content rows")
            
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
                'question': current_q[1].strip(),
                'answers': current_q[2:6],
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
            'question': current_q[1].strip(),
            'answers': current_q[2:6],
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
        is_correct = answer == current_q[2].strip()
        
        if is_correct:
            session['score'] = session.get('score', 0) + 1
        else:
            # Store wrong answer
            wrong_answers.append({
                'question': current_q[1].strip(),
                'yourAnswer': answer,
                'correctAnswer': current_q[2].strip()
            })
            session['wrong_answers'] = wrong_answers
            
        session['current_question'] = current + 1
        
        return jsonify({
            'correct': is_correct,
            'correct_answer': current_q[2].strip(),
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
        if 'credentials' not in session:
            return redirect(url_for('login'))
        
        try:
            creds = Credentials(
                token=session['credentials']['token'],
                refresh_token=session['credentials']['refresh_token'],
                token_uri=session['credentials']['token_uri'],
                client_id=session['credentials']['client_id'],
                client_secret=session['credentials']['client_secret'],
                scopes=session['credentials']['scopes']
            )

            print("Building sheets service...")
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
        
    except Exception as e:
        print(f"Error in test_sheet: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 400

def shuffle_multiple_times(items, times=5):
    """Shuffle a list multiple times"""
    for _ in range(times):
        random.shuffle(items)
    return items

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port)
