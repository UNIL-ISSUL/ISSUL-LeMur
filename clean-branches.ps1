git branch | ForEach-Object {
    $branch = $_.Trim()
    if ($branch -ne "main" -and $branch -ne "* main") {
        $confirm = Read-Host "Supprimer la branche '$branch' ? (y/N)"
        if ($confirm -eq "y") {
            git branch -d $branch 2>$null
            if ($LASTEXITCODE -ne 0) {
                git branch -D $branch
            }
        }
        else {
            Write-Host "→ Conservée : $branch"
        }
    }
}

git fetch --prune