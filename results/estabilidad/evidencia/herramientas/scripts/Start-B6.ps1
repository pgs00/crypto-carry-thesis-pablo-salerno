param(
    [string]$Candidate = 'entregas/entrega_4/estabilidad_incertidumbre/20261001T215423Z/candidato',
    [string]$DataRoot = 'D:/Backtesting',
    [string]$RawRoot = 'D:/Backtesting/outputs/estabilidad_incertidumbre/20261001T215423Z'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$env:NUMEXPR_NUM_THREADS = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:MPLBACKEND = 'Agg'
$env:PYTHONIOENCODING = 'utf-8'
& "$projectRoot/.venv/Scripts/python.exe" -B -u -X utf8 "$projectRoot/scripts/coordinate_stability_uncertainty.py" --candidate $Candidate --data-root $DataRoot --raw-root $RawRoot
exit $LASTEXITCODE
