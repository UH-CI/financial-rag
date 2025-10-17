pipeline {
    agent any

    environment {
        // Jenkins credentials IDs
        SSH_CRED_ID = 'finance-js2-instance'
        VM_HOST_CRED_ID = 'finance-js2-ip'
        SLACK_CRED_ID = 'finance-slack-webhook'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
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
                withCredentials([
                    sshUserPrivateKey(credentialsId: env.SSH_CRED_ID, keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER'),
                    string(credentialsId: env.VM_HOST_CRED_ID, variable: 'VM_HOST')
                ]) {
                    sh """
                    ssh -o StrictHostKeyChecking=no -i $SSH_KEY $SSH_USER@$VM_HOST '
                        set -e
                        cd /home/exouser/RAG-system
                        git pull origin main
                        cd /home/exouser/RAG-system/frontend
                        sudo npm install
                        sudo npm run build
                        sudo nginx -t
                        sudo systemctl reload nginx
                    '
                    """
                }
            }
        }

        stage('Deploy Backend') {
            steps {
                withCredentials([
                    sshUserPrivateKey(credentialsId: env.SSH_CRED_ID, keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER'),
                    string(credentialsId: env.VM_HOST_CRED_ID, variable: 'VM_HOST')
                ]) {
                    sh """
                    ssh -o StrictHostKeyChecking=no -i $SSH_KEY $SSH_USER@$VM_HOST '
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
