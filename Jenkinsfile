pipeline {
    agent any

    environment {
        // Jenkins credentials IDsa
        SSH_CRED_ID = 'finance-js2-instance'
        VM_HOST_CRED_ID = 'finance-js2-ip'
        SLACK_CRED_ID = 'finance-slack-webhook'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                withCredentials([string(credentialsId: env.SLACK_CRED_ID, variable: 'SLACK_URL')]) {
                sh """
                curl -X POST -H 'Content-type: application/json' \
                --data '{"text":"Starting Deployment ${env.JOB_NAME} #${env.BUILD_NUMBER} (<${env.BUILD_URL}|View Build>)"}' \
                $SLACK_URL
                """
                }
            }

        }

        stage('Check Changes') {
            steps {
                script {
                    if (currentBuild.changeSets.size() > 0) {
                        echo "✅ New commits detected in this build:"
                        currentBuild.changeSets.each { changeSet ->
                            changeSet.items.each { item ->
                                echo "  Commit ID: ${item.commitId}"
                                echo "  Author: ${item.author}"
                                echo "  Message: ${item.msg}"
                            }
                        }
                    } else {
                        echo "⚠️ No new commits since the last successful build. Skipping pipeline."
                        currentBuild.result = 'NOT_BUILT'
                        currentBuild.description = "Skipped - no new commits."
                        error("No new commits found - build not needed")
                    }
                }
            }
        }

        stage('Deploy Frontend') {
            steps {
                script {
                    try {
                        echo "🔄 Starting Frontend Deployment..."
                        echo "Loading credentials..."
                    } catch (Exception e) {
                        echo "❌ Frontend deployment failed: ${e.getMessage()}"
                        throw e
                    }
                }
                withCredentials([
                    string(credentialsId: env.VM_HOST_CRED_ID, variable: 'VM_HOST')
                ]) {
                    echo "✅ VM_HOST credential loaded"
                    sshagent(credentials: [env.SSH_CRED_ID]) {
                        echo "✅ SSH agent started with credential: ${env.SSH_CRED_ID}"
                        sh """
                        ssh -o StrictHostKeyChecking=no exouser@${VM_HOST} '
                            set -e
                            cd /home/exouser/RAG-system
                            git stash --include-untracked
                            git pull origin main
                            git stash drop || true
                            cd /home/exouser/RAG-system/frontend
                            sudo npm install
                            sudo npm run build
                            sudo nginx -t
                            sudo systemctl reload nginx
                        '
                        """
                    }
                }
                script {
                    echo "✅ Frontend deployment completed successfully"
                }
            }
        }

        stage('Deploy Backend') {
            steps {
                withCredentials([
                    string(credentialsId: env.VM_HOST_CRED_ID, variable: 'VM_HOST')
                ]) {
                    sshagent(credentials: [env.SSH_CRED_ID]) {
                        sh """
                        ssh -o StrictHostKeyChecking=no exouser@${VM_HOST} '
                            set -e
                            cd /home/exouser/RAG-system/src
                            source .env
                            cd ..
                            ./stop_production.sh
                            ./start_production.sh
                        '
                        """
                    }
                }
            }
        }
    }

    post {
        success {
            withCredentials([string(credentialsId: env.SLACK_CRED_ID, variable: 'SLACK_URL')]) {
                sh """
                curl -X POST -H 'Content-type: application/json' \
                --data '{"text":"✅ Deployment SUCCESS: Job ${env.JOB_NAME} #${env.BUILD_NUMBER} (<${env.BUILD_URL}|View Build>)"}' \
                $SLACK_URL
                """
            }
        }

        failure {
            withCredentials([string(credentialsId: env.SLACK_CRED_ID, variable: 'SLACK_URL')]) {
                sh """
                curl -X POST -H 'Content-type: application/json' \
                --data '{"text":"❌ Deployment FAILED: Job ${env.JOB_NAME} #${env.BUILD_NUMBER} (<${env.BUILD_URL}|View Build>)"}' \
                $SLACK_URL
                """
            }
        }

        always {
            echo "Cleaning up workspace..."
            cleanWs()
        }
    }
}
