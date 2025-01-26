let questions = [];
let currentQuestionIndex = 0;
let score = 0;

// Initialize quiz when the page loads
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Get quiz ID and spreadsheet ID from URL
        const urlParams = new URLSearchParams(window.location.search);
        const spreadsheetId = urlParams.get('spreadsheetId');
        const pathParts = window.location.pathname.split('/');
        const quizId = pathParts[pathParts.length - 1];
        
        if (!spreadsheetId) {
            throw new Error('Spreadsheet ID is missing');
        }
        
        // Get quiz questions
        const response = await fetch(`/api/questions/${quizId}?spreadsheetId=${spreadsheetId}`);
        if (!response.ok) {
            throw new Error('Quiz not found or no longer active');
        }
        
        questions = await response.json();
        
        // Initialize progress
        document.getElementById('total-questions').textContent = questions.length;
        document.getElementById('score-value').textContent = '0';
        currentQuestionIndex = 0;
        score = 0;
        
        updateProgress();
        displayQuestion();
    } catch (error) {
        console.error('Error loading quiz:', error);
        document.getElementById('quiz-container').innerHTML = `
            <div class="error-message">
                <h2>Error</h2>
                <p>${error.message}</p>
                <button onclick="window.location.reload()" class="retry-button">Retry</button>
            </div>
        `;
    }
});

function displayQuestion() {
    if (currentQuestionIndex >= questions.length) {
        // Quiz is finished
        document.getElementById('quiz-container').innerHTML = `
            <div class="quiz-complete">
                <h2>Quiz Complete!</h2>
                <p>Your final score: ${score}/${questions.length}</p>
                <p>Percentage: ${Math.round((score / questions.length) * 100)}%</p>
            </div>
        `;
        return;
    }

    const question = questions[currentQuestionIndex];
    document.getElementById('question').textContent = question.question;
    document.getElementById('current-question').textContent = currentQuestionIndex + 1;
    
    const answersContainer = document.getElementById('answers');
    const answerFeedback = document.getElementById('answer-feedback');
    const continueButton = document.getElementById('continue-btn');
    
    answersContainer.innerHTML = '';
    answerFeedback.innerHTML = '';
    continueButton.style.display = 'none';
    
    // Create answer buttons
    question.answers.forEach(answer => {
        const button = document.createElement('button');
        button.className = 'answer-button';
        button.textContent = answer;
        button.onclick = () => checkAnswer(answer);
        answersContainer.appendChild(button);
    });
}

function checkAnswer(selectedAnswer) {
    const question = questions[currentQuestionIndex];
    const answerFeedback = document.getElementById('answer-feedback');
    const answerButtons = document.querySelectorAll('.answer-button');
    const continueButton = document.getElementById('continue-btn');
    
    // Disable all answer buttons and show correct/incorrect
    answerButtons.forEach(button => {
        button.disabled = true;
        if (button.textContent === question.correctAnswer) {
            button.classList.add('correct');
        } else if (button.textContent === selectedAnswer && selectedAnswer !== question.correctAnswer) {
            button.classList.add('incorrect');
        }
    });

    // Show feedback
    if (selectedAnswer === question.correctAnswer) {
        score++;
        document.getElementById('score-value').textContent = score;
        answerFeedback.innerHTML = '<div class="correct-feedback">Correct!</div>';
    } else {
        answerFeedback.innerHTML = `
            <div class="incorrect-feedback">
                Incorrect. The correct answer was: ${question.correctAnswer}
            </div>
        `;
    }

    // Show continue button
    continueButton.style.display = 'block';
    continueButton.onclick = () => {
        currentQuestionIndex++;
        updateProgress();
        displayQuestion();
    };
}

function updateProgress() {
    const progressFill = document.getElementById('progress-fill');
    const progress = ((currentQuestionIndex) / questions.length) * 100;
    progressFill.style.width = `${progress}%`;
}
