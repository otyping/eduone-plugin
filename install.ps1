# EDU ONE - ตัวช่วยติดตั้งสำหรับเครื่องพนักงาน (Windows)
#
#   irm https://raw.githubusercontent.com/otyping/eduone-plugin/main/install.ps1 | iex
#
# ออกแบบให้ "ถามก่อนทำทุกครั้ง" - ไม่มีขั้นไหนติดตั้งอะไรโดยไม่ได้รับคำตอบ
# รันซ้ำได้ปลอดภัย ข้ามสิ่งที่มีอยู่แล้ว

$ErrorActionPreference = "Stop"
$script:todo = @()

function Say($t)  { Write-Host $t }
function Head($t) { Write-Host ""; Write-Host "== $t ==" -ForegroundColor Cyan }
function Good($t) { Write-Host "  [มีแล้ว] $t" -ForegroundColor Green }
function Miss($t) { Write-Host "  [ขาด]   $t" -ForegroundColor Yellow }
function Bad($t)  { Write-Host "  [พัง]   $t" -ForegroundColor Red }

function Ask($q) {
    while ($true) {
        $a = Read-Host "$q [Y=ตกลง / N=ข้าม]"
        if ($a -eq "" -or $a -match '^[Yy]') { return $true }
        if ($a -match '^[Nn]') { return $false }
    }
}

function Find-Python312 {
    # หา Python 3.12 จาก py launcher ก่อน แล้วค่อยหาจาก PATH
    $cands = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try { $p = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null); if ($p) { $cands += $p } } catch {}
    }
    $cands += "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    if (Get-Command python -ErrorAction SilentlyContinue) { $cands += (Get-Command python).Source }
    foreach ($c in $cands) {
        if ($c -and (Test-Path $c)) {
            try {
                # เลี่ยง % ในสตริง - PowerShell ตีความเป็นตัวดำเนินการ ไม่ใช่ตัวอักษร
                $v = & $c -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))" 2>$null
                if ($v -eq "3.12") { return $c }
            } catch {}
        }
    }
    return $null
}

function Get-PluginDir {
    $base = "$env:USERPROFILE\.claude\plugins\cache\eduone\edu-one"
    if (-not (Test-Path $base)) { return $null }
    # เรียงแบบเวอร์ชันจริง - Sort-Object Name จะตัดสินว่า 3.0.9 ใหม่กว่า 3.0.10
    $d = Get-ChildItem $base -Directory -ErrorAction SilentlyContinue |
         Sort-Object { $_.Name -as [version] } | Select-Object -Last 1
    if ($d) { return $d.FullName }
    return $null
}

Write-Host ""
Write-Host "  EDU ONE - ติดตั้งเครื่องมือผลิตสื่อการเรียนการสอน" -ForegroundColor Cyan
Write-Host "  จะถามก่อนทุกขั้น ไม่ติดตั้งอะไรเองโดยไม่ได้รับคำตอบ"

# ---------------------------------------------------------------- 1 Claude Code
Head "1/6  Claude Code"
$claude = Get-Command claude -ErrorAction SilentlyContinue
if ($claude) {
    Good "$((& claude --version) -join ' ')"
} else {
    Miss "ยังไม่มี Claude Code - เป็นตัวหลักที่ใช้ทำงาน ขาดไม่ได้"
    if (Ask "  ติดตั้ง Claude Code เลยไหม (ดาวน์โหลดจาก claude.ai)") {
        irm https://claude.ai/install.ps1 | iex
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
        $claude = Get-Command claude -ErrorAction SilentlyContinue
        if ($claude) { Good "ติดตั้งแล้ว" } else { Bad "ติดตั้งไม่สำเร็จ - ลองเปิด PowerShell ใหม่แล้วรันสคริปต์นี้อีกครั้ง"; $script:todo += "Claude Code" }
    } else {
        $script:todo += "Claude Code"
    }
}

