# Workout Gate — Brief operativo v2 (a milestone)

> Data: 2026-06-16. Riscrittura del capitolato originale (33 sezioni) in forma a milestone, dopo le 7 decisioni prese con Nik. Self-contained: una sessione di build può eseguirlo senza il capitolato originale.

---

## 0. Cosa è e per chi

Tool **personale** per Nik, una singola macchina **Windows 11**. Ogni 30 minuti di uso *attivo* del PC si apre un gate fullscreen che si chiude solo dopo **10 squat verificati via webcam**. Non è un prodotto da distribuire: deve funzionare sulla scrivania di Nik. Si ottimizza per "funziona per me questa settimana", non per "shippable".

---

## 1. Le 7 decisioni che governano questo brief

1. **Esercizio = squat.** Nik si allontana dalla cam quel tanto che basta perché tutto il corpo sia inquadrato (confermato in M0). **Requisito UX forte: durante l'esercizio Nik si vede ripreso live** (mirror preview + scheletro MediaPipe sovrapposto). È parte del valore, non opzionale. Mostrarsi a schermo e non salvare nulla sono compatibili: il frame si mostra e si scarta.
2. **Build a milestone con checkpoint**, mai big-bang. Dopo ogni milestone: stop e dichiara *cosa gira davvero / cosa è testato / cosa è stub / l'ignoto più rischioso rimasto*.
3. **Niente exe/installer in v1.** Avvio con `pythonw` + shortcut in `shell:startup`. Zero privilegi admin, zero PyInstaller. Il packaging si valuta solo dopo che il nucleo gira.
4. **Counter verificabile su landmark sintetici** + una **dev-mode** che registra SOLO coordinate numeriche di landmark per tarare le soglie (mai immagini, mai attiva in produzione).
5. **Gate "soft":** finestra topmost borderless per monitor. Niente guerra di focus. L'enforcement è il patto con te stesso. Con alt-tab si può uscire (restano fail-open + bypass).
6. **Timer a tick:** accumula tempo mentre sei attivo, non sottrarre timestamp. API Windows: `GetLastInputInfo` (idle), `WM_WTSSESSION_CHANGE` (lock/unlock), `WM_POWERBROADCAST` (sleep/resume).
7. **v1 = spina dorsale.** JSON al posto di SQLite+migrazioni finché non serve davvero.

---

## 2. Invarianti non negoziabili (dal capitolato originale, tenuti interi)

**Privacy forzata nel codice** — `save_video / save_frames / save_images / network_access / telemetry / analytics = false`, non attivabili da UI. Frame eliminati dalla memoria appena elaborati. Si persiste solo dato numerico/operativo. Banner sempre visibile nel gate:
> La webcam verifica il movimento localmente. Nessun video, immagine o fotogramma viene registrato o salvato.

**Fail-open tecnico** — qualsiasi errore (cam assente/occupata/disconnessa, permessi negati, MediaPipe/OpenCV ko, modello in errore, UI crash, monitor non copribile, config invalida): mostra messaggio breve → logga → rilascia cam e risorse → chiudi il gate → ridai il PC → **non simulare squat, non creare debito** → riprova dopo 10 min di uso attivo. Sempre `try/finally`, cleanup idempotente, rilascio cam garantito.

**Sicurezza fisica** — messaggio sempre visibile:
> Interrompi immediatamente in caso di dolore, vertigini, perdita di equilibrio o malessere. Workout Gate non è un dispositivo medico.

Niente diagnosi, niente correzioni mediche. Se l'utente dichiara dolore/impossibilità, non imporre l'esercizio.

**Bypass d'emergenza** — sempre disponibile, mai accidentale: tieni premuto 10s con countdown → scegli categoria (problema fisico / dolore / vertigini / webcam ko / urgenza / ambiente non adatto / altro) → logga solo categoria + timestamp → chiudi senza debito e senza segnare il workout come fatto → riprova dopo 10 min attivi.

**State machine squat** — `WAITING_FOR_BODY → STANDING → DESCENDING → BOTTOM → ASCENDING → STANDING`. Conta solo il ciclo completo. Isteresi + debounce anti-doppio-conteggio. Soglie iniziali (calibrabili): `min_landmark_visibility 0.65`, `standing_knee_angle 160°`, `bottom_knee_angle 100°`, `cycle 0.8–8.0s`, `standing_stability 0.4s`, `hysteresis 8°`. Non contare: mezzi squat, piegamenti del busto, rimbalzi, oscillazioni sulla soglia, movimenti troppo rapidi, soggetto sullo sfondo, corpo parzialmente fuori inquadratura.

---

## 3. Milestone

### M0 — Spike di de-risking (prima di scrivere il prodotto)
Due verifiche che possono affossare il progetto.
- **Ambiente:** su questo Win11, in un venv Python 3.11, `pip install` di mediapipe + opencv-python + PySide6 va a buon fine, e **MediaPipe Tasks PoseLandmarker** carica e gira su un frame webcam? Se mediapipe non installa/gira pulito, lo sappiamo ora.
- **Framing fisico** (richiede Nik, 5 min): script che mostra webcam live + scheletro. Nik si posiziona, fa 2-3 squat, si verifica che **anche, ginocchia e caviglie restino visibili per tutto il ROM** (incluso BOTTOM). Si conferma distanza e che lo squat sia l'esercizio giusto.
- **DoD:** screenshot dello scheletro su Nik in BOTTOM con landmark gamba visibili + log delle versioni installate.

