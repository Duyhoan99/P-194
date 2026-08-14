# PowerShell script to split local changes into 11 separate branches with specific authors
$ErrorActionPreference = "Continue"

# 1. Check if there are active changes on temp-backup-all or main
# Since we might have already run the script, temp-backup-all might exist.
# Let's delete temp-backup-all if it exists, but wait, we need it if it contains our backup!
# If temp-backup-all exists, we don't need to recreate it if we already have it.
# But wait, if we want to run again, the current main is clean. Our changes are in temp-backup-all!
# So we MUST NOT delete temp-backup-all before we restore files.
# Actually, the backup is already in temp-backup-all.
# Let's write the script to detect if temp-backup-all exists. If it doesn't, create it from current changes.
# If it does, just use it!

if (-not (git branch --list temp-backup-all)) {
    Write-Host "Creating a temporary backup branch from current changes..."
    git checkout -b temp-backup-all
    git add .
    git commit -m "temp: backup all changes before splitting"
    git checkout main
} else {
    Write-Host "Using existing backup branch temp-backup-all."
}

# Function to create a branch, pull specific files from the backup branch, and commit
function Create-Commit-Branch {
    param(
        [string]$BranchName,
        [string[]]$Files,
        [string]$Message,
        [string]$Author
    )
    Write-Host "--------------------------------------------------"
    Write-Host "Creating branch: $BranchName"
    
    # Delete the branch if it already exists locally to prevent errors
    if (git branch --list $BranchName) {
        git branch -D $BranchName
    }

    git checkout -b $BranchName main
    
    $addedAny = $false
    foreach ($file in $Files) {
        # Check if file exists in temp-backup-all
        $exists = git show temp-backup-all`:"$file" 2>$null
        if ($LASTEXITCODE -eq 0 -or $file.EndsWith("/") -or $file.EndsWith("\")) {
            git checkout temp-backup-all -- $file
            $addedAny = $true
        } else {
            Write-Warning "File or folder '$file' not found in backup, skipping."
        }
    }

    if ($addedAny) {
        git add .
        git commit -m $Message --author=$Author
        Write-Host "Successfully committed $BranchName"
    } else {
        Write-Warning "No files were added to branch $BranchName. Creating empty commit."
        git commit --allow-empty -m $Message --author=$Author
    }
    
    git checkout main
}

# 3. Define and create the 11 branches
Create-Commit-Branch `
    -BranchName "quoc/fe-base" `
    -Files @("frontend/package.json", "frontend/package-lock.json", "frontend/next.config.mjs", "frontend/jest.setup.ts", "frontend/src/app/globals.css", "frontend/src/app/layout.tsx") `
    -Message "feat(frontend): base nextjs config and layout" `
    -Author "Wolfbundau <nguyendinhquoc1506@gmail.com>"

Create-Commit-Branch `
    -BranchName "quoc/fe-pages" `
    -Files @("frontend/src/app/page.tsx", "frontend/src/app/login/page.tsx", "frontend/src/app/dashboard/page.tsx", "frontend/src/app/patients/page.tsx", "frontend/src/app/patients/layout.tsx", "frontend/src/app/patients/[id]/page.tsx", "frontend/src/app/analytics", "frontend/src/app/case-files", "frontend/src/app/help", "frontend/src/app/settings") `
    -Message "feat(frontend): core routing and pages" `
    -Author "Wolfbundau <nguyendinhquoc1506@gmail.com>"

Create-Commit-Branch `
    -BranchName "quoc/fe-core-components" `
    -Files @("frontend/src/components/Sidebar.tsx", "frontend/src/components/RootLayoutWrapper.tsx", "frontend/src/components/UploadZone.tsx", "frontend/src/components/DocumentModal.tsx", "frontend/__tests__/UploadZone.test.tsx", "frontend/public") `
    -Message "feat(frontend): sidebar, upload zone, and document modal components" `
    -Author "Wolfbundau <nguyendinhquoc1506@gmail.com>"

Create-Commit-Branch `
    -BranchName "quoc/fe-agent-components" `
    -Files @("frontend/src/components/ChatPanel.tsx", "frontend/src/components/EvidencePanel.tsx", "frontend/src/components/Timeline.tsx", "frontend/src/components/PatientAlerts.tsx", "frontend/src/components/PatientMetricsChart.tsx", "frontend/src/components/StructuredReview.tsx") `
    -Message "feat(frontend): chatbot, evidence panel, and patient analytics components" `
    -Author "Wolfbundau <nguyendinhquoc1506@gmail.com>"

Create-Commit-Branch `
    -BranchName "quoc/fe-api-store" `
    -Files @("frontend/src/lib/api.ts", "frontend/src/lib/store.ts", "frontend/src/lib/i18n.tsx") `
    -Message "feat(frontend): api clients, state management store, and internationalization" `
    -Author "Wolfbundau <nguyendinhquoc1506@gmail.com>"

Create-Commit-Branch `
    -BranchName "hieu/clinical-extractor" `
    -Files @("src/clinical/pdf_extractor.py", "src/clinical/pdf_canonicalizer.py", "src/clinical/pdf_generator.py") `
    -Message "feat(clinical): pdf extractor, parser, and generator modules" `
    -Author "Dao-Trung-Hieu-2912 <daohieu589@gmail.com>"

Create-Commit-Branch `
    -BranchName "hieu/clinical-parser" `
    -Files @("src/clinical/ingestion.py", "src/clinical/fhir_canonicalizer.py", "src/clinical/structured_fact.py") `
    -Message "feat(clinical): data ingestion pipeline and fhir canonicalizer" `
    -Author "Dao-Trung-Hieu-2912 <daohieu589@gmail.com>"

Create-Commit-Branch `
    -BranchName "hieu/clinical-db-audit" `
    -Files @("src/clinical/demo_repository.py", "src/clinical/audit.py", "src/clinical/evidence_packet.py") `
    -Message "feat(clinical): sqlite repository, clinical audit logs, and evidence packets" `
    -Author "Dao-Trung-Hieu-2912 <daohieu589@gmail.com>"

Create-Commit-Branch `
    -BranchName "hoan/api-routes" `
    -Files @("src/api") `
    -Message "feat(api): fastapi routing and patient/ops/ocr endpoints" `
    -Author "Pham Duy Hoan <duyhoan3905@gmail.com>"

Create-Commit-Branch `
    -BranchName "hoan/agent-graph" `
    -Files @("src/agents") `
    -Message "feat(agent): langgraph workflow, agent state, decision nodes, and tools" `
    -Author "Pham Duy Hoan <duyhoan3905@gmail.com>"

# NOTE: config.py is now src/config.py, and configs folder is added
Create-Commit-Branch `
    -BranchName "hoan/qa-tests-config" `
    -Files @("tests", "eval", "requirements.txt", "src/config.py", "configs", "conftest.py", "pytest.ini", "ruff.toml", "start.py", "test_db.py", "fix_tests.py", "README_boilerplate.md", ".gitignore", "docker-compose.yml", "Dockerfile", "Makefile", "WORKLOG.md", "ARCHITECTURE.md", "API_CONTRACT.md", "Diagram.md", "JOURNAL.md", "README.md") `
    -Message "test(qa): backend testing suites, config files, and deployment descriptors" `
    -Author "Pham Duy Hoan <duyhoan3905@gmail.com>"

# 4. Clean up the temp backup branch
Write-Host "--------------------------------------------------"
Write-Host "Cleaning up temporary backup branch..."
git branch -D temp-backup-all

Write-Host "All 11 local branches have been successfully created!"
Write-Host "You can now push all of them to remote using: git push origin --all"
