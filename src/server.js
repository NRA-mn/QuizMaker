const express = require('express');
const { google } = require('googleapis');
const path = require('path');
const fs = require('fs');
const cors = require('cors');
require('dotenv').config();

const app = express();
const port = process.env.PORT || 3000;

// Enable CORS for all routes
app.use(cors());
app.use(express.json());

// Load credentials
const credentials = require('/Users/raizelattal/Downloads/quizfor103-e65e3d2139ae.json');

// Create a new JWT client using the credentials
const client = new google.auth.JWT(
    credentials.client_email,
    null,
    credentials.private_key,
    ['https://www.googleapis.com/auth/spreadsheets.readonly']
);

// Create the sheets API client
const sheets = google.sheets({ version: 'v4', auth: client });

// Path to active quizzes file
const activeQuizzesPath = path.join(__dirname, 'data', 'active-quizzes.json');

// Create data directory if it doesn't exist
if (!fs.existsSync(path.join(__dirname, 'data'))) {
    fs.mkdirSync(path.join(__dirname, 'data'));
}

// Initialize active quizzes file if it doesn't exist
if (!fs.existsSync(activeQuizzesPath)) {
    fs.writeFileSync(activeQuizzesPath, JSON.stringify([]));
}

// Load active quizzes from file
function getActiveQuizzes() {
    try {
        return JSON.parse(fs.readFileSync(activeQuizzesPath, 'utf8'));
    } catch (error) {
        console.error('Error reading active quizzes:', error);
        return [];
    }
}

// Save active quizzes to file
function saveActiveQuizzes(quizzes) {
    fs.writeFileSync(activeQuizzesPath, JSON.stringify(quizzes));
}

// Serve static files from the public directory
app.use(express.static('public'));

// Admin route
app.get('/admin', (req, res) => {
    res.sendFile(path.join(__dirname, '../public/admin.html'));
});

// Quiz route - serve the quiz page for specific quiz
app.get('/quiz/:quizName', (req, res) => {
    const quizName = req.params.quizName;
    const activeQuizzes = getActiveQuizzes();
    
    if (!activeQuizzes.includes(quizName)) {
        res.status(404).send('Quiz not found or no longer active');
        return;
    }
    
    res.sendFile(path.join(__dirname, '../public/quiz.html'));
});

// Endpoint to get quiz questions
app.get('/api/questions/:sheetName', async (req, res) => {
    try {
        const { sheetName } = req.params;
        const spreadsheetId = req.query.spreadsheetId;
        
        if (!spreadsheetId) {
            return res.status(400).json({ error: 'Spreadsheet ID is required' });
        }

        console.log('Fetching questions for sheet:', sheetName, 'from spreadsheet:', spreadsheetId);

        const activeQuizzes = getActiveQuizzes();
        if (!activeQuizzes.includes(sheetName)) {
            return res.status(400).json({ error: 'Quiz is not active' });
        }

        const response = await sheets.spreadsheets.values.get({
            spreadsheetId: spreadsheetId,
            range: `${sheetName}!A:F`,
        });

        const rows = response.data.values || [];
        if (rows.length <= 1) {
            return res.status(400).json({ error: 'No questions found' });
        }

        // Skip header row and process questions
        const questions = rows.slice(1).map(row => {
            // Skip if question, correct answer, or at least one wrong answer is missing
            if (!row[1] || !row[2] || !row[3]) {
                return null;
            }

            // Collect all wrong answers (D, E, F) that exist
            const wrongAnswers = [row[3]];
            if (row[4]) wrongAnswers.push(row[4]);
            if (row[5]) wrongAnswers.push(row[5]);

            return {
                question: row[1], // Question from column B
                correctAnswer: row[2], // Correct answer from column C
                wrongAnswers: wrongAnswers // Wrong answers from D, E, F
            };
        }).filter(q => q !== null);

        if (questions.length === 0) {
            return res.status(404).json({ error: 'No valid questions found' });
        }

        // Shuffle questions multiple times
        for (let i = 0; i < 5; i++) {
            shuffleArray(questions);
        }

        // For each question, create an answers array with correct and wrong answers
        questions.forEach(q => {
            q.answers = [q.correctAnswer, ...q.wrongAnswers];
            // Shuffle answers multiple times
            for (let i = 0; i < 5; i++) {
                shuffleArray(q.answers);
            }
        });

        res.json(questions);
    } catch (error) {
        console.error('Error fetching questions:', error);
        res.status(500).json({ 
            error: 'Failed to fetch questions',
            message: error.message,
            details: error.response ? error.response.data : undefined
        });
    }
});

