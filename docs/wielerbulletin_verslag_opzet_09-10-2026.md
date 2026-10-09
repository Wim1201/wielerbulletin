# Wielerbulletin — verslag opzet

| | |
|---|---|
| Datum | 09-10-2026 |
| Versie | eerste opzet (sw-cache `wb-shell-v1`) |
| Omgeving | Claude-chat met cloud-werkruimte |
| Van / aan | Claude → Wim |
| Vervolg op | — |

## Vrijdagspecial toegevoegd (09-10-2026, 20:15)

- **Wat**: wekelijkse special over niet-professioneel wielrennen in NL en BE (jeugd, junioren, beloften en elite zonder contract, clubs, masters, vrouwen; weg, veld, MTB, baan, BMX, gravel; tot provinciaal niveau). Bestandsnaam `episodes/<datum>-vrijdagspecial.md`, front matter `kind: special`, `label: Vrijdagspecial`.
- **Geplande taak**: `trig_01Mnsx2eke7Rfd3u24VMrdgh`, vrijdag 07:25 Europe/Amsterdam, automatisch goedkeuren, pushmelding aan. Eerste run 16-10-2026.
- **Dagelijkse taak** (`trig_019VJgxZDmvSEiYWn5Ex2eTK`): prompt aangevuld met `git pull --rebase` vóór push, omdat beide taken op vrijdag naar main pushen.
- **Pijplijn**: afleveringen hebben een eigen id (bestandsnaam); specials blijven 56 dagen staan, dagelijkse 14. De run faalt als een aflevering van vandaag niet lukt; oude audio blijft staan als een her-render faalt.
- **App**: archief toont een geel label bij specials; de speler opent standaard het dagelijkse bulletin. Service-worker-cache naar `wb-shell-v2`.
- **Eerste special**: `episodes/2026-10-09-vrijdagspecial.md`, ca. 500 woorden.

### Bronnen voor de special: wat werkt en wat niet

| Bron | Stand 09-10-2026 |
|---|---|
| cyclingsite.be | Werkt; Belgische jeugd-, junioren-, nieuwelingen- en kermiskoersen. Data staan niet altijd bij de berichten. |
| veldritkrant.be | Werkt; veldritkalender en uitslagen. |
| sporza.be, wielerflits.nl, nos.nl | Werken; weinig nieuws onder nationaal niveau. |
| knwu.nl, dewielersite.net | Weigeren de ophaaltool (robots.txt). |
| cyclingvlaanderen.be | **Niet gebruiken**: stuurde door naar een onbekende reclamesite. |

**Vermoeden, niet vastgesteld**: Nederlands nieuws op club- en jeugdniveau zal mager blijven zolang KNWU en dewielersite niet leesbaar zijn. De eerste special heeft daardoor vrijwel alleen Belgische uitslagen.

## Stand 09-10-2026, 17:15: live

- **Eerste aflevering gepubliceerd** (run #4, groen). Duur 4:40, model `eleven_v4`, stem Emma (Calm, Clear and Confident, Standaard-Nederlands). App: https://wim1201.github.io/wielerbulletin/
- **Run #1 tot en met #3 gefaald**, opgelost:
  - #1: `apt-get install ffmpeg` duurde 15 min, daarna ontbraken de secrets nog. Workflow gebruikt nu `FedericoCarboni/setup-ffmpeg@v3` (6 s) en heeft `timeout-minutes: 20`.
  - #2: secrets nog niet ingesteld.
  - #3: API-sleutel miste het recht `text_to_speech`. Door Wim in ElevenLabs aangepast.
- **Diagnose**: fouten van het script verschijnen nu als annotatie bij de run, zodat ze zonder inloggen leesbaar zijn via de GitHub API.
- **Spreektempo**: v4 met Emma doet ca. 17 tekens per seconde; 4.300 tekens = 4:40 inclusief pauzes.
- **Credits**: ElevenLabs-tegoed op 09-10-2026 ca. 89.600. Bij ~5.000 tekens per dag is dat krap; maandtegoed nog te controleren.

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
| Pijplijn (`scripts/build_episodes.py`) | Getest met `--fake-tts`: 7 hoofdstukken, hoofdstuktijden, golfvorm, overslaan van bestaande afleveringen en opschonen na 14 dagen werken. Met de echte ElevenLabs-API gedraaid op 09-10-2026: 4:40, hoofdstuktijden correct. |
| Workflow (`.github/workflows/publish.yml`) | Draait; run #4 op 09-10-2026 groen. |
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
