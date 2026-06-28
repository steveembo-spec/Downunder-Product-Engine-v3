DPE Sprint 4.3 - SQLite Catalogue Foundation

This package adds the local SQLite catalogue engine.
It does NOT replace the working Build Centre.
It does NOT modify your current dpe_app.py.

FILES INCLUDED

1. dpe_catalogue_db.py
   Builds output/dpe_catalogue.db from your existing catalogue CSV.

2. dpe_catalogue_search_test.py
   Lets you test fast catalogue search in PowerShell before we wire it into the desktop app.

INSTALL

Copy these two Python files into:

C:\Users\steve\OneDrive\Documents\GitHub\Downunder-Product-Engine-v3

RUN

From PowerShell inside the project folder:

python dpe_catalogue_db.py

Then test search:

python dpe_catalogue_search_test.py

NEXT STEP

Once search is confirmed fast, we wire the Catalogue Control Centre to read from output/dpe_catalogue.db instead of rescanning the CSV.
