 = Get-Content 'D:\DiscordAI\bot.py' -Raw

 = 'from config import (
    ROLE_ID,$
    KEYWORDS,$
    PVP_RANK_KEYWORDS,$
)
from game.pvp.ui'
 = 'from config import (
    ROLE_ID,$
    KEYWORDS,$
    PVP_RANK_KEYWORDS,$
)

pending_kicks = {}  # user_id -> target_user_id for kick confirmation

from game.pvp.ui'

if  -match [regex]::Escape()) {
     =  -replace [regex]::Escape(), 
     | Set-Content -Path 'D:\DiscordAI\bot.py' -Encoding utf8
    Write-Host 'Applied pending_kicks'
} else {
    Write-Host 'Pattern not found'
}
