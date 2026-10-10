# Wielerbulletin

Elke ochtend om acht uur vijf minuten wielernieuws, voorgelezen als zakelijk nieuwsbulletin. Een PWA in geel en zwart die je via Safari op je iPhone-beginscherm zet.

## Hoe het werkt

| Tijd | Wie | Wat |
|---|---|---|
| 07:45 (vrijdag ook 07:25) | Geplande Claude-taken | Zoeken het nieuws, schrijven `episodes/<datum>.md` (en op vrijdag `<datum>-vrijdagspecial.md`) en zetten het bestand in de map op Wims pc (`C:\Users\Wim\Documents\Wielerbulletin`, "Werk in een map"). Pc moet aanstaan met de Claude-app open. |
| 07:30–09:00, elke 5 min | Windows Taakplanner → `scripts/push_episodes.bat` | Commit en pusht nieuwe bestanden in `episodes/` (de geplande taak kan op de pc geen git uitvoeren). Logboek: `pc_push.log`. |
| reserve | GitHub Action `write.yml` | Schrijft hetzelfde via de Anthropic API. Schema staat uit; alleen handmatig te starten (vereist secret `ANTHROPIC_API_KEY`). |
| ± 07:50 | `publish.yml` (bij elke push, of aangeroepen door `write.yml`) | Spreekt elk hoofdstuk in met ElevenLabs (`eleven_v4`), voegt samen, berekent hoofdstuktijden en golfvorm, schrijft `feed.json` en publiceert naar GitHub Pages |
| 08:00 | De app | Haalt `feed.json` op en zet het nieuwe bulletin klaar |

De ElevenLabs- en Anthropic-sleutels staan alleen als secret in GitHub.

GitHub start geplande runs soms 5 tot 20 minuten later dan de cron-tijd. In de wintertijd draait `write.yml` een uur eerder (06:35), omdat de cron-tijd in UTC staat.

Zelf een script schrijven of corrigeren kan altijd: zet het bestand in `episodes/` en push. Bestaat het bestand van vandaag al, dan slaat `write.yml` het over. De audio staat op de aparte branch `audio` (alleen de laatste 14 dagen, telkens overschreven), zodat de repository niet dagelijks megabytes groeit.

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

## Pc-push instellen (eenmalig)

Open de **Opdrachtprompt** (niet Git Bash) en voer uit:

```
schtasks /Create /TN "Wielerbulletin push" /TR "C:\Users\Wim\Documents\Wielerbulletin\scripts\push_episodes.bat" /SC DAILY /ST 07:30 /RI 5 /DU 01:30 /F
```

Testen: `schtasks /Run /TN "Wielerbulletin push"` en daarna `pc_push.log` bekijken (staat er niets nieuws, dan blijft het logboek leeg).

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
| `episodes/` | Eén script per dag (`<datum>.md`) plus op vrijdag de special (`<datum>-vrijdagspecial.md`); `## `-koppen worden hoofdstukken, `### `-koppen subhoofdstukken |
| `scripts/build_episodes.py` | Tekst → audio → `feed.json` |
| `scripts/write_episode.py` | Nieuws zoeken en script schrijven via de Anthropic API; controleert het formaat en probeert één keer opnieuw |
| `prompts/` | De opdracht voor het dagelijkse bulletin en de vrijdagspecial; hier pas je inhoud en bronnen aan |
| `.github/workflows/write.yml` | Schrijft elke ochtend het script en roept daarna `publish.yml` aan; handmatig te starten met keuze dagelijks, vrijdagspecial, beide of test |
| `.github/workflows/publish.yml` | Bouwt en publiceert bij elke push |
