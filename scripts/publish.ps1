# Локальная публикация: push + открыть PR (или создать через gh, если установлен).
param(
  [string]$Message = "",
  [switch]$NoCommit
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$branch = (git branch --show-current).Trim()
if ($branch -eq "main") {
  Write-Host "Вы на main. Создайте рабочую ветку, например: git checkout -b fix/my-change" -ForegroundColor Yellow
  exit 1
}

if (-not $NoCommit) {
  $status = git status --porcelain
  if ($status) {
    if (-not $Message) {
      $Message = Read-Host "Сообщение коммита"
    }
    if (-not $Message.Trim()) {
      Write-Host "Коммит отменён: пустое сообщение." -ForegroundColor Yellow
      exit 1
    }
    git add -A
    git commit -m $Message
  }
}

Write-Host "Push $branch ..." -ForegroundColor Cyan
git push -u origin $branch

$repo = "sachachugun/tutuorders"
$compareUrl = "https://github.com/$repo/compare/main...$branch?expand=1"

$gh = Get-Command gh -ErrorAction SilentlyContinue
if ($gh) {
  $existing = gh pr list --base main --head $branch --json number --jq 'length' 2>$null
  if ($existing -eq "0") {
    gh pr create --base main --head $branch --title "Update: $branch" --body "PR из scripts/publish.ps1"
  } else {
    Write-Host "PR уже существует:" -ForegroundColor Green
    gh pr view --web
    exit 0
  }
  gh pr view --web
} else {
  Write-Host ""
  Write-Host "GitHub CLI (gh) не установлен. Открываю страницу PR в браузере..." -ForegroundColor Yellow
  Write-Host $compareUrl
  Start-Process $compareUrl
  Write-Host ""
  Write-Host "После merge: на VPS git pull origin main (или настройте Deploy VPS в GitHub Actions)." -ForegroundColor Cyan
}
