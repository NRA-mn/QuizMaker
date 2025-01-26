# Quiz Maker

A Flask-based quiz application that allows users to create and take quizzes using Google Sheets as a backend.

## Features

- Create quizzes using Google Sheets
- Take quizzes with randomized questions and answers
- Real-time feedback on answers
- Progress tracking
- Review wrong answers
- Mobile-friendly design

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up Google Sheets API:
   - Create a project in Google Cloud Console
   - Enable Google Sheets API
   - Create credentials (OAuth 2.0 Client ID)
   - Download credentials as `credentials.json`
   - Place `credentials.json` in the project root

4. Set environment variables:
   ```bash
   FLASK_SECRET_KEY=your_secret_key
   ```

## Running Locally

```bash
python app.py
```

## Deployment

This application is ready to deploy on Render.com:

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Use the following settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Add environment variables:
   - `FLASK_SECRET_KEY`
   - Add the contents of `credentials.json` as `GOOGLE_CREDENTIALS`

## Usage

1. Create a Google Sheet with your quiz questions
2. Share the sheet with the service account email
3. Get the spreadsheet ID and tab name
4. Access the quiz at: `/quiz/<spreadsheet_id>/<tab_name>`

## Google Sheet Format

Your Google Sheet should have the following columns:
- Question
- Correct Answer
- Wrong Answer 1
- Wrong Answer 2
- Wrong Answer 3
