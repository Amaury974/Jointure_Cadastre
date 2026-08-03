# Jointure Cadastre — plugin QGIS

*Développé intégralement avec Claude.ai*

Plugin QGIS 3.x permettant de joindre automatiquement un tableau de données
(CSV, XLSX ou ODS) à une couche de parcelles cadastrales, avec :
- reconnaissance automatique des communes de La Réunion (24 communes,
  noms/alias/fautes de frappe courantes) et récupération de leur code INSEE ;
- découpage des cellules contenant plusieurs parcelles (avec **duplication de
  ligne + avertissement**) ;
- gestion de 3 dispositions de colonnes possibles, avec **détection
  automatique** (corrigeable manuellement) ;
- normalisation/uniformisation des numéros de parcelles ;
- **récupération automatique des parcelles cadastrales** via le service
  ouvert cadastre.data.gouv.fr (Etalab/DINUM), commune par commune — ou,
  au choix, couche de référence sur serveur FTP, ou couche locale fournie
  par l'utilisateur.

## Structure du projet

```
parcelle_joiner/
├── __init__.py                     # point d'entrée QGIS (classFactory)
├── metadata.txt                    # métadonnées du plugin
├── parcelle_joiner.py              # classe principale : menu/toolbar
├── parcelle_joiner_dialog.py        # logique de la boîte de dialogue principale (UI <-> métier)
├── parcelle_joiner_dialog_base.ui   # interface graphique principale (Qt Designer)
├── ftp_settings_dialog.py           # boîte de dialogue "Paramètres FTP..."
├── ftp_settings_dialog_base.ui      # interface graphique des paramètres FTP
├── resources.qrc                   # ressources (icônes)
├── icon.png                        # icône du plugin (À AJOUTER)
├── core/
│   ├── __init__.py
│   ├── reunion_communes.py         # référentiel des 24 communes de La Réunion + codes INSEE
│   ├── commune_matcher.py          # reconnaissance du nom de commune (exact + approché)
│   ├── parcel_parser.py            # découpage d'une cellule en 1..N parcelles (section, numéro)
│   ├── column_detector.py          # détection automatique du rôle des colonnes
│   ├── row_expander.py             # orchestration : commune + découpage + duplication de lignes
│   ├── table_reader.py             # lecture unifiée CSV / XLSX / ODS (via GDAL/OGR, sans dépendance externe)
│   ├── normalize.py                # normalisation de chaînes / composition de codes parcelle
│   ├── ftp_loader.py                # téléchargement/cache de la couche cadastrale FTP (option alternative)
│   ├── settings.py                  # paramètres persistants (QSettings + gestionnaire d'authentification QGIS)
│   ├── cadastre_source.py          # récupération auto des parcelles par commune (cadastre.data.gouv.fr)
│   └── join_processor.py           # préparation + jointure finale + construction de la couche résultat
└── tests/
    ├── __init__.py
    ├── test_normalize.py
    ├── test_commune_matcher.py
    ├── test_parcel_parser.py
    ├── test_row_expander.py
    └── test_cadastre_source.py
```

## Fonctionnement du traitement

1. **Lecture du tableau source** (`table_reader.py`) : CSV, XLSX ou ODS,
   ouvert nativement via GDAL/OGR (déjà inclus dans QGIS — aucune
   installation de `pandas`/`openpyxl` requise). Pour les classeurs
   multi-feuilles, une feuille est sélectionnable dans l'interface.

