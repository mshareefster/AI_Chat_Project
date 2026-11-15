
pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timestamps()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build React Frontend') {
            steps {
                dir('frontend') {
                    sh 'npm ci'
                    sh 'npm run build'
                }
            }
        }

        stage('Install Backend Dependencies') {
            steps {
                dir('backend') {
                    sh 'python3 -m venv .venv-ci'
                    sh '.venv-ci/bin/python -m pip install --upgrade pip'
                    sh '.venv-ci/bin/pip install -r requirements.txt'
                    sh '.venv-ci/bin/python -m compileall -q main.py'
                }
            }
        }
    }

    post {
        success {
            echo 'Huda AI CI pipeline completed successfully!'
        }
        failure {
            echo 'Huda AI CI pipeline failed. Check the build logs.'
        }
        always {
            sh 'rm -rf backend/.venv-ci'
        }
    }
}

