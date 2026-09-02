# run_period.ps1 — รันงานผลิตสื่อ "หนึ่งคาบ หนึ่งเซสชัน" (EDU ONE)
#
# ทำไมต้องมีสคริปต์นี้
#   จากการวัดของจริง 1 คาบ = $308 โดย **orchestrator กินไป 54%** เพราะบริบทของแม่
#   เฉลี่ย 726,000 โทเคน ถูกอ่านซ้ำทุก turn 316 ครั้ง — และครึ่งหนึ่งของบริบทนั้น
#   ไม่เกี่ยวกับงานผลิตสื่อเลย เป็นงานอื่นที่ค้างอยู่ในเซสชันเดียวกันมาก่อน
#   (แม่เริ่ม pipeline ที่ 585,680 โทเคนตั้งแต่ turn แรก)
#
#   สคริปต์นี้ยิง `claude -p` **แยกโปรเซสต่อคาบ** จึงได้เซสชันใหม่ทุกครั้งโดยไม่ต้อง
#   พึ่งวินัยของคน — คาดว่าลดได้ ~$80-100 ต่อคาบ โดยไม่แตะโมเดลและไม่แตะคุณภาพ
#
# ใช้งาน
#   .\run_period.ps1 m1 math 1              # คาบเดียว
#   .\run_period.ps1 m1 math 1 -To 5        # คาบ 1 ถึง 5 ทีละคาบ
#   .\run_period.ps1 m1 math 1 -Only c1,ex  # เลือกเฉพาะบางผลผลิต (ใช้ตอนแก้งาน)
#   .\run_period.ps1 m1 math 1 -DryRun      # ดูคำสั่งที่จะรัน ไม่รันจริง
#
# ผลลัพธ์
#   log ต่อคาบที่ .eduone-runs/<BASE>.log  (ไม่ track git)
#   สรุปท้ายการรันว่าคาบไหนจบ/ไม่จบ พร้อมเวลาที่ใช้

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$GradeSlug,
    [Parameter(Mandatory = $true)][string]$SubjectSlug,
    [Parameter(Mandatory = $true)][int]$From,
    [int]$To = 0,
    [string]$Only = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
if ($To -lt $From) { $To = $From }

# โฟลเดอร์งาน = ที่ที่เรียกสคริปต์ (ต้องมี Output/ หรือ CLAUDE.md ของโปรเจกต์)
$work = (Get-Location).Path
if (-not (Test-Path (Join-Path $work "CLAUDE.md"))) {
    Write-Warning "ไม่เจอ CLAUDE.md ที่ $work — ให้ cd ไปโฟลเดอร์งานก่อนรัน"
}

$logDir = Join-Path $work ".eduone-runs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$claude = (Get-Command claude -ErrorAction SilentlyContinue)
if (-not $claude -and -not $DryRun) {
    throw "ไม่พบคำสั่ง claude ใน PATH — ติดตั้ง Claude Code ก่อน"
}

$results = @()
foreach ($no in $From..$To) {
    $prompt = "/edu-one $GradeSlug $SubjectSlug $no"
    if ($Only) { $prompt = "$prompt --only $Only" }

    $base = "$GradeSlug-$SubjectSlug-no$no"
    $log = Join-Path $logDir "$base.log"

    Write-Host ""
    Write-Host "=== คาบ $no · $GradeSlug $SubjectSlug ===" -ForegroundColor Cyan
    Write-Host "    เซสชันใหม่ (โปรเซสแยก) · log -> $log"
    Write-Host "    $prompt"

    if ($DryRun) {
        $results += [pscustomobject]@{ No = $no; Status = "dry-run"; Minutes = 0 }
        continue
    }

    $t0 = Get-Date
    # โปรเซสใหม่ต่อคาบ = เซสชันใหม่เสมอ ไม่มีบริบทเก่าติดมา
    & claude -p $prompt 2>&1 | Tee-Object -FilePath $log
    $code = $LASTEXITCODE
    $mins = [math]::Round(((Get-Date) - $t0).TotalMinutes, 1)

    $status = if ($code -eq 0) { "จบ" } else { "ไม่จบ (exit $code)" }
    Write-Host "    $status · $mins นาที" -ForegroundColor (if ($code -eq 0) { "Green" } else { "Red" })
    $results += [pscustomobject]@{ No = $no; Status = $status; Minutes = $mins }
}

Write-Host ""
Write-Host "=== สรุป ===" -ForegroundColor Cyan
$results | Format-Table -AutoSize
Write-Host "log ทั้งหมดอยู่ที่ $logDir"
Write-Host "โทเคนที่ใช้จริงดูได้จากบรรทัด usage ใน log แต่ละไฟล์"