# ---------------------------------------------------------------- 2 Git for Windows
Head "2/6  Git for Windows"
if (Get-Command git -ErrorAction SilentlyContinue) {
    Good ((& git --version) -join ' ')
} else {
    Miss "ยังไม่มี git - Claude Code ใช้ Git Bash รันคำสั่ง ถ้าไม่มีจะใช้ PowerShell แทนซึ่งสคริปต์บางตัวอาจไม่ทำงาน"
    if (Ask "  เปิดหน้าดาวน์โหลด Git for Windows ไหม") {
        Start-Process "https://git-scm.com/downloads/win"
        Say "  ติดตั้งเสร็จแล้วเปิด PowerShell ใหม่ แล้วรันสคริปต์นี้อีกครั้ง"
    }
    $script:todo += "Git for Windows"
}

# ---------------------------------------------------------------- 3 Python 3.12
Head "3/6  Python 3.12"
$py = Find-Python312
if ($py) {
    Good "$py"
} else {
    Miss "ไม่พบ Python 3.12 (ต้องเป็น 3.12 เท่านั้น เพราะผลผลิตเป็นไฟล์เอกสารที่ต้องเหมือนกันทุกเครื่อง)"
    if (Ask "  ติดตั้งด้วย winget ไหม (ถ้าไม่มี winget จะเปิดหน้าดาวน์โหลดให้)") {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
            $env:Path = "$env:LOCALAPPDATA\Programs\Python\Python312;$env:LOCALAPPDATA\Programs\Python\Python312\Scripts;$env:Path"
            $py = Find-Python312
            if ($py) { Good "ติดตั้งแล้ว: $py" } else { Say "  ติดตั้งแล้วแต่ยังหาไม่เจอ - เปิด PowerShell ใหม่แล้วรันสคริปต์นี้อีกครั้ง"; $script:todo += "Python 3.12" }
        } else {
            Start-Process "https://www.python.org/downloads/release/python-3120/"
            Say "  ตอนติดตั้งอย่าลืมติ๊ก 'Add python.exe to PATH'"
            $script:todo += "Python 3.12"
        }
    } else {
        $script:todo += "Python 3.12"
    }
}

# ---------------------------------------------------------------- 4 ปลั๊กอิน
Head "4/6  ปลั๊กอิน edu-one"
if (-not $claude) {
    Miss "ข้ามไปก่อน เพราะยังไม่มี Claude Code"
    $script:todo += "ปลั๊กอิน edu-one"
} else {
    $installed = ""
    try { $installed = (& claude plugin list 2>&1 | Out-String) } catch {}
    if ($installed -match "edu-one") {
        Good "ติดตั้งแล้ว - จะลองอัปเดตให้เป็นรุ่นล่าสุด"
        if (Ask "  อัปเดตปลั๊กอินเป็นรุ่นล่าสุดไหม") {
            & claude plugin marketplace update eduone
            & claude plugin update edu-one@eduone
        }
    } else {
        Miss "ยังไม่ได้ติดตั้ง"
        if (Ask "  ติดตั้งปลั๊กอิน edu-one เลยไหม") {
            & claude plugin marketplace add otyping/eduone-plugin
            & claude plugin install edu-one@eduone
            Good "ติดตั้งแล้ว"
        } else {
            $script:todo += "ปลั๊กอิน edu-one"
        }
    }
}

# ---------------------------------------------------------------- 5 แพ็กเกจ Python
Head "5/6  แพ็กเกจ Python"
$plug = Get-PluginDir
if (-not $py) {
    Miss "ข้ามไปก่อน เพราะยังไม่มี Python 3.12"
    $script:todo += "แพ็กเกจ Python"
} elseif (-not $plug) {
    Miss "ข้ามไปก่อน เพราะยังไม่มีปลั๊กอิน (requirements.txt มากับปลั๊กอิน)"
    $script:todo += "แพ็กเกจ Python"
} else {
    $req = Join-Path $plug "requirements.txt"
    Say "  รายการอยู่ที่ $req"
    if (Ask "  ติดตั้งแพ็กเกจทั้ง 11 ตัวเลยไหม") {
        & $py -m pip install --disable-pip-version-check -r $req
        Good "ติดตั้งแพ็กเกจแล้ว"
    } else {
        $script:todo += "แพ็กเกจ Python"
    }
}

