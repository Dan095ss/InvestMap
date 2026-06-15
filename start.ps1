$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host " ╔══════════════════════════════════╗" -ForegroundColor Cyan
Write-Host " ║    InvestMap — Запускатор        ║" -ForegroundColor Cyan
Write-Host " ╚══════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Проверка Python
try { python --version | Out-Null } catch {
    Write-Error "Python не найден. Установите Python 3.10+ с https://python.org"
    exit 1
}

# Виртуальное окружение
if (-not (Test-Path ".venv")) {
    Write-Host "[1/4] Создаю виртуальное окружение..." -ForegroundColor Yellow
    python -m venv .venv
}
.\.venv\Scripts\Activate.ps1

# Зависимости
Write-Host "[2/4] Устанавливаю зависимости..." -ForegroundColor Yellow
pip install -r requirements.txt -q --disable-pip-version-check

# SECRET_KEY
if (-not (Test-Path ".env")) {
    Write-Host "[3/4] Генерирую SECRET_KEY..." -ForegroundColor Yellow
    python -c "import secrets; open('.env','w').write('SECRET_KEY='+secrets.token_hex(32)+'\n')"
    Write-Host "    .env создан."
} else {
    Write-Host "[3/4] .env найден."
}

Get-Content ".env" | ForEach-Object {
    $parts = $_ -split "=", 2
    if ($parts.Length -eq 2) {
        [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
    }
}

# Наполнение БД
if (-not (Test-Path "instance\investmap.db")) {
    Write-Host "[4/4] Первый запуск — заполняю базу данных..." -ForegroundColor Yellow
    python seed.py
} else {
    Write-Host "[4/4] База данных уже существует."
}

Write-Host ""
Write-Host " Сервер запущен: http://127.0.0.1:5000" -ForegroundColor Green
Write-Host " Для остановки: Ctrl+C"
Write-Host ""
python run.py
