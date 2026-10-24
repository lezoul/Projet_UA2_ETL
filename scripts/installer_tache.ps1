<#
installer_tache.ps1
Projet UA2 Web scraping : véhicules d'occasion (Ottawa-Gatineau)

Inscrit la collecte quotidienne dans le Planificateur de tâches de Windows.
  - tous les jours à 3 h du matin (heure creuse pour les sites) ;
  - si l'ordinateur est en veille à 3 h, Windows le réveille pour la tâche (WakeToRun) ;
    pipeline.py empêche ensuite la remise en veille jusqu'à la fin de l'exécution ;
  - si l'ordinateur était éteint à 3 h, la tâche se lance dès qu'il redémarre (StartWhenAvailable) ;
  - fonctionne aussi sur batterie (ordinateur portable) ;
  - arrêtée automatiquement si elle dure plus d'une heure (garde-fou).

Utilisation (PowerShell, dans le dossier du projet) :
    powershell -ExecutionPolicy Bypass -File scripts\installer_tache.ps1              # installer
    powershell -ExecutionPolicy Bypass -File scripts\installer_tache.ps1 -Heure 02:30 # autre heure
    powershell -ExecutionPolicy Bypass -File scripts\installer_tache.ps1 -Desinstaller

Pas besoin des droits administrateur : la tâche s'exécute avec ton compte, quand ta session Windows est ouverte.
#>

param(
    [string]$Heure = "03:00",
    [switch]$Desinstaller
)

$NomTache = "Projet UA2 - collecte quotidienne vehicules"

if ($Desinstaller) {
    Unregister-ScheduledTask -TaskName $NomTache -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tâche « $NomTache » supprimée."
    exit 0
}

# Chemins calculés à partir de l'emplacement de ce script (fonctionne malgré les espaces dans les noms de dossiers)
$Racine = Split-Path -Parent $PSScriptRoot
$Bat    = Join-Path $PSScriptRoot "collecte_quotidienne.bat"

if (-not (Test-Path $Bat)) { Write-Error "Introuvable : $Bat"; exit 1 }
if (-not (Test-Path (Join-Path $Racine ".venv\Scripts\python.exe"))) {
    Write-Error "Environnement virtuel introuvable : $Racine\.venv. Crée-le avant d'installer la tâche."
    exit 1
}

$Action   = New-ScheduledTaskAction -Execute $Bat -WorkingDirectory $Racine
$Trigger  = New-ScheduledTaskTrigger -Daily -At $Heure
$Reglages = New-ScheduledTaskSettingsSet `
              -StartWhenAvailable `
              -WakeToRun `
              -AllowStartIfOnBatteries `
              -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
              -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $NomTache `
    -Description "Collecte quotidienne des inventaires de véhicules d'occasion (projet UA2, La Cité). Une fois par jour, mêmes délais et mêmes règles que le notebook." `
    -Action $Action -Trigger $Trigger -Settings $Reglages -Force | Out-Null

$Tache = Get-ScheduledTask -TaskName $NomTache
$Info  = Get-ScheduledTaskInfo -TaskName $NomTache
Write-Host ""
Write-Host "Tâche installée : $NomTache"
Write-Host "  Script        : $Bat"
Write-Host "  Dossier       : $Racine"
Write-Host "  Heure         : tous les jours à $Heure (réveille l'ordinateur s'il est en veille)"
Write-Host "  Prochaine exécution : $($Info.NextRunTime)"
Write-Host ""
Write-Host "Pour tester tout de suite : Start-ScheduledTask -TaskName `"$NomTache`""
Write-Host "Les logs seront dans : $Racine\logs"
