# Wielerbulletin

Elke ochtend om acht uur vijf minuten wielernieuws, voorgelezen als zakelijk nieuwsbulletin. Een PWA in geel en zwart die je via Safari op je iPhone-beginscherm zet.

## Hoe het werkt

| Tijd | Wie | Wat |
|---|---|---|
| 07:45 | Geplande Claude-taak | Zoekt het wielernieuws, schrijft `episodes/<datum>.md` en pusht dat naar `main` |
| ± 07:50 | GitHub Action `publish.yml` | Spreekt elk hoofdstuk in met ElevenLabs (`eleven_v4`), voegt samen, berekent hoofdstuktijden en golfvorm, schrijft `feed.json` en publiceert naar GitHub Pages |
| 08:00 | De app | Haalt `feed.json` op en zet het nieuwe bulletin klaar |

De ElevenLabs-sleutel staat alleen als secret in GitHub; Claude ziet hem nooit. De audio staat op de aparte branch `audio` (alleen de laatste 14 dagen, telkens overschreven), zodat de repository niet dagelijks megabytes groeit.

## Eenmalig instellen

1. **Repository aanmaken** op GitHub: `Wim1201/wielerbulletin`. Publiek is het eenvoudigst (GitHub Pages is gratis voor publieke repo's; voor een privé-repo met Pages heb je GitHub Pro nodig).
2. **Bestanden pushen** (Git Bash):
   ```bash
   cd ~/wielerbulletin
   git init -b main
   git add README.md app scripts episodes .github .gitignore docs/wielerbulletin_verslag_opzet_09-10-2026.md
   git status --short | grep -E "^A"
   git commit -m "Wielerbulletin: app, pijplijn en eerste aflevering"
   git remote add origin https://github.com/Wim1201/wielerbulletin.git
   git push -u origin main
   ```
3. **Secrets** in GitHub → Settings → Secrets and variables → Actions → *New repository secret*:
   - `ELEVENLABS_API_KEY` — je API-sleutel van elevenlabs.io (Profile → API keys). Geef de sleutel minimaal *Text to Speech*-rechten.
   - `ELEVENLABS_VOICE_ID` — het id van een Nederlandse stem (Voices → stem kiezen → *Copy voice ID*). Kies een rustige, zakelijke nieuwslezersstem.
   - Optioneel als *variable* (niet secret): `ELEVENLABS_MODEL`, standaard `eleven_v4`.
4. **Pages aanzetten**: Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
5. **Eerste run**: Actions → *Publiceer Wielerbulletin* → *Run workflow*. Na een paar minuten staat de app op `https://wim1201.github.io/wielerbulletin/`.
6. **Op de iPhone**: open die link in Safari → Deel-knop → *Zet op beginscherm*.
7. **Claude-toegang tot de repo**: de geplande taak moet kunnen pushen. Controleer dat de Claude GitHub-app toegang heeft tot `wielerbulletin` (claude.ai → Instellingen → Connectors → GitHub). De taak meldt het als dat niet lukt.

## Kosten

Vijf minuten is ongeveer 4.000–4.500 tekens per dag, dus zo'n 130.000 tekens per maand. Controleer het tegoed van je ElevenLabs-abonnement; v4 verbruikt credits per teken.

## Lokaal testen zonder ElevenLabs

```bash
pip install -r scripts/requirements.txt   # plus ffmpeg
python scripts/build_episodes.py --episodes episodes --store store --fake-tts
```

## Bestanden

| Pad | Inhoud |
|---|---|
| `app/` | De PWA: `index.html`, `app.css`, `app.js`, `sw.js`, manifest en iconen |
| `episodes/` | Eén script per dag; `## `-koppen worden hoofdstukken, `### Visma \| Lease a Bike` wordt een subhoofdstuk |
| `scripts/build_episodes.py` | Tekst → audio → `feed.json` |
| `.github/workflows/publish.yml` | Bouwt en publiceert bij elke push |
