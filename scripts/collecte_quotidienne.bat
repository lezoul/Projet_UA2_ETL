@echo off
REM ==========================================================================
REM collecte_quotidienne.bat
REM Projet UA2 Web scraping : vehicules d'occasion (Ottawa-Gatineau)
REM Lance la collecte quotidienne (sans le diagnostic) puis le pretraitement,
REM en mode silencieux,
REM avec un fichier de log date dans logs\.
REM Lance chaque nuit par le Planificateur de taches (voir installer_tache.ps1).
REM Peut aussi etre lance a la main : double-clic sur ce fichier.
REM ==========================================================================
setlocal

REM Se placer a la racine du projet (le dossier parent de scripts\)
cd /d "%~dp0.."

REM Verifier que l'environnement virtuel existe
if not exist ".venv\Scripts\python.exe" (
    if not exist "logs" mkdir "logs"
    echo %date% %time% ERREUR : .venv\Scripts\python.exe introuvable >> "logs\erreurs_planificateur.log"
    exit /b 1
)

REM Collecte du jour (memes delais et memes regles que le notebook),
REM puis pretraitement de tous les fichiers bruts (aucune requete)
".venv\Scripts\python.exe" "src\pipeline.py" --etapes collecte pretraitement --silencieux --log
set CODE=%ERRORLEVEL%

if not "%CODE%"=="0" (
    if not exist "logs" mkdir "logs"
    echo %date% %time% ERREUR : pipeline termine avec le code %CODE% >> "logs\erreurs_planificateur.log"
)
exit /b %CODE%