// Endpoint to get available sheets
app.get('/api/sheets', async (req, res) => {
    try {
        const spreadsheetId = req.query.spreadsheetId;
        if (!spreadsheetId) {
            return res.status(400).json({ error: 'Spreadsheet ID is required' });
        }

        console.log('\n--- Fetching sheets ---');
        console.log('Spreadsheet ID:', spreadsheetId);

        // First, authorize the client
        await client.authorize();
        console.log('Client authorized');

        // Then make the API request
        const request = {
            spreadsheetId: spreadsheetId,
            ranges: [], // Empty ranges means get all sheets
            includeGridData: false,
        };

        const response = await sheets.spreadsheets.get(request);
        console.log('Got response:', JSON.stringify(response.data, null, 2));

        if (!response.data.sheets) {
            throw new Error('No sheets found in spreadsheet');
        }

        const sheetNames = response.data.sheets.map(sheet => sheet.properties.title);
        console.log('Sheet names:', sheetNames);

        res.json({ 
            sheets: sheetNames,
            activeQuizzes: getActiveQuizzes()
        });
    } catch (error) {
        console.error('\n=== Error fetching sheets ===');
        console.error('Error:', error);
        
        let errorMessage = 'Failed to fetch sheets. ';
        if (error.response && error.response.status === 403) {
            errorMessage = `Access denied. Please share the spreadsheet with: ${credentials.client_email}`;
        } else if (error.code === 'ENOTFOUND') {
            errorMessage = 'Could not connect to Google Sheets API. Please check your internet connection.';
        } else {
            errorMessage += error.message || 'Unknown error';
        }

        res.status(error.response?.status || 500).json({ 
            error: errorMessage,
            details: error.response ? error.response.data : undefined
        });
    }
});

// Endpoint to activate a quiz
app.post('/api/quizzes/activate', (req, res) => {
    const { sheetName, spreadsheetId } = req.body;
    if (!sheetName || !spreadsheetId) {
        return res.status(400).json({ error: 'Sheet name and spreadsheet ID are required' });
    }

    const activeQuizzes = getActiveQuizzes();
    if (!activeQuizzes.includes(sheetName)) {
        activeQuizzes.push(sheetName);
        saveActiveQuizzes(activeQuizzes);
    }

    res.json({ 
        activeQuizzes,
        quizUrl: `/quiz/${sheetName}?spreadsheetId=${spreadsheetId}`
    });
});

// Endpoint to deactivate a quiz
app.post('/api/quizzes/deactivate', (req, res) => {
    const { sheetName } = req.body;
    if (!sheetName) {
        return res.status(400).json({ error: 'Sheet name is required' });
    }

    const activeQuizzes = getActiveQuizzes();
    const updatedQuizzes = activeQuizzes.filter(quiz => quiz !== sheetName);
    saveActiveQuizzes(updatedQuizzes);
    res.json({ activeQuizzes: updatedQuizzes });
});

function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

// Redirect root to admin
app.get('/', (req, res) => {
    res.redirect('/admin');
});

// Test the connection on startup
async function testConnection() {
    try {
        console.log('Testing Google Sheets connection...');
        await client.authorize();
        console.log('Successfully connected to Google Sheets!');
    } catch (error) {
        console.error('Failed to connect to Google Sheets:', error);
        process.exit(1);
    }
}

// Start the server after testing connection
testConnection().then(() => {
    app.listen(port, () => {
        console.log(`Server is running on port ${port}`);
    });
});
