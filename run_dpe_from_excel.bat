@echo off
title Downunder Product Engine v3

cd /d "C:\Users\steve\OneDrive\Documents\GitHub\Downunder-Product-Engine-v3"

echo ============================================
echo DOWNUNDER PRODUCT ENGINE v3
echo ============================================
echo.
echo Running catalogue build...
echo.

python run_dpe_v3.py

echo.
echo ============================================
echo DPE finished.
echo Output file:
echo output\dpe_v3_shopify_ready.csv
echo ============================================
echo.

pause