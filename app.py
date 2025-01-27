from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
from google.oauth2 import service_account
from googleapiclient.discovery import build
import random
import os
from dotenv import load_dotenv
import json
import tempfile
import pathlib
import time
from datetime import timedelta

app = Flask(__name__)

# Session configuration
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = tempfile.gettempdir()
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=5)
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
        range_name = f'{tab_name}!A:F'  # Get all rows
        print(f"Fetching range: {range_name}")
        
        try:
            result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                      range=range_name).execute()
            values = result.get('values', [])
            print(f"Successfully fetched {len(values)} rows from sheet")
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
        session.clear()
        
        # Get questions
        print("Getting questions from spreadsheet...")
        try:
            raw_data = get_sheet_data(spreadsheet_id, tab_name)
            if not raw_data:
                return render_template('quiz.html', error="Could not load questions from spreadsheet.")
                
            print(f"Successfully loaded {len(raw_data)} rows")
            
            # Skip header rows and format questions
            if len(raw_data) > 2:
                questions = []
                skipped = 0
                for row in raw_data[2:]:  # Skip first two rows
                    try:
                        # Must have at least question and one answer
                        if len(row) >= 3 and row[1].strip() and row[2].strip():
                            # Get question and correct answer
                            question_text = row[1].strip()
                            correct_answer = row[2].strip()  # C is always correct answer
                            
                            # Get available wrong answers (D, E, F)
                            wrong_answers = []
                            for i in range(3, min(len(row), 6)):  # Check columns D, E, F
                                if row[i].strip():
                                    wrong_answers.append(row[i].strip())
                            
                            if wrong_answers:  # Must have at least one wrong answer
                                # Combine correct and wrong answers
                                all_answers = [correct_answer] + wrong_answers
                                
                                # Shuffle answers
                                random.seed(time.time())
                                shuffled_answers = shuffle_multiple_times(all_answers)
                                
                                question = {
                                    'question': question_text,
                                    'answers': shuffled_answers,
                                    'correct_answer': correct_answer
                                }
                                questions.append(question)
                            else:
                                skipped += 1
                                print(f"Skipping row {len(questions) + skipped}: No wrong answers")
                        else:
                            skipped += 1
                            print(f"Skipping row {len(questions) + skipped}: Missing question or correct answer")
                    except Exception as row_error:
                        skipped += 1
                        print(f"Error processing row: {row_error}")
                        continue
                        
                print(f"Processed {len(questions)} valid questions (skipped {skipped})")
            
                if not questions:
                    return render_template('quiz.html', error="No valid questions found in the spreadsheet.")
                
                # Shuffle questions
                random.seed(time.time())
                questions = shuffle_multiple_times(questions)
                print("Shuffled questions")
                
            else:
                print("Not enough rows in sheet")
                return render_template('quiz.html', error="Not enough questions in the spreadsheet.")
            
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
        
        # Store in session
        try:
            print("Storing questions in session...")
            # Shuffle questions one final time before storing
            random.seed(time.time())
            questions = shuffle_multiple_times(questions)
            session['questions'] = questions
            session['current_question'] = 0
            session['score'] = 0
            session['total_questions'] = len(questions)
            session['wrong_answers'] = []
            print(f"Stored {len(questions)} questions in session")
            
            # Get first question ready
            current_q = questions[0]
            first_question = {
                'question': current_q['question'],
                'answers': current_q['answers'],
                'current': 1,
                'total': len(questions)
            }
            
            return render_template('quiz.html', question=first_question)
            
        except Exception as se:
            print(f"Session error: {str(se)}")
            return render_template('quiz.html', error="Failed to initialize quiz session.")
        
    except Exception as e:
        print(f"ERROR in quiz route: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return render_template('quiz.html', error=str(e))

@app.route('/get_question', methods=['POST'])
def get_question():
    try:
        questions = session.get('questions', [])
        current = session.get('current_question', 0)
        wrong_answers = session.get('wrong_answers', [])
        
        print(f"Getting question {current + 1} of {len(questions)}")
        
        if not questions:
            print("No questions found in session")
            return jsonify({'error': 'No questions found'}), 400
            
        if current >= len(questions):
            print("Quiz complete")
            score = session.get('score', 0)
            return jsonify({
                'complete': True,
                'score': score,
                'total': len(questions),
                'wrong_answers': wrong_answers
            })
            
        current_q = questions[current]
        response_data = {
            'complete': False,
            'question': current_q['question'],
            'answers': current_q['answers'],
            'current': current + 1,
            'total': len(questions),
            'wrong_answers': wrong_answers
        }
        print(f"Returning question data: {response_data}")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in get_question: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/check_answer', methods=['POST'])
def check_answer():
    try:
        data = request.get_json()
        if not data:
            print("No data received in check_answer")
            return jsonify({'error': 'No answer provided'}), 400
            
        answer = data.get('answer', '').strip()
        if not answer:
            print("Empty answer received")
            return jsonify({'error': 'Empty answer'}), 400
        
        questions = session.get('questions', [])
        current = session.get('current_question', 0)
        wrong_answers = session.get('wrong_answers', [])
        
        print(f"Checking answer for question {current + 1} of {len(questions)}")
        print(f"Received answer: {answer}")
        
        if not questions or current >= len(questions):
            print("No valid question to check")
            return jsonify({'error': 'No question to check'}), 400
            
        current_q = questions[current]
        is_correct = answer.strip() == current_q['correct_answer'].strip()
        print(f"Answer is {'correct' if is_correct else 'incorrect'}")
        
        if is_correct:
            session['score'] = session.get('score', 0) + 1
            print(f"New score: {session['score']}")
        else:
            # Store wrong answer
            wrong_answers.append({
                'question': current_q['question'],
                'yourAnswer': answer,
                'correctAnswer': current_q['correct_answer']
            })
            session['wrong_answers'] = wrong_answers
            print("Added to wrong answers list")
            
        # Move to next question
        session['current_question'] = current + 1
        print(f"Moving to question {session['current_question'] + 1}")
        
        # Make sure session is saved
        session.modified = True
        
        return jsonify({
            'correct': is_correct,
            'correct_answer': current_q['correct_answer'],
            'wrong_answers': wrong_answers
        })
        
    except Exception as e:
        print(f"Error in check_answer: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 400

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
    """Shuffle a list multiple times with random seed"""
    if not items:
        return items
    items = items.copy()  # Create a copy to avoid modifying original
    # Set random seed based on current time for different shuffling each time
    random.seed(time.time())
    for _ in range(times):
        random.shuffle(items)
    return items

if __name__ == '__main__':
    port = 5004
    app.run(host='0.0.0.0', port=port, debug=True)
