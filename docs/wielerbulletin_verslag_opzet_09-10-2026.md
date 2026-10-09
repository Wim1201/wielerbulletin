# Wielerbulletin — verslag opzet

| | |
|---|---|
| Datum | 09-10-2026 |
| Versie | eerste opzet (sw-cache `wb-shell-v1`) |
| Omgeving | Claude-chat met cloud-werkruimte |
| Van / aan | Claude → Wim |
| Vervolg op | — |

## Correcties en wijzigingen (09-10-2026, 15:35)

- **Inhoud gewijzigd op verzoek van Wim**: Visma | Lease a Bike is de rode draad. Per onderwerp volgt een subkop `### Visma | Lease a Bike` met selectie, opstelling en teamnieuws. Elke koers van vandaag of morgen krijgt starttijd, parcours, historie, favorieten en tv-uitzending.
- **Pijplijn**: `###`-koppen worden subhoofdstukken met een eigen starttijd (`level: 3` in `feed.json`); de pauzeduur wordt nu gemeten in plaats van aangenomen.
- **App**: subhoofdstukken staan in de lijst met een geel honingraatje en krijgen een kortere streep op de golfvorm.
- **Geplande taak**: prompt van `trig_019VJgxZDmvSEiYWn5Ex2eTK` vervangen; doel 700–800 woorden, op grote koersdagen tot 850.
- **Aflevering 09-10-2026 herschreven** in het nieuwe format (ca. 685 woorden). Visma-selectie Lombardije uit de startlijst van cyclinguptodate.com (08-10-2026); een opstelling op teamvismaleaseabike.com bleek van een eerder jaar en is niet gebruikt.

## Wat is gemaakt

| Onderdeel | Stand |
|---|---|
| PWA (`app/`) | Gebouwd en getest in headless Chromium met testaudio (390 × 844). Afspelen, hoofdstukken, archief, snelheid, ±15 s werken. Op een echte iPhone nog niet getest. |
| Pijplijn (`scripts/build_episodes.py`) | Getest met `--fake-tts`: 7 hoofdstukken, hoofdstuktijden, golfvorm, overslaan van bestaande afleveringen en opschonen na 14 dagen werken. Met de echte ElevenLabs-API nog niet gedraaid. |
| Workflow (`.github/workflows/publish.yml`) | Geschreven, nog niet gedraaid (repo bestaat nog niet). |
| Eerste aflevering | `episodes/2026-10-09.md`, ca. 685 woorden, 7 hoofdstukken en 2 Visma-subhoofdstukken. |
| Geplande taak | `trig_019VJgxZDmvSEiYWn5Ex2eTK`, dagelijks 07:45 Europe/Amsterdam, automatisch goedkeuren, pushmelding aan. Eerste run 10-10-2026 07:45. |

## Ontwerpkeuzes

- **PWA in plaats van native**: Wim heeft geen Mac; gekozen op 09-10-2026.
- **ElevenLabs in GitHub Actions, niet in de Claude-taak**: de Claude-werkruimte kan api.elevenlabs.io niet bereiken, en zo blijft de API-sleutel buiten Claude.
- **Per hoofdstuk inspreken**: levert exacte hoofdstuktijden voor de app. Nadeel: intonatie loopt tussen hoofdstukken niet door; de pauze van 0,8 s maakt dat natuurlijk.
- **Fallback**: weigert het text-to-speech-endpoint `eleven_v4`, dan probeert het script het text-to-dialogue-endpoint met één stem.
- **Audio-branch geforceerd overschreven**: houdt de repo klein.
- **Kleuren**: teamgeel `#FFDD00`, honing `#D9B500`, zwart; fijne diagonale arcering als verwijzing naar het bijenhaarpatroon in het 2026-tenue. Geen logo's of namen van de ploeg in de app.

## Te testen door Wim

1. Eerste workflowrun: komt er audio uit, en klinkt de gekozen stem zakelijk genoeg? Zo niet: andere `ELEVENLABS_VOICE_ID`, of `stability` in `tts_elevenlabs()` aanpassen.
2. Duur: vermoedens over spreektempo zijn gebaseerd op 150 woorden per minuut; de werkelijke duur van v4 kan afwijken. Bijstellen via het woordenaantal in de taakprompt.
3. Afspelen op het vergrendelscherm en met AirPods (Media Session).

## Buiten dit verslag

- **Repo bestaat nog niet**: `Wim1201/wielerbulletin` moet Wim aanmaken vóór 10-10-2026 07:45, anders faalt de eerste geplande run.
- **Secrets**: `ELEVENLABS_API_KEY` en `ELEVENLABS_VOICE_ID` instellen; Pages op *GitHub Actions* zetten.
- **Push door Claude**: anders dan bij de andere repo's pusht hier de geplande taak zelf, maar alleen `episodes/<datum>.md`. Bewust zo, want het hele punt is dat het zonder handwerk loopt.
- **Bronnen eerste aflevering**: Sporza en WielerFlits van 09-10-2026. Twee items (Del Toro knie, Bernal) staan er voorzichtig in, omdat de bronnen onvolledig of tegenstrijdig waren.
