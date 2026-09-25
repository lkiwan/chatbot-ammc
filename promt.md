# Prompt — indexation complète (468 rapports / 102 entreprises) vers le serveur de prod

## CONTEXTE (ne rien supposer, tout est vérifié)

- Repo local : `C:\Users\arhou\OneDrive\Bureau\projet omar\colab\chatbot-ammc` (branche `main`, remote GitHub `lkiwan/chatbot-ammc`)
- Serveur prod : `ubuntu@150.136.64.50`, clé `C:\Users\arhou\Downloads\ssh-key-2026-08-20.key`
  - ARM64 aarch64, 1 vCPU, 5.8 Go RAM (~2.6 Go libres), Docker 26.1.3
  - IMPORTANT : `docker compose` N'EXISTE PAS, utiliser `docker-compose` (binaire autonome v2.29.2)
- App prod : `/home/ubuntu/ammc/app`, conteneur `ammc_prod_app` (127.0.0.1:8010 -> 8000)
  - PostgreSQL interne `ammc_prod_postgres`, tunnel Cloudflare Quick `ammc_quicktunnel`
- Front : Vercel, `https://www.aivox.website` + `https://chatbot-ammc.vercel.app` (racine = `frontend/`, build auto depuis GitHub)
- API protégée par `X-Api-Token`, `RATE_LIMIT_PER_MIN=20`, `CORS_ORIGINS` contient les 2 domaines
- `chromadb` épinglé à `1.5.9` (requirements.txt) — NE PAS modifier cette version

## OBJECTIF

Passer de 137 rapports / 21 entreprises à 468 rapports / 102 entreprises, sans downtime
prolongé et avec rollback < 2 min.

## ÉTAT ACTUEL (vérifié, ne pas refaire l'analyse)

- `ammc_report_scraper/data/reports/<SECTEUR>/<ENTREPRISE>/<ANNEE>/annual_report.pdf` = 468 PDF, tous au layout 4 niveaux correct
- `data/chunks/*.json` = 139 fichiers (132 correspondent aux 468)
- **336 rapports / 71 entreprises NON convertis**
- `iter_reports()` (`build_index.py:75`) découvre déjà les 468 via `rglob`
- `build_index(force=False)` est incrémental : réutilise les chunks existants, ne fait que les manquants

## ÉTAPE 1 — Reconstruction LOCALE uniquement

Ne rien toucher au serveur avant.

```bash
cd "C:\Users\arhou\OneDrive\Bureau\projet omar\colab\chatbot-ammc"
python main.py ingest
```

- **INTERDIT** : `python main.py index --force` et `POST /api/ingest --force`
  (`--force` supprime la collection Chroma et ré-embed les 132 rapports déjà faits = plusieurs heures perdues)
- Ne pas fermer le terminal. Surveiller la progression et la taille de `.chroma`.
- Estimation : ~133 000 chunks, `.chroma` ~1,8 Go, plusieurs heures.

## ÉTAPE 2 — Contrôles locaux (OBLIGATOIRES avant tout upload)

- Compter les chunks dans `.chroma`
- `data/chunks` doit contenir 468 fichiers `.json`
- L'app locale (`/api/health`) doit renvoyer `index:true`, `chunks:<n>`, `rapports:468`
- `/api/companies` doit renvoyer ~102 entrées
- Tester 3 questions sur 3 entreprises **INÉDITES**, une par secteur
  (ex. `CARTON_EMBALLAGE_IMPRESSION`, `CHIMIE_PARACHIMIE`, `HOLDING`)
  et vérifier que la réponse contient des sources avec le bon rapport
- Si un rapport échoue : NE PAS relancer en boucle, noter l'échec et continuer

## ÉTAPE 3 — Upload (AUCUN PDF)

Fichiers à envoyer :

- `.chroma/`
- `data/chunks/`
- `data/raw/`
- `data/reports.json`
- `data/scraper_meta.json`
- `data/metrics.json`

- **INTERDIT** : ne jamais envoyer les PDF (`ammc_report_scraper/data/reports` = 468 PDF, ~1-2 Go)
- Méthode : `scp`/`rsync` en plusieurs lots, puis **VÉRIFIER sha256 de chaque lot avant/après**
- Destination de staging (l'app continue de tourner) :
  - `/home/ubuntu/ammc/staging-2026xxxx/.chroma`
  - `/home/ubuntu/ammc/staging-2026xxxx/data`
- L'app doit rester **UP** pendant tout l'upload.

## ÉTAPE 4 — Bascule (downtime 1-2 min)

```bash
cd /home/ubuntu/ammc/app
docker-compose -f docker-compose.prod.yml stop app
mv .chroma .chroma.bak-$(date +%Y%m%d%H%M)     # rollback possible
mv /home/ubuntu/ammc/staging-2026xxxx/.chroma .chroma
rsync -a --delete /home/ubuntu/ammc/staging-2026xxxx/data/ ./data/
docker-compose -f docker-compose.prod.yml up -d
```

- Vérifier : `/api/health` (avec `X-Api-Token`), `/api/companies` (~102), 3 questions
- Si OK : conserver `.chroma.bak` 24h puis le supprimer (**demander avant**)
- Si KO : arrêter, `rm -rf .chroma`, `mv .chroma.bak-<date> .chroma`, `up -d`

## ÉTAPE 5 — Frontend (seulement si nécessaire)

- `frontend/src/components/ChatPanel.jsx` : le texte d'accueil « l'ensemble des 70
  entreprises indexées » est en dur → le remplacer par une valeur dynamique ou le supprimer.
  Le topbar lit déjà `/api/reports` et `/api/companies`.
- Ne redéployer Vercel que si le code frontend change (sinon inutile).

## CONTRAINTES GÉNÉRALES

- Toujours demander avant de supprimer, écraser ou réinitialiser quoi que ce soit
- Ne jamais commiter `.env`, `data/` ni `.chroma/` (déjà dans `.gitignore`)
- Le modèle d'embedding doit être identique local/serveur (cache dans le volume `model_cache`)
- Si une étape échoue : s'arrêter et rapporter, ne pas contourner
