from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from google.oauth2 import service_account
from googleapiclient.discovery import build
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

# Enable file-based caching
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year in seconds

# Add CORS headers for better performance with Vercel's CDN
@app.after_request
def add_header(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'public, max-age=300'  # Cache for 5 minutes by default
    return response

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
            try:
                creds_dict = json.loads(google_creds)
                print("Successfully parsed credentials JSON")
                creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
                print("Successfully created credentials object")
            except json.JSONDecodeError as e:
                print(f"Error parsing credentials JSON: {e}")
                return None
            except Exception as e:
                print(f"Error creating credentials object: {e}")
                return None
        else:
            print("ERROR: No credentials found!")
            return None

        print("Building sheets service...")
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        # Get all data from the specified tab
        range_name = f'{tab_name}!A1:F'
        print(f"Fetching range: {range_name}")
        
        try:
            result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                      range=range_name).execute()
            print("Successfully fetched data from sheet")
            values = result.get('values', [])
            return values
        except Exception as e:
            print(f"Error fetching sheet data: {e}")
            return None
            
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

@app.route('/login')
def login():
    return redirect(url_for('index'))

@app.route('/login/callback')
def callback():
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('admin.html')

@app.route('/get_tabs/<spreadsheet_id>')
def get_tabs(spreadsheet_id):
    try:
        print("\n=== DEBUG: GET_TABS ===")
        print(f"Spreadsheet ID: {spreadsheet_id}")
        
        try:
            creds = None
            google_creds = os.environ.get('GOOGLE_CREDENTIALS')
            if google_creds:
                print("Found GOOGLE_CREDENTIALS in environment, loading...")
                creds_dict = json.loads(google_creds)
                creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            else:
                print("ERROR: No credentials found!")
                raise ValueError("No credentials found")

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
        try:
            creds = None
            google_creds = os.environ.get('GOOGLE_CREDENTIALS')
            if google_creds:
                print("Found GOOGLE_CREDENTIALS in environment, loading...")
                creds_dict = json.loads(google_creds)
                creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            else:
                print("ERROR: No credentials found!")
                raise ValueError("No credentials found")

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

@app.route('/test-sheets')
def test_sheets():
    spreadsheet_id = "1O_3JeLPpPWMvakQEP8JVP0UB5FkwTW2k-IPirx2nkcM"  # Your spreadsheet ID
    tab_name = "Sheet1"  # Your tab name
    
    # Test credentials
    google_creds = os.environ.get('GOOGLE_CREDENTIALS')
    if not google_creds:
        return jsonify({"error": "No credentials found in environment"})
    
    try:
        creds_dict = json.loads(google_creds)
        return jsonify({
            "status": "Credentials parsed successfully",
            "project_id": creds_dict.get("project_id"),
            "client_email": creds_dict.get("client_email")
        })
    except Exception as e:
        return jsonify({"error": f"Error parsing credentials: {str(e)}"})

@app.route('/test-sheet-read')
def test_sheet_read():
    spreadsheet_id = "1O_3JeLPpPWMvakQEP8JVP0UB5FkwTW2k-IPirx2nkcM"
    tab_name = "Sheet1"
    
    print("\n=== TESTING SHEET READ ===")
    
    # 1. Test Google Sheets API
    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account
        print("✓ Successfully imported Google Sheets libraries")
    except Exception as e:
        print(f"✗ Error importing libraries: {e}")
        return jsonify({"error": f"Import error: {str(e)}"})
    
    # 2. Test credentials
    try:
        google_creds = os.environ.get('GOOGLE_CREDENTIALS')
        if not google_creds:
            print("✗ No credentials found in environment")
            return jsonify({"error": "No credentials found"})
        
        creds_dict = json.loads(google_creds)
        print(f"✓ Found credentials for project: {creds_dict.get('project_id')}")
        print(f"✓ Service account email: {creds_dict.get('client_email')}")
    except Exception as e:
        print(f"✗ Error parsing credentials: {e}")
        return jsonify({"error": f"Credentials error: {str(e)}"})
    
    # 3. Test service account auth
    try:
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        print("✓ Successfully created credentials object")
    except Exception as e:
        print(f"✗ Error creating service account auth: {e}")
        return jsonify({"error": f"Auth error: {str(e)}"})
    
    # 4. Test building service
    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        print("✓ Successfully built sheets service")
    except Exception as e:
        print(f"✗ Error building service: {e}")
        return jsonify({"error": f"Service error: {str(e)}"})
    
    # 5. Test fetching data
    try:
        range_name = f'{tab_name}!A1:F'
        print(f"Attempting to fetch range: {range_name}")
        result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get('values', [])
        if values:
            print(f"✓ Successfully fetched {len(values)} rows")
            return jsonify({
                "status": "success",
                "row_count": len(values),
                "first_row": values[0] if values else None
            })
        else:
            print("✗ No data found in sheet")
            return jsonify({"error": "No data found in sheet"})
    except Exception as e:
        print(f"✗ Error fetching data: {e}")
        return jsonify({"error": f"Data fetch error: {str(e)}"})

@app.route('/debug-sheet')
def debug_sheet():
    spreadsheet_id = "1O_3JeLPpPWMvakQEP8JVP0UB5FkwTW2k-IPirx2nkcM"
    tab_name = "Sheet1"
    
    try:
        # Get raw data
        values = get_sheet_data(spreadsheet_id, tab_name)
        
        if values:
            # Return detailed info about the data structure
            return jsonify({
                "total_rows": len(values),
                "row_lengths": [len(row) for row in values],
                "first_two_rows": values[:2] if len(values) >= 2 else values,
                "sample_row": {
                    "raw": values[2] if len(values) > 2 else None,
                    "column_count": len(values[2]) if len(values) > 2 else 0
                } if len(values) > 2 else None
            })
        else:
            return jsonify({"error": "No data found in sheet"})
            
    except Exception as e:
        return jsonify({"error": f"Error: {str(e)}"})

def shuffle_multiple_times(items, times=5):
    """Shuffle a list multiple times"""
    for _ in range(times):
        random.shuffle(items)
    return items

if __name__ == '__main__':
    port = 5003
    app.run(host='0.0.0.0', port=port, debug=True)
