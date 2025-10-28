pipeline {
    agent any

    options {
        // Increase Git timeout to 30 minutes for large repositories
        timeout(time: 30, unit: 'MINUTES')
        // Skip default checkout, we'll do it manually with custom timeout
        skipDefaultCheckout()
    }

    environment {
        // Jenkins credentials IDsa
        SSH_CRED_ID = 'finance-js2-instance'
        VM_HOST_CRED_ID = 'finance-js2-ip'
        SLACK_CRED_ID = 'finance-slack-webhook'
    }

    stages {
        stage('Checkout') {
            steps {
                script {
                    // Checkout with increased timeout (30 minutes)
                    // Note: Repository is large (~375MB) due to historical commits of:
                    // - ChromaDB databases (468MB)
                    // - Vector JSON files (570MB + 323MB)
                    // See CLEANUP_LARGE_FILES.md for cleanup instructionsasd
                    checkout([
                        $class: 'GitSCM',
                        branches: scm.branches,
                        extensions: [
                            [$class: 'CloneOption', timeout: 30, depth: 0, noTags: false, shallow: false],
                            [$class: 'CheckoutOption', timeout: 30]
                        ],
                        userRemoteConfigs: scm.userRemoteConfigs
                    ])
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
                        
                        // Send Slack notification only when changes are detected
                        withCredentials([string(credentialsId: env.SLACK_CRED_ID, variable: 'SLACK_URL')]) {
                            sh """
                            curl -X POST -H 'Content-type: application/json' \
                            --data '{"text":"🚀 Starting Deployment ${env.JOB_NAME} #${env.BUILD_NUMBER} (<${env.BUILD_URL}|View Build>)"}' \
                            \$SLACK_URL
                            """
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
                            
                            # Create backup directory if it doesn'\''t exist
                            mkdir -p /home/exouser/fiscal_notes_backups
                            
                            # Create timestamped backup of fiscal notes (with user annotations)
                            BACKUP_DATE=\$(date +%Y%m%d_%H%M%S)
                            BACKUP_FILE="/home/exouser/fiscal_notes_backups/fiscal_notes_\${BACKUP_DATE}.tar.gz"
                            
                            if [ -d "src/fiscal_notes/generation" ]; then
                                echo "📦 Creating backup: \${BACKUP_FILE}"
                                tar -czf "\${BACKUP_FILE}" src/fiscal_notes/generation/
                                echo "✅ Backup created successfully"
                                
                                # Keep only last 10 backups to save space
                                cd /home/exouser/fiscal_notes_backups
                                ls -t fiscal_notes_*.tar.gz | tail -n +11 | xargs -r rm
                                echo "📊 Current backups:"
                                ls -lh fiscal_notes_*.tar.gz 2>/dev/null || echo "No backups yet"
                                cd /home/exouser/RAG-system
                            fi
                            
                            # Stash any local changes to fiscal notes (user annotations)
                            git add src/fiscal_notes/generation/ 2>/dev/null || true
                            git stash push -m "Preserve user annotations before pull" src/fiscal_notes/generation/ 2>/dev/null || true
                            
                            # Update code (gitignored files like fiscal notes are preserved)
                            git pull origin main
                            
                            # Restore local changes (user annotations)
                            git stash pop 2>/dev/null || true
                            
                            # Build and deploy frontend
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
            script {
                def failedStage = env.STAGE_NAME ?: 'Unknown Stage'
                def buildUrl = env.BUILD_URL
                def consoleUrl = "${buildUrl}console"
                def jobName = env.JOB_NAME
                def buildNumber = env.BUILD_NUMBER
                
                // Capture last 50 lines of console output for debugging
                def consoleLog = sh(
                    script: '''
                        # Get the last 50 lines of the build log
                        tail -50 "${JENKINS_HOME}/jobs/${JOB_NAME}/builds/${BUILD_NUMBER}/log" 2>/dev/null || echo "Could not retrieve console output"
                    ''',
                    returnStdout: true
                ).trim()
                
                // Escape special characters for JSON
                consoleLog = consoleLog
                    .replaceAll('\\\\', '\\\\\\\\')
                    .replaceAll('"', '\\\\"')
                    .replaceAll('\n', '\\\\n')
                    .take(3000) // Limit to 3000 chars to stay under Slack's limit
                
                withCredentials([string(credentialsId: env.SLACK_CRED_ID, variable: 'SLACK_URL')]) {
                    sh """
                    curl -X POST -H 'Content-type: application/json' \
                    --data '{
                        "text":"❌ *Deployment FAILED*",
                        "attachments": [{
                            "color": "danger",
                            "fields": [
                                {
                                    "title": "Job",
                                    "value": "${jobName} #${buildNumber}",
                                    "short": true
                                },
                                {
                                    "title": "Failed Stage",
                                    "value": "${failedStage}",
                                    "short": true
                                },
                                {
                                    "title": "Console Output (Last 50 lines)",
                                    "value": "```${consoleLog}```",
                                    "short": false
                                },
                                {
                                    "title": "Actions",
                                    "value": "<${buildUrl}|View Build> | <${consoleUrl}|Full Console Output>",
                                    "short": false
                                }
                            ],
                            "footer": "Jenkins CI/CD",
                            "ts": '"\$(date +%s)"'
                        }]
                    }' \
                    \$SLACK_URL
                    """
                }
            }
        }

        always {
            echo "Cleaning up workspace..."
            cleanWs()
        }
    }
}