2. **Détection des colonnes** (`column_detector.py`) — détection **mixte**,
   combinant deux signaux :
   - le **nom des colonnes** (en-têtes) : signal prioritaire et indépendant
     du contenu — une colonne "Commune" ou "N° de parcelle(s)" est un indice
     quasi certain ; une colonne "Date du paiement", "Montant", "Surface"...
     est exclue d'office par mot-clé, quel que soit son contenu ;
   - le **contenu** de la colonne (comme avant : correspondance avec le
     référentiel des communes / le parseur de parcelles), utilisé en
     complément pour les rôles que les en-têtes n'ont pas permis de résoudre
     (en-têtes non explicites, absentes ou ambiguës).

   Cette combinaison identifie :
   - la colonne "commune"
   - soit une colonne combinée "section+numéro", soit deux colonnes séparées
     "section" et "numéro", soit une seule colonne "tout en un"

   L'utilisateur peut à tout moment changer le mode (3 boutons radio) et
   corriger les colonnes détectées via les listes déroulantes.

   Seules les colonnes de type **texte** (ou entier) sont candidates par la
   voie CONTENU (`table_reader.classifier_types_champs`) : les colonnes
   Date/Heure/Numérique à virgule en sont exclues. Un filtrage complémentaire
   ignore aussi, lors de l'échantillonnage, les lignes quasi entièrement
   vides ("fantômes").

   *Pourquoi une détection mixte plutôt que le contenu seul ?* Une colonne
   de dates peut, selon la façon dont GDAL/OGR restitue les valeurs d'un
   fichier Excel (représentation textuelle avec séparateurs "/", artefacts
   sur cellules vides mises en forme, format de champ non reconnu comme
   Date...), ressembler par coïncidence à des fragments de numéro de
   parcelle et obtenir un meilleur score de contenu que la vraie colonne —
   observé en pratique sur un cas réel. Le nom de la colonne suffit à lui
   seul à écarter ce cas, sans dépendre de la fiabilité du typage GDAL.

3. **Préparation des lignes** (`row_expander.py`) :
   - la commune est identifiée via `commune_matcher.py` : correspondance
     exacte sur alias normalisés (nom, "code postal - nom"), reconnaissance
     directe si la valeur est un **code INSEE seul** (ex: `"97411"`, y
     compris si stockée comme nombre par un tableur), puis correspondance
     approchée en dernier repli ;
   - chaque cellule de parcelle(s) est découpée par `parcel_parser.py`, qui
     gère notamment le cas où une seule des valeurs porte la lettre de
     section et les suivantes en héritent (`"BM 180 / 213 / 104"` →
     BM180, BM213, BM104) ;
   - **si plusieurs parcelles sont détectées sur une ligne, celle-ci est
     dupliquée** (une ligne de sortie par parcelle) et un avertissement est
     ajouté dans la colonne `avertissements` de la couche résultat.

4. **Jointure** (`join_processor.py`) : le code de parcelle composé
   (`code_insee + préfixe + section + numéro`) est comparé au champ
   normalisé de la couche cadastrale. Deux couches sont produites :
   - une couche **polygone** (`resultat_jointure`) avec les parcelles
     effectivement trouvées dans le cadastre (géométrie + tous les
     attributs d'origine + commune/section/numéro détectés + statut `ok`
     ou `doublon_cadastre`) ;
   - une couche **tableau, sans géométrie** (`parcelles_non_reconnues`),
     ajoutée séparément au projet, listant les parcelles pour lesquelles
     aucune correspondance n'a été trouvée (commune non reconnue ou numéro
     absent du cadastre), avec la colonne `avertissements` expliquant
     pourquoi — pratique pour repérer/corriger/exporter uniquement les cas
     à problème sans les mêler à la couche cartographique.

## Référentiel des communes

`core/reunion_communes.py` contient les 24 communes de La Réunion avec leur
code INSEE (COG au 1er janvier 2026) et des alias courants (sans accents,
abréviations "St"/"Ste", variantes de tirets/espaces), ainsi qu'un index par
code INSEE pour la reconnaissance directe des valeurs numériques (voir
point 3 ci-dessus). Si ce plugin doit être utilisé sur un autre territoire,
il suffit de remplacer ce fichier par un référentiel équivalent (même
structure `COMMUNES_REUNION`) ; le reste du code n'en dépend pas directement.

## Sources de la couche cadastrale

Trois options, sélectionnables dans l'interface :

