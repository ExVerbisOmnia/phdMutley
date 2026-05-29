$procs = Get-Process python* -ErrorAction SilentlyContinue
foreach ($p in ($procs | Sort-Object WorkingSet64 -Descending)) {
    $mb = [math]::Round($p.WorkingSet64 / 1MB)
    Write-Host ("PID {0}: {1} MB" -f $p.Id, $mb)
}
$totalGB = [math]::Round(($procs | Measure-Object WorkingSet64 -Sum).Sum / 1GB, 2)
Write-Host ("Total Python: {0} GB" -f $totalGB)
$os = Get-CimInstance Win32_OperatingSystem
$freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
Write-Host ("Free RAM: {0} GB" -f $freeGB)