# ------------------------------------------- 6 คำสั่ง eduone-py ในเทอร์มินัลของพนักงาน
Head "6/6  คำสั่ง eduone-py ในเทอร์มินัลของคุณ"
Say "  Claude Code รู้จักคำสั่งนี้เองอยู่แล้ว แต่หน้าต่างเทอร์มินัลที่คุณเปิดเองยังไม่รู้จัก"
Say "  ซึ่งเป็นหน้าต่างที่ใช้รัน  eduone-py watch.py  ตามที่เว็บบอกระหว่างรองาน"

# เขียนลง profile แบบ AllHosts เพื่อให้ console, Windows Terminal และเทอร์มินัลใน VS Code
# เห็นเหมือนกันหมด · ถ้าเครื่องมี PowerShell ทั้งสอง edition (5.1 คู่กับ 7) ก็เขียนให้ทั้งคู่
# เพราะคนละ edition คนละไฟล์ profile - ตั้งให้ตัวเดียวแล้วไปเปิดอีกตัวจะงงว่าทำไมไม่มี
$profiles = @($PROFILE.CurrentUserAllHosts)
$other = if ($PSVersionTable.PSEdition -eq "Core") {
    # .Replace() ไม่ใช่ -replace เพราะอันหลังเป็น regex แล้ว \ ต้อง escape ซ้อน
    $PROFILE.CurrentUserAllHosts.Replace("\PowerShell\", "\WindowsPowerShell\")
} else {
    $PROFILE.CurrentUserAllHosts.Replace("\WindowsPowerShell\", "\PowerShell\")
}
if ($other -ne $PROFILE.CurrentUserAllHosts -and (Test-Path (Split-Path $other))) {
    $profiles += $other
}

# ★ ตัวฟังก์ชันเป็น ASCII ล้วนโดยตั้งใจ - profile ของพนักงานอาจถูกเขียนด้วย encoding อื่น
#   มาก่อน ถ้าต่อท้ายด้วยข้อความไทยจะได้ BOM กลางไฟล์ แล้วบรรทัดไทยเพี้ยนทั้งไฟล์
# ★ หาเวอร์ชันตอนเรียก ไม่ฝังเลขเวอร์ชันไว้ - path มีเลขเวอร์ชันอยู่ (…\edu-one\3.0.3\bin)
#   ถ้าฝังไว้ พออัปเดตปลั๊กอินครั้งเดียวก็พังทันที
$fn = @'

# EDU ONE - call eduone-py from your own terminal (resolves the newest plugin version)
function eduone-py {
    $root = "$env:USERPROFILE\.claude\plugins\cache\eduone\edu-one"
    $bin  = (Get-ChildItem "$root\*\bin" -Directory -ErrorAction SilentlyContinue |
             Sort-Object { $_.Parent.Name -as [version] } | Select-Object -Last 1).FullName
    if (-not $bin) { Write-Error "eduone-py: edu-one plugin not installed"; return }
    & "$bin\eduone-py.cmd" @args
}
'@

$need = @()
foreach ($f in $profiles) {
    if ((Test-Path $f) -and ((Get-Content -Raw $f) -match "function eduone-py")) {
        Good "ตั้งไว้แล้ว: $f"
    } else {
        $need += $f
    }
}
if ($need.Count -gt 0) {
    Miss "ยังไม่ได้ตั้ง - เปิดเทอร์มินัลเองแล้วพิมพ์ eduone-py จะขึ้นว่าไม่รู้จักคำสั่ง"
    if (Ask "  เพิ่มให้เลยไหม (ต่อท้ายไฟล์ profile ของเดิมไม่หาย)") {
        foreach ($f in $need) {
            # ห้ามใช้ New-Item -Force กับไฟล์ที่มีอยู่แล้ว มันล้างไฟล์ทิ้ง
            if (-not (Test-Path $f)) { New-Item -ItemType File -Path $f -Force | Out-Null }
            Add-Content -Path $f -Value $fn
            Good "เพิ่มแล้ว: $f"
        }
    } else {
        $script:todo += "คำสั่ง eduone-py"
    }
}

# ★ เขียนฟังก์ชันลง profile สำเร็จ ไม่ได้แปลว่าจะใช้ได้ — ค่าเริ่มต้นของ Windows คือ
#   ExecutionPolicy = Restricted ซึ่งแปลว่า **ไม่โหลด profile เลย** ฟังก์ชันที่เพิ่งเขียน
#   จึงตายเงียบ ๆ ทั้งที่ไฟล์ถูกต้องทุกตัวอักษร (เจอจริงบนเครื่องผู้ดูแลตอนออก 3.0.3)
#   `irm | iex` ไม่โดนกฎนี้เพราะรันจากสตริง ไม่ใช่จากไฟล์ ตัวช่วยจึงติดตั้งผ่านมาได้ปกติ
$hasFn = (Test-Path $PROFILE.CurrentUserAllHosts) -and
         ((Get-Content -Raw $PROFILE.CurrentUserAllHosts) -match "function eduone-py")
if ($hasFn) {
    $ep = Get-ExecutionPolicy
    if ($ep -eq "Restricted" -or $ep -eq "AllSigned") {
        Miss "PowerShell ตั้งไว้ไม่ให้โหลด profile (ExecutionPolicy = $ep) ฟังก์ชันที่เขียนไปจะไม่ทำงาน"
        $gpo = @((Get-ExecutionPolicy -Scope MachinePolicy), (Get-ExecutionPolicy -Scope UserPolicy))
        if ($gpo -contains "Restricted" -or $gpo -contains "AllSigned") {
            Bad "ค่านี้ถูกบังคับมาจาก Group Policy ขององค์กร - ต้องให้ฝ่ายไอทีแก้ให้"
            $script:todo += "ExecutionPolicy"
        } elseif (Ask "  ตั้งเป็น RemoteSigned เฉพาะบัญชีคุณไหม (ไม่ต้องใช้สิทธิ์ผู้ดูแล)") {
            Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
            Good "ตั้งแล้ว: CurrentUser = $(Get-ExecutionPolicy -Scope CurrentUser)"
            Say "  RemoteSigned = สคริปต์ที่เขียนเองรันได้ ที่โหลดมาจากเน็ตยังต้องมีลายเซ็น"
        } else {
            $script:todo += "ExecutionPolicy"
        }
    }
}

# ★ ถึงตรงนี้ไฟล์ถูกและ policy ผ่านแล้ว แต่ **หน้าต่างนี้ยังไม่รู้จักคำสั่ง** เพราะ
#   PowerShell อ่าน profile ตอนเปิดหน้าต่างเท่านั้น — ตอนหน้าต่างนี้เปิดขึ้นมา
#   ยังไม่มีฟังก์ชัน (หรือ policy ยังบล็อกอยู่) จึงต้องดอตซอร์สซ้ำเองที่นี่
#   ไม่งั้นพนักงานจะพิมพ์คำสั่งในหน้าต่างเดิมแล้วเจอ "not recognized" ทั้งที่ทุกอย่างถูก
if ($hasFn) {
    try { . $PROFILE.CurrentUserAllHosts } catch {}
    if (Get-Command eduone-py -ErrorAction SilentlyContinue) {
        Good "หน้าต่างนี้พิมพ์ eduone-py ได้เลยแล้ว"
    } else {
        Miss "หน้าต่างนี้ยังพิมพ์ eduone-py ไม่ได้ - profile ถูกอ่านตอนเปิดหน้าต่างเท่านั้น"
        Say  "  >>> ปิดหน้าต่างนี้ แล้วเปิด PowerShell ใหม่หนึ่งครั้ง จึงจะใช้คำสั่งได้ <<<"
    }
}

# ---------------------------------------------------------------- โฟลเดอร์งาน
Head "โฟลเดอร์งาน"
Say "  ผลผลิตทุกชิ้นจะลงที่นี่ แยกจากตัวปลั๊กอิน"
$def = Join-Path $env:USERPROFILE "eduone-work"
$w = Read-Host "  จะวางไว้ที่ไหน [กด Enter = $def]"
if ($w -eq "") { $w = $def }
if (Test-Path $w) {
    Good "มีอยู่แล้ว: $w"
} else {
    if (Ask "  สร้างโฟลเดอร์ $w ไหม") {
        New-Item -ItemType Directory -Force $w | Out-Null
        Good "สร้างแล้ว: $w"
    }
}

# ---------------------------------------------------------------- กฎอนุญาต
Head "กฎอนุญาตให้รันสคริปต์โดยไม่ต้องถามทุกครั้ง"
Say "  ปกติ Claude Code จะถามอนุญาตทุกครั้งที่รันคำสั่ง ซึ่งจะถามบ่อยมากตอนผลิตสื่อ"
Say "  กฎนี้อนุญาตเฉพาะ eduone-py (ตัวห่อของ EDU ONE) ไม่ได้เปิดให้รันอะไรก็ได้"
$settingsDir = Join-Path $w ".claude"
$settingsFile = Join-Path $settingsDir "settings.json"
if (Test-Path $settingsFile) {
    $cur = Get-Content -Raw $settingsFile
    if ($cur -match "eduone-py") {
        Good "ตั้งไว้แล้ว: $settingsFile"
    } else {
        Miss "มี settings.json อยู่แล้วแต่ยังไม่มีกฎนี้ - ไม่แก้ทับให้ กันของเดิมหาย"
        Say "  เพิ่มบรรทัดนี้ในส่วน permissions.allow เอง:  \"Bash(eduone-py *)\""
    }
} else {
    if (Ask "  ตั้งกฎอนุญาตให้ไหม (เขียนที่ $settingsFile)") {
        New-Item -ItemType Directory -Force $settingsDir | Out-Null
        $json = @"
{
  "permissions": {
    "allow": [
      "Bash(eduone-py *)"
    ]
  }
}
"@
        [System.IO.File]::WriteAllText($settingsFile, $json, (New-Object System.Text.UTF8Encoding $false))
        Good "เขียนแล้ว: $settingsFile"
    }
}
# ---------------------------------------------------------------- ตรวจผล
Head "ตรวจผลรวม"
$plug = Get-PluginDir
if ($py -and $plug -and (Test-Path (Join-Path $plug "scripts\doctor.py"))) {
    Push-Location $w
    $env:PYTHONIOENCODING = "utf-8"
    & $py (Join-Path $plug "scripts\doctor.py")
    Pop-Location
} else {
    Say "  ยังตรวจไม่ได้ - ติดตั้งส่วนที่ขาดให้ครบก่อน"
}

Write-Host ""
if ($script:todo.Count -gt 0) {
    Write-Host "ยังเหลือที่ต้องทำ: $($script:todo -join ', ')" -ForegroundColor Yellow
    Write-Host "ทำเสร็จแล้วเปิด PowerShell ใหม่ แล้วรันสคริปต์นี้ซ้ำได้เลย"
} else {
    Write-Host "เรียบร้อย" -ForegroundColor Green
    Write-Host "ขั้นต่อไป: cd `"$w`"  แล้วพิมพ์  claude  เพื่อเริ่มใช้งาน"
    Write-Host "ครั้งแรกจะให้ล็อกอินผ่านเบราว์เซอร์ - ใช้บัญชีที่บริษัทเบิกให้"
}
