pipeline {
    agent any

    options {
        // Increase timeout to 45 minutes for Docker builds with complex dependencies
        timeout(time: 45, unit: 'MINUTES')
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

        stage('Backup Data') {
            steps {
                script {
                    echo "🔄 Starting data backup..."
                }
                withCredentials([
                    string(credentialsId: env.VM_HOST_CRED_ID, variable: 'VM_HOST')
                ]) {
                    sshagent(credentials: [env.SSH_CRED_ID]) {
                        sh """
                        ssh -o StrictHostKeyChecking=no exouser@${VM_HOST} '
                            set -e
                            cd /home/exouser/RAG-system
                            
                            # Create backup directory
                            mkdir -p /home/exouser/RAG-system/fiscal_notes_backups
                            
                            # Create timestamped backup of fiscal notes (with user annotations)
                            BACKUP_DATE=\$(date +%Y%m%d_%H%M%S)
                            BACKUP_FILE="/home/exouser/RAG-system/fiscal_notes_backups/fiscal_notes_\${BACKUP_DATE}.tar.gz"
                            
                            if [ -d "src/fiscal_notes/generation" ]; then
                                echo "📦 Creating backup: \${BACKUP_FILE}"
                                tar -czf "\${BACKUP_FILE}" src/fiscal_notes/generation/
                                echo "✅ Backup created successfully"
                                
                                # Keep only last 10 backups to save space
                                cd /home/exouser/RAG-system/fiscal_notes_backups
                                ls -t fiscal_notes_*.tar.gz | tail -n +11 | xargs -r rm
                                echo "📊 Current backups:"
                                ls -lh fiscal_notes_*.tar.gz 2>/dev/null || echo "No backups yet"
                                cd /home/exouser/RAG-system
                            fi
                        '
                        """
                    }
                }
                script {
                    echo "✅ Data backup completed successfully"
                }
            }
        }

        stage('Update Code') {
            steps {
                script {
                    echo "🔄 Updating code from repository..."
                }
                withCredentials([
                    string(credentialsId: env.VM_HOST_CRED_ID, variable: 'VM_HOST')
                ]) {
                    sshagent(credentials: [env.SSH_CRED_ID]) {
                        sh """
                        ssh -o StrictHostKeyChecking=no exouser@${VM_HOST} '
                            set -e
                            cd /home/exouser/RAG-system
                            
                            # Clean up temporary files that might conflict
                            rm -f src/log.txt uvicorn.pid logs/*.log 2>/dev/null || true
                            
                            # Stash any local changes to fiscal notes and property prompts (user data)
                            git add src/fiscal_notes/generation/ src/fiscal_notes/property_prompts_config.json 2>/dev/null || true
                            git stash push -m "Preserve user annotations before pull" src/fiscal_notes/generation/ src/fiscal_notes/property_prompts_config.json 2>/dev/null || true
                            
                            # Reset any other local changes that might conflict
                            git reset --hard HEAD
                            
                            # Update code (gitignored files like fiscal notes are preserved)
                            git pull origin main
                            
                            # Restore local changes (user annotations and property prompts)
                            git stash pop 2>/dev/null || true
                        '
                        """
                    }
                }
                script {
                    echo "✅ Code update completed successfully"
                }
            }
        }

        stage('Deploy with GO.sh') {
            steps {
                script {
                    echo "🔄 Starting production deployment with GO.sh..."
                }
                withCredentials([
                    string(credentialsId: env.VM_HOST_CRED_ID, variable: 'VM_HOST')
                ]) {
                    sshagent(credentials: [env.SSH_CRED_ID]) {
                        sh """
                        ssh -o StrictHostKeyChecking=no exouser@${VM_HOST} '
                            set -e
                            cd /home/exouser/RAG-system
                            
                            # Make sure GO.sh is executable
                            chmod +x GO.sh
                            
                            # Run full production deployment with GO.sh
                            # This includes: backup, stop containers, cleanup, build, start, health checks
                            ./GO.sh prod --deploy --workers \${WORKERS:-8}
                            
                            # Start RefBot background worker (detached)
                            echo "🚀 Starting RefBot background worker..."
                            docker compose -f docker-compose.prod.yml exec -d api bash src/start_worker.sh
                        '
                        """
                    }
                }
                script {
                    echo "✅ Production deployment with GO.sh completed successfully"
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
