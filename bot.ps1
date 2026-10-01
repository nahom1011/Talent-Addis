# AWS Telegram Bot Management CLI
param (
    [Parameter(Position=0)]
    [ValidateSet("status", "logs", "start", "stop", "restart", "ssh", "deploy", "help")]
    [string]$Action = "status"
)

$KeyPath = "C:\Users\NAHOM\Downloads\bot-key.pem"
$Server = "ubuntu@51.20.128.190"

switch ($Action) {
    "status" {
        Write-Host "Checking bot status on AWS..." -ForegroundColor Cyan
        ssh -i $KeyPath $Server "sudo systemctl status talentbot --no-pager"
    }
    "logs" {
        Write-Host "Streaming live logs from AWS (Press Ctrl + C to stop)..." -ForegroundColor Cyan
        ssh -i $KeyPath $Server "sudo journalctl -u talentbot -f"
    }
    "start" {
        Write-Host "Starting bot service on AWS..." -ForegroundColor Green
        ssh -i $KeyPath $Server "sudo systemctl start talentbot && sudo systemctl status talentbot --no-pager"
    }
    "stop" {
        Write-Host "Stopping bot service on AWS..." -ForegroundColor Yellow
        ssh -i $KeyPath $Server "sudo systemctl stop talentbot && echo 'Bot service stopped.'"
    }
    "restart" {
        Write-Host "Restarting bot service on AWS..." -ForegroundColor Cyan
        ssh -i $KeyPath $Server "sudo systemctl restart talentbot && sleep 2 && sudo systemctl status talentbot --no-pager"
    }
    "ssh" {
        Write-Host "Connecting to AWS EC2 terminal..." -ForegroundColor Cyan
        ssh -i $KeyPath $Server
    }
    "deploy" {
        Write-Host "Uploading latest local code to AWS..." -ForegroundColor Cyan
        scp -i $KeyPath database/models.py ubuntu@51.20.128.190:/home/ubuntu/Talent-Addis/database/models.py
        scp -i $KeyPath handlers/*.py ubuntu@51.20.128.190:/home/ubuntu/Talent-Addis/handlers/
        scp -i $KeyPath keyboards/*.py ubuntu@51.20.128.190:/home/ubuntu/Talent-Addis/keyboards/
        scp -i $KeyPath *.py ubuntu@51.20.128.190:/home/ubuntu/Talent-Addis/
        Write-Host "Restarting bot on AWS..." -ForegroundColor Cyan
        ssh -i $KeyPath $Server "sudo systemctl restart talentbot && sleep 2 && sudo systemctl status talentbot --no-pager"
        Write-Host "Deploy completed successfully!" -ForegroundColor Green
    }
    "help" {
        Write-Host "Available commands:" -ForegroundColor Yellow
        Write-Host "  .\bot.ps1 status   - Check if bot is running"
        Write-Host "  .\bot.ps1 logs     - View real-time live activity logs"
        Write-Host "  .\bot.ps1 stop     - Stop the bot"
        Write-Host "  .\bot.ps1 start    - Start the bot"
        Write-Host "  .\bot.ps1 restart  - Restart the bot"
        Write-Host "  .\bot.ps1 ssh      - Open full terminal on AWS"
        Write-Host "  .\bot.ps1 deploy   - Sync your code changes to AWS & restart"
    }
}
