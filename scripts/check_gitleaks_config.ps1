$ErrorActionPreference = "Stop"

function gitleaks_hook_present {
    $config = Get-Content -Raw ".pre-commit-config.yaml"
    if ($config -notmatch "gitleaks") {
        throw "gitleaks hook missing from .pre-commit-config.yaml"
    }
}

gitleaks_hook_present
Write-Output "gitleaks hook present"
