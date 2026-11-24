
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

                script {
                    def commit = sh(
                        script: 'git rev-parse --short HEAD',
                        returnStdout: true
                    ).trim()

                    def branch = sh(
                        script: 'git branch --show-current',
                        returnStdout: true
                    ).trim()

                    if (!branch) {
                        branch = 'main'
                    }

                    currentBuild.displayName = "#${env.BUILD_NUMBER} - ${commit}"
                    currentBuild.description = "Commit: ${commit} | Branch: ${branch}"

                    echo "Building Git commit: ${commit}"
                }
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
                    sh '.venv-ci/bin/pip install -r requirements-dev.txt'
                }
            }
        }

        stage('Validate Backend') {
            steps {
                dir('backend') {
                    sh '.venv-ci/bin/python -m compileall -q main.py'
                }
            }
        }

        stage('Run Backend Tests') {
            steps {
                dir('backend') {
                    sh '.venv-ci/bin/python -m pytest tests/ -v'
                }
            }
        }
    }

    post {
        success {
            echo 'Huda AI CI pipeline completed successfully!'
            echo 'Frontend build and backend tests passed.'
        }

        failure {
            echo 'Huda AI CI pipeline failed. Check the build logs.'
        }

        always {
            sh 'rm -rf backend/.venv-ci'
        }
    }
}

