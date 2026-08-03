# Parcelle Joiner — plugin QGIS

Squelette de plugin QGIS 3.x permettant de joindre automatiquement un
tableau de données à une couche de parcelles cadastrales, avec une étape
de correction/uniformisation des numéros de parcelles.

## Structure du projet

```
parcelle_joiner/
├── __init__.py                     # point d'entrée QGIS (classFactory)
├── metadata.txt                    # métadonnées du plugin (nom, version, etc.)
├── parcelle_joiner.py              # classe principale : menu/toolbar, cycle de vie
├── parcelle_joiner_dialog.py        # logique de la boîte de dialogue (UI <-> métier)
├── parcelle_joiner_dialog_base.ui   # interface graphique (Qt Designer)
├── resources.qrc                   # ressources (icônes) — à compiler en resources.py
├── icon.png                        # icône du plugin (À AJOUTER — voir ci-dessous)
├── core/
│   ├── __init__.py
│   ├── normalize.py                # normalisation des numéros de parcelles (sans dépendance QGIS)
│   ├── ftp_loader.py               # téléchargement/cache de la couche cadastrale FTP
│   └── join_processor.py           # jointure tableau <-> cadastre + rapport
└── tests/
    ├── __init__.py
    └── test_normalize.py           # tests unitaires (exécutables sans QGIS)
```

## À faire avant la première exécution

1. **Icône** : ajoutez un fichier `icon.png` (256x256 conseillé) à la racine du plugin.
2. **Compiler les ressources Qt** (optionnel si vous chargez l'icône directement par
   chemin, comme fait actuellement dans `parcelle_joiner.py`) :
   ```
   pyrcc5 resources.qrc -o resources.py
   ```
3. **Configurer le FTP** dans `core/ftp_loader.py` :
   `FTP_HOST`, `FTP_USER`, `FTP_PASSWORD`, `FTP_CHEMIN_DISTANT`.
   Pour un usage plus flexible, migrez ces valeurs vers `QSettings` et ajoutez un
   onglet "Paramètres" dans le dialogue.
4. **Adapter la normalisation** dans `core/normalize.py` selon le format réel de vos
   numéros de parcelles (le format par défaut suit la convention cadastrale française
   `commune(5) + préfixe(3) + section(2) + numéro(4)`).

## Installer le plugin en local pour tester

```bash
# Linux
ln -s /chemin/vers/parcelle_joiner ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/parcelle_joiner

# Windows (invite de commandes en admin)
mklink /D "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\parcelle_joiner" "C:\chemin\vers\parcelle_joiner"
```

Puis dans QGIS : **Extensions > Installer/Gérer les extensions > Extensions installées**,
cocher "Parcelle Joiner", et l'icône apparaît dans la barre d'outils.

## Lancer les tests unitaires (sans QGIS)

```bash
cd parcelle_joiner
python3 -m unittest tests/test_normalize.py -v
```

## Prochaines étapes suggérées

- Support des tableaux XLSX (via `pandas`/`openpyxl`) en plus du CSV/QgsVectorLayer natif.
- Ajout d'un `QgsProcessingAlgorithm` pour exposer le traitement dans la boîte à outils
  de traitement QGIS (exécution en tâche de fond, historique, chaînage avec d'autres
  algorithmes).
- Export du rapport de jointure (numéros non trouvés, doublons) en CSV.
- Onglet "Paramètres" pour configurer le serveur FTP depuis l'interface plutôt qu'en dur
  dans le code.
- Gestion de plusieurs formats de couches cadastrales de référence (GeoPackage,
  shapefile zippé, etc.) avec détection automatique.
