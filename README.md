# Workout Gate

Ogni **30 minuti di uso attivo** del PC, Workout Gate apre una schermata fullscreen
che si chiude solo dopo **10 squat verificati via webcam** (computer vision, in
locale). Poi azzera il timer e ricomincia. Gira in background, nella system tray.

Niente pulsante "ho fatto gli squat": la verifica avviene solo tramite il movimento
rilevato da MediaPipe. Niente lockout: in caso di problema tecnico il PC torna
subito utilizzabile (fail-open), e c'e' sempre un bypass d'emergenza.

---

## Requisiti

- Windows 11 (progettato e verificato qui; il core e' multipiattaforma).
- **Python 3.11, 3.12 o 3.13.** MediaPipe **non** supporta Python 3.14: serve un
  interprete 3.11-3.13. L'installer usa 3.12.
- Una webcam.
- Nessun privilegio amministrativo.

## Installazione

```powershell
# 1. (se manca) installa Python 3.12 per-utente
winget install --id Python.Python.3.12 --scope user

# 2. installa Workout Gate (crea venv, installa, diagnostica, autostart)
powershell -ExecutionPolicy Bypass -File installer\install.ps1
```

L'installer crea `.venv312`, installa il pacchetto, esegue `doctor` e registra
l'avvio automatico al login (shortcut in `shell:startup`, niente admin).

Disinstallazione:

```powershell
powershell -ExecutionPolicy Bypass -File installer\uninstall.ps1          # mantiene i dati
powershell -ExecutionPolicy Bypass -File installer\uninstall.ps1 -Purge   # cancella i dati (con conferma)
```

## Il comando per la prova fisica (serve la tua presenza)

Il conteggio reale degli squat e' l'unica parte che richiede una persona davanti
alla webcam. Per provarlo:

```powershell
# prova di inquadratura: scheletro live + checklist anche/ginocchia/caviglie
.venv312\Scripts\python -m workout_gate test-camera

# ciclo completo accelerato: il gate si apre dopo 30s di uso attivo invece di 30 min
.venv312\Scripts\python -m workout_gate run --work-interval-seconds 30
```

Posizionati in modo che anche, ginocchia e caviglie restino inquadrate anche in
fondo allo squat (di solito un paio di passi indietro dalla scrivania).

## Comandi

```text
workout-gate run [--work-interval-seconds N]   avvia (N = modalita' sviluppo)
workout-gate status                            stato dell'istanza attiva
workout-gate start | stop                      avvia in background / chiude
workout-gate pause 15m | 30m | 1h              pausa (la tray ha anche "fino al login")
workout-gate resume                            riprende
workout-gate workout-now                       apre subito il gate
workout-gate calibrate                         calibrazione soglie (webcam)
workout-gate test-camera                       prova webcam + inquadratura
workout-gate stats | history                   statistiche / storico
workout-gate config                            mostra la config effettiva
workout-gate doctor                            diagnostica ambiente
workout-gate install-autostart | remove-autostart
workout-gate reset-timer [--yes]               azzera il tempo accumulato (conferma)
```

Tutti i comandi sono anche nel menu della system tray.

## Come funziona

- **Timer a tick**: il tempo sale solo mentre sei attivo (input < 2 min di idle,
  workstation sbloccata, non in pausa). Non si sottraggono mai timestamp assoluti,
  quindi sleep, lock, cambio dell'orologio e spegnimento non falsano il conteggio.
  L'accumulato e' persistito su JSON e ripreso dopo il riavvio.
- **Riconoscimento squat**: macchina a stati esplicita
  `STANDING -> DESCENDING -> BOTTOM -> ASCENDING -> STANDING`, con isteresi e
  debounce. Una ripetizione conta solo a ciclo completo, con profondita' raggiunta,
  ritorno in piedi e durata realistica. Mezzi squat, rimbalzi e oscillazioni sulla
  soglia non contano; nessun doppio conteggio.
- **Due modalita' di rilevamento** (`vision.exercise_mode`):
  - `torso` (**default**): conta lo squat dal movimento verticale del busto/spalle.
    Funziona con una webcam che inquadra solo testa e spalle (tipico laptop), dove
    le gambe non sono mai in quadro. La baseline "in piedi" si auto-tara.
  - `knee`: angolo anca-ginocchio-caviglia. Piu' preciso ma richiede che tutto il
    corpo, gambe comprese, sia inquadrato (webcam bassa e arretrata).
- **Visione**: MediaPipe Tasks **PoseLandmarker** (modello `pose_landmarker_lite`
  bundlato nel pacchetto) + OpenCV per la cattura.
- **Gate**: finestra fullscreen topmost su tutti i monitor, "soft" (niente guerra
  di focus: e' un invito a muoverti, non un kiosk inviolabile). Intercetta ALT+F4 ed
  Esc nella propria finestra; con un bypass o un errore tecnico si chiude.
- **Widget desktop ON/OFF**: piccolo pannello con interruttore retro, **agganciato
  allo sfondo del desktop** (dietro le finestre, non appare nelle condivisioni
  schermo; `startup.widget_on_top: true` per tenerlo invece in primo piano).
  **OFF** spegne il counter (pausa indefinita) e chiude un gate eventualmente
  aperto, senza debito: utile prima di una riunione o presentazione. **ON**
  riaccende. Si nasconde/mostra dalla tray ("Mostra/Nascondi widget").

## Privacy

La webcam analizza il movimento **solo in locale e in tempo reale**. Nessun video,
immagine o frame viene registrato o salvato; i frame sono eliminati dopo
l'elaborazione. Nessuna rete, telemetria o analytics. Si salvano **solo numeri**
(squat completati, durate, streak, bypass, errori). Questi vincoli sono **forzati
nel codice** (`config.privacy`) e non attivabili da file o interfaccia.

## Sicurezza

Workout Gate non e' un dispositivo medico. Interrompi subito in caso di dolore,
vertigini o malessere e usa il bypass d'emergenza (tieni premuto 10s, scegli un
motivo: si registra solo categoria e orario, nessun debito).

## Fail-open

Webcam assente/occupata, MediaPipe non disponibile, errore interno: il gate mostra
un messaggio breve, rilascia la webcam, si chiude e ti ridà il PC. Mai un lockout,
mai un completamento simulato; riprova dopo 10 minuti di uso attivo.

## Sviluppo

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-tests.ps1   # ruff + mypy + pytest
.venv312\Scripts\python -m pytest                                # solo test
```

Il **core logico** (timer, geometria, macchina a stati, subject tracker, storage,
config, single instance) non importa MediaPipe/OpenCV/PySide6 ed e' testabile senza
webcam ne' GUI. Il counter e' verificato su **sequenze di landmark sintetiche**. Il
gate e' verificato end-to-end con un **engine finto** (thread, finestra,
completamento, cleanup) tramite la piattaforma Qt offscreen.

```text
src/workout_gate/
  config · storage · single_instance · active_time · idle_detector
  windows_session · scheduler · commands · tray · autostart · diagnostics
  app · cli · main
  gate/      controller · fullscreen · vision_worker · engine · emergency_bypass
  vision/    camera · pose_detector · squat_counter · squat_state · subject_tracker
             geometry · calibration · draw · preview · models/pose_landmarker_lite.task
  ui/        workout_window · settings_window · stats_window
tests/       17 file, copertura del core + integrazione gate
installer/   install.ps1 · uninstall.ps1
scripts/     run-tests.ps1 · camera_check.py
```

## Limitazioni residue (oneste)

- **Visione monoculare, single-person.** v1 usa `num_poses=1`: MediaPipe sceglie la
  posa piu' prominente. Una persona sullo sfondo che si muove molto puo' confondere
  il rilevamento; il subject tracker mitiga la continuita' ma non e' identificazione
  biometrica. Non c'e' garanzia assoluta anti-inganno.
- **Modalita' torso (default): sensibile, dipende dalla distanza.** Conta lo squat
  dal calo verticale delle spalle (default `vision.torso_min_drop` 0.07: basta
  scendere e risalire, non serve la profondita'). Alzalo se conta movimenti
  involontari, abbassalo se non conta da lontano (dove il movimento appare piu'
  piccolo). La baseline "in piedi" si auto-tara; la soglia no. **Il conteggio non
  si azzera mai durante una sessione**: uno squat sbagliato o un'uscita momentanea
  dall'inquadratura resettano solo la ripetizione in corso, non il totale.
- **Il gate e' user-space**, non un blocco di sicurezza: ALT+F4 e' intercettato nella
  finestra, ma Task Manager, logout, riavvio e terminazione del processo restano
  sempre possibili (per scelta: non si tolgono all'utente le vie d'uscita).
- **Esecuzione richiesta Python 3.11-3.13** (vincolo MediaPipe). Nessun `.exe`
  standalone in v1: si avvia con `pythonw -m workout_gate run` + shortcut Startup. Il
  packaging in eseguibile e' rimandato (rischio noto MediaPipe + PyInstaller).
- **Rilevamento lock/sleep** via polling (1 Hz) e heuristica `OpenInputDesktop`; lo
  sleep e' gestito dal clamp del gap nel timer, non da eventi in push.

## Licenza

MIT. Vedi `LICENSE`.