### M1 — Loop end-to-end con gate finto (nessuna CV)
- **Timer active-time a tick:** sale solo se uso attivo (input < 120s di idle via `GetLastInputInfo`), si ferma su lock/sleep (session/power events), persiste ogni 15s su JSON, riparte dal valore salvato dopo riavvio (mai conteggia tempo a PC spento).
- **Tray:** stato (attivo/pausa) + tempo rimanente + menu minimo (workout ora, pausa 15/30/60m, riprendi, esci).
- **Single instance.**
- **Gate fullscreen topmost** su tutti i monitor con placeholder "premi SPAZIO per simulare 10 squat" → chiude, azzera il timer, riparte solo a gate chiuso.
- **Dev fast-interval:** `--work-interval-seconds 30` per testare senza aspettare 30 min (solo CLI/dev, non scrive in config permanente, loggato).
- **DoD eseguibile da Nik senza webcam:** parte, conta tempo solo se attivo, ignora idle/lock, all'intervallo apre il gate, lo chiudo, riparte. Test automatici sul timer (tick, idle escluso, lock escluso, persistenza, no-tempo-a-PC-spento, reset post-workout, nuovo ciclo).

### M2 — Counter squat verificabile (nessuna webcam)
- Geometria angoli (anca-ginocchio-caviglia + angolo ginocchio), state machine esplicita, isteresi, debounce, durata ciclo realistica, ROM minima, stabilità iniziale, lato dx/sx quando visibili.
- Subject tracking: scegli soggetto principale (più grande/centrale), ignora persone sullo sfondo, reset + ri-stabilizzazione se il soggetto sparisce o cambia durante una rep.
- **DoD:** test su **sequenze di landmark sintetiche** (nessun umano, nessun video): "10 squat puliti" → 10; "10 mezzi squat" → 0; "rimbalzi sulla soglia" → 0; "troppo rapido / troppo lento" → scartati; "un movimento" → mai 2; "soggetto che sparisce/cambia" → reset corretto. Tutti verdi.

### M3 — MediaPipe live + gate vero (richiede Nik fisico per l'ultima verifica)
- `camera.py` (context manager, rilascio garantito in `finally`), `pose_detector` (PoseLandmarker), `subject_tracker`.
- **Overlay live = il self-view che Nik vuole:** feed webcam + scheletro + angolo ginocchio + fase corrente + contatore grande `N / 10` + confidenza + indicazione distanza + landmark mancanti.
- Feedback dinamici: avvicinati/allontanati, corpo non visibile, inquadra tutto il corpo, posizione rilevata, scendi ancora, profondità raggiunta, risali, estendi le gambe, squat valido, movimento incompleto/troppo rapido, 10/10.
- **Calibrazione prima esecuzione:** informativa privacy + consenso uso locale cam, scelta webcam, guida al posizionamento, verifica corpo intero visibile, taratura standing/profondità, verifica che 1 squat valido venga riconosciuto, salva SOLO soglie numeriche, elimina subito i frame.
- **Dev-mode opzionale** (off di default, mai in produzione): registra SOLO coordinate landmark in un file locale taggato per replay/tuning soglie.
- **DoD (un solo comando per Nik):** fa 10 squat reali → 9 validi non chiudono, il 10° sì → gate si chiude → cam rilasciata → timer riparte. Mezzi squat e rimbalzi non contano.

### M4 — Robustezza e rifiniture (solo dopo che M3 gira)
- Fail-open su tutti i percorsi d'errore; bypass d'emergenza completo; pause (15/30/60m + custom + fino al prossimo login); autostart via shortcut in `shell:startup`; statistiche minime (squat totali, sessioni, streak) su JSON.
- Eventuale packaging exe SOLO se serve davvero distribuirlo. Si valuta allora (rischio mediapipe+PyInstaller noto).

---

## 4. Scope v1 vs rimandato

**v1 (spina dorsale):** timer tick + tray + gate soft + counter affidabile + self-view live + calibrazione + fail-open + bypass + pause + autostart shortcut + dev fast-interval. Storage = un file JSON.

**Rimandato:** exe/installer, macOS/Linux, SQLite + migrazioni + foreign key, set completo di 8 sottocomandi CLI, streak/record elaborati, diagnostica estesa, multi-monitor con recupero focus.

---

## 5. Stack

Python 3.11 · PySide6 (UI / tray / multi-monitor) · MediaPipe Tasks PoseLandmarker · OpenCV (acquisizione) · JSON (persistenza v1) · pywin32 / ctypes (idle / session / power) · pytest + Ruff. **Niente PyInstaller in v1.**

---

## 6. Come si lancia (v1)

- Sviluppo veloce: `python -m workout_gate run --work-interval-seconds 30`
- Normale: shortcut a `pythonw -m workout_gate run` in `shell:startup`
- Test: `pytest`
- Calibrazione: `python -m workout_gate calibrate`
- Test webcam: `python -m workout_gate test-camera`

---

## 7. Regole di metodo per l'agent che costruisce

Una milestone per volta, fermati al checkpoint. Niente stub spacciati per fatti: se è stub, dillo. Niente `TODO` nelle funzioni principali. "Eseguito e verificato" significa: per il **counter** = test sintetici verdi; per il **live** = comando pronto per Nik. Cleanup idempotente, cam sempre rilasciata in `finally`. Separa CV / UI / scheduler / storage: niente logica di conteggio nella UI, niente logica di timer nella tray.
