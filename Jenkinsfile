pipeline {
    agent any

    stages {
        stage('Setup') {
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --upgrade pip
                    pip install -e ".[dev]"
                '''
            }
        }
        stage('Lint') {
            steps {
                sh '''
                    . .venv/bin/activate
                    ruff check .
                '''
            }
        }
        stage('Test') {
            steps {
                sh '''
                    . .venv/bin/activate
                    pytest -v --junitxml=pytest-results.xml
                '''
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'pytest-results.xml'
        }
    }
}
