param(
    [int]$Port = 3307,
    [string]$DataDir = "",
    [string]$MysqldPath = ""
)

$ErrorActionPreference = "Stop"
$backendRoot = Split-Path -Parent $PSScriptRoot
$mysqlRoot = "D:\MySQL\MySQL Server 8.0"

if (-not $MysqldPath) {
    $command = Get-Command mysqld -ErrorAction SilentlyContinue
    $MysqldPath = if ($command) {
        $command.Source
    } else {
        Join-Path $mysqlRoot "bin\mysqld.exe"
    }
}
if (-not (Test-Path $MysqldPath)) {
    throw "未找到 mysqld.exe，请通过 -MysqldPath 指定 MySQL 安装路径。"
}

$baseDir = Split-Path -Parent (Split-Path -Parent $MysqldPath)
if (-not $DataDir) {
    $DataDir = Join-Path (Split-Path -Parent $baseDir) "zhixue-data"
}
$DataDir = [System.IO.Path]::GetFullPath($DataDir)
$mysqlClient = Join-Path (Split-Path -Parent $MysqldPath) "mysql.exe"
$runtimeDir = Split-Path -Parent $DataDir
$errorLog = Join-Path $runtimeDir "zhixue-mysql-error.log"
$pidFile = Join-Path $runtimeDir "zhixue-mysql.pid"
$serverLog = Join-Path $runtimeDir "zhixue-mysql-server.log"
$consoleLog = Join-Path $runtimeDir "zhixue-mysql-console.log"
$configFile = Join-Path $runtimeDir "zhixue-my.ini"
$configWorkingDir = $runtimeDir
if ($configFile.Contains(" ")) {
    $configFile = Join-Path $env:TEMP "zhixue-mysql-my.ini"
    $configWorkingDir = $env:TEMP
}

New-Item -ItemType Directory -Path $DataDir -Force | Out-Null

$configText = @"
[client]
port=$Port
default-character-set=utf8mb4

[mysqld]
basedir=$($baseDir.Replace('\', '/'))
datadir=$($DataDir.Replace('\', '/'))
port=$Port
bind-address=127.0.0.1
mysqlx=0
log-error=$($errorLog.Replace('\', '/'))
pid-file=$($pidFile.Replace('\', '/'))
character-set-server=utf8mb4
collation-server=utf8mb4_0900_ai_ci
default-storage-engine=INNODB
"@
[System.IO.File]::WriteAllText(
    $configFile,
    $configText,
    [System.Text.UTF8Encoding]::new($false)
)

if (-not (Test-Path (Join-Path $DataDir "mysql"))) {
    & $MysqldPath `
        "--defaults-file=$configFile" `
        --initialize-insecure
    if ($LASTEXITCODE -ne 0) {
        throw "MySQL 数据目录初始化失败，请查看 $errorLog"
    }
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen `
    -ErrorAction SilentlyContinue
if (-not $listener) {
    $process = Start-Process `
        -FilePath $MysqldPath `
        -ArgumentList "--defaults-file=$(Split-Path -Leaf $configFile) --console" `
        -WorkingDirectory $configWorkingDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $serverLog `
        -RedirectStandardError $consoleLog `
        -PassThru
    Set-Content -LiteralPath $pidFile -Value $process.Id

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen `
            -ErrorAction SilentlyContinue
        if ($listener) {
            $ready = $true
            break
        }
    }
    if (-not $ready) {
        throw "MySQL 未能在端口 $Port 启动，请查看 $errorLog"
    }
}

$bootstrapSql = @"
CREATE DATABASE IF NOT EXISTS smart_learning_path
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS 'zhixue_dev'@'127.0.0.1'
    IDENTIFIED WITH mysql_native_password BY 'zhixue_dev_2026';
ALTER USER 'zhixue_dev'@'127.0.0.1'
    IDENTIFIED WITH mysql_native_password BY 'zhixue_dev_2026';
GRANT ALL PRIVILEGES ON smart_learning_path.* TO 'zhixue_dev'@'127.0.0.1';
FLUSH PRIVILEGES;
"@
$bootstrapSql | & $mysqlClient `
    --protocol=tcp `
    --host=127.0.0.1 `
    "--port=$Port" `
    --user=root
if ($LASTEXITCODE -ne 0) {
    throw "数据库或应用账号初始化失败。"
}

Write-Host "MySQL 已就绪：127.0.0.1:$Port/smart_learning_path"