1. **Récupération automatique (recommandée, par défaut)** — `cadastre_source.py`
   télécharge, pour chaque commune identifiée dans le tableau source (et
   seulement celles-là), le fichier GeoJSON des parcelles publié par
   [cadastre.data.gouv.fr](https://cadastre.data.gouv.fr/datasets/cadastre-etalab)
   (service ouvert de la DINUM/Etalab, issu du PCI Vecteur de la DGFiP, mis à
   jour plusieurs fois par an, aucune clé d'API requise). Les fichiers sont
   mis en cache localement (30 jours) pour éviter de retélécharger à chaque
   exécution. Le champ de jointure utilisé est `id`, qui contient déjà le
   numéro de parcelle complet dans ces données. Comme le plugin sait déjà
   quelles communes sont nécessaires avant même de contacter le cadastre
   (grâce à `commune_matcher.py`), seules les communes réellement présentes
   dans vos données sont téléchargées — pas tout un département.

2. **Serveur FTP** — pour un référentiel interne à votre organisation
   (couche déjà préparée/homogénéisée). Configurable via le menu
   **Extensions > Parcelle Joiner > Paramètres FTP...** ou via le bouton
   dédié dans la boîte de dialogue principale.
   - Hôte, port et chemin du fichier distant sont enregistrés via QSettings
     (non chiffré, adapté à des informations non sensibles).
   - **Les identifiants (utilisateur/mot de passe) sont gérés par le
     gestionnaire d'authentification de QGIS** (`QgsAuthManager`), via le
     widget standard `QgsAuthConfigSelect` — base **chiffrée**, protégée par
     le mot de passe maître de QGIS, partagée avec les autres couches/plugins
     du projet. Le plugin ne stocke jamais le mot de passe lui-même, mais
     uniquement l'identifiant de la configuration ("authcfg", une courte
     chaîne générée par QGIS).
   - Le fichier distant peut être un shapefile (`.shp` — les fichiers
     annexes `.shx`/`.dbf`/`.prj` sont alors aussi récupérés) ou un fichier
     unique directement lisible par OGR (GeoJSON, GeoPackage...) — détecté
     automatiquement selon l'extension.

3. **Couche locale** — si l'utilisateur n'a accès à aucune des deux sources
   ci-dessus, il peut fournir sa propre couche de parcelles déjà chargée
   dans QGIS.

## À faire avant la première exécution

1. **Icône** : ajoutez un fichier `icon.png` (256x256 conseillé) à la racine.
2. **Configurer le FTP (si utilisé)** : depuis QGIS, menu **Extensions >
   Parcelle Joiner > Paramètres FTP...** — renseignez l'hôte, le port, le
   chemin du fichier distant, et créez/sélectionnez une configuration
   d'authentification QGIS (bouton "..." à côté du sélecteur) pour
   l'utilisateur et le mot de passe. Utilisez le bouton "Tester la
   connexion" pour vérifier avant d'enregistrer.
3. Vérifiez que le champ choisi dans la couche cadastrale locale/FTP contient
   bien le numéro de parcelle complet (code commune + section + numéro) —
   c'est ce champ qui est comparé au code composé à partir du tableau source.

## Installer le plugin en local pour tester

```bash
# Linux
ln -s /chemin/vers/parcelle_joiner ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/parcelle_joiner

# Windows (invite de commandes en admin)
mklink /D "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\parcelle_joiner" "C:\chemin\vers\parcelle_joiner"
```

Puis dans QGIS : **Extensions > Installer/Gérer les extensions > Extensions installées**,
cocher "Parcelle Joiner".

## Lancer les tests unitaires (sans QGIS)

Tous les modules `core/` sauf `table_reader.py` et `join_processor.py` (qui
utilisent l'API QGIS) sont testables en pur Python :

```bash
cd parcelle_joiner
python3 -m unittest discover -s tests -v
```

## Prochaines étapes suggérées

- Étendre `reunion_communes.py` à d'autres départements si besoin (ou
  généraliser via l'API découpage administratif de data.gouv.fr).
- Ajout d'un `QgsProcessingAlgorithm` pour exposer le traitement dans la
  boîte à outils de traitement QGIS (exécution en tâche de fond, historique).
- Export du rapport de jointure (numéros non trouvés, doublons, communes non
  reconnues) en CSV, en plus du log affiché dans l'interface.
- Onglet "Paramètres" pour configurer le serveur FTP depuis l'interface.
- Mode "tout en un" (commune + section + numéro dans une seule colonne) :
  la détection actuelle est fonctionnelle mais heuristique, faute d'exemple
  réel disponible au moment du développement — à affiner avec de vraies
  données si ce format est utilisé en pratique.
