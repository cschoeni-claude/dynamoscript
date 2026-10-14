# Index (Änderung) auf Plänen ergänzen
# - trägt die im Auswahlfenster angehakten Änderungen unter "Änderungen auf Plan" ein
# - schreibt das Datum in den Planparameter "Datum"
# - zählt in der Plannummer den Index alphabetisch weiter und setzt den Planstatus
# - schreibt den neuen Index zusätzlich in den Planparameter "(6) Index"
# Die Pläne müssen dafür nicht geöffnet werden.

import clr
clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import *
clr.AddReference('RevitServices')
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager
from System.Collections.Generic import List
clr.AddReference('System.Windows.Forms  ')
clr.AddReference('System.Drawing')
import System.Windows.Forms as WF
import System.Drawing as SD

doc   = DocumentManager.Instance.CurrentDBDocument
uidoc = DocumentManager.Instance.CurrentUIDocument

nr_filter     = (IN[0] or "").strip()                  # Plannummer beginnt mit, leer = alle
beschreibung  = (IN[1] or "").strip()                  # leer = Auswahlfenster, sonst Beschreibung(en) mit ";" getrennt
ausfuehren    = bool(IN[2])                            # False = nur prüfen
datum_setzen  = bool(IN[3])                            # Parameter "Datum" aktualisieren
datum         = (IN[4] or "").strip()                  # leer = heute
nr_anpassen   = bool(IN[5])                            # Plannummer anpassen
status_filter = str(IN[6] or "Alle").strip()           # V / F / B / Alle
status_neu    = str(IN[7] or "unverändert").strip()    # B / F / V / unverändert

# Plannummer: Teile getrennt durch "_", z. B. ARC_GR_DA_005_C_B
# vorletzter Teil = Index, letzter Teil = Planstatus
TRENNER      = "_"
PARAM_DATUM  = "Datum"
PARAM_INDEX  = "(6) Index"
DATUMSFORMAT = "%d.%m.%Y"   # z. B. 03.06.2026

# Planstatus darf nur vorwärts gehen: V -> F -> B (nie zurück).
# Wäre es ein Rückschritt, ist der Plan gesperrt und bleibt komplett unverändert.
# Ebenso gesperrt: Pläne, auf denen eine gewählte Änderung schon eingetragen ist.
STATUS_RANG = {"V": 0, "F": 1, "B": 2}

if status_filter.lower() == "alle":
    status_filter = ""
status_eingabe = status_neu   # für das Protokoll
if status_neu.lower() == "unverändert":
    status_neu = ""
status_neu = status_neu.upper()

if not datum:
    from datetime import date
    datum = date.today().strftime(DATUMSFORMAT)


def naechster_index(index):
    # "-" oder leer -> A, C -> D, Z -> AA, AZ -> BA
    index = index.strip().upper()
    if index in ("", "-"):
        return "A"
    if not index.isalpha():
        raise ValueError("Index '{}' ist kein Buchstabe".format(index))
    zeichen = list(index)
    pos = len(zeichen) - 1
    while pos >= 0:
        if zeichen[pos] != "Z":
            zeichen[pos] = chr(ord(zeichen[pos]) + 1)
            return "".join(zeichen)
        zeichen[pos] = "A"
        pos -= 1
    return "A" + "".join(zeichen)


def rev_text(r):
    return "Seq. {} - {}   ({})".format(r.SequenceNumber, r.Description,
                                        r.RevisionDate or "-")


def auswahlfenster(revs):
    # Fenster mit Häkchen-Liste aller Änderungen; neueste ist vorausgewählt.
    # Rückgabe: Liste der angehakten Änderungen, None bei Abbrechen.
    form = WF.Form()
    form.Text = "Änderungen auf Plänen ergänzen"
    form.Size = SD.Size(560, 480)
    form.StartPosition = WF.FormStartPosition.CenterScreen
    form.MinimizeBox = False
    form.MaximizeBox = False
    form.TopMost = True

    hinweis = WF.Label()
    hinweis.Text = "Welche Änderungen sollen auf den Plänen ergänzt werden?"
    hinweis.Dock = WF.DockStyle.Top
    hinweis.Height = 32
    hinweis.Padding = WF.Padding(8, 10, 8, 0)

    liste = WF.CheckedListBox()
    liste.Dock = WF.DockStyle.Fill
    liste.CheckOnClick = True
    liste.IntegralHeight = False
    for i, r in enumerate(revs):
        liste.Items.Add(rev_text(r), i == len(revs) - 1)

    knoepfe = WF.FlowLayoutPanel()
    knoepfe.Dock = WF.DockStyle.Bottom
    knoepfe.Height = 44
    knoepfe.FlowDirection = WF.FlowDirection.RightToLeft
    knoepfe.Padding = WF.Padding(6)

    abbrechen = WF.Button()
    abbrechen.Text = "Abbrechen"
    abbrechen.Size = SD.Size(95, 28)
    abbrechen.DialogResult = WF.DialogResult.Cancel
    ok = WF.Button()
    ok.Text = "OK"
    ok.Size = SD.Size(95, 28)
    ok.DialogResult = WF.DialogResult.OK
    knoepfe.Controls.Add(abbrechen)
    knoepfe.Controls.Add(ok)

    # Reihenfolge wichtig: Fill zuerst, dann Top/Bottom
    form.Controls.Add(liste)
    form.Controls.Add(hinweis)
    form.Controls.Add(knoepfe)
    form.AcceptButton = ok
    form.CancelButton = abbrechen

    if form.ShowDialog() != WF.DialogResult.OK:
        return None
    return [revs[i] for i in liste.CheckedIndices]


protokoll = []

# --- Änderungen bestimmen: per Beschreibung oder über das Auswahlfenster ---
alle_revs = sorted(FilteredElementCollector(doc).OfClass(Revision),
                   key=lambda r: r.SequenceNumber)

fehlermeldung = None
revs = []
if status_neu not in ("", "V", "F", "B"):
    fehlermeldung = "Ungültiger Planstatus '{}' – erlaubt: unverändert, V, F, B".format(status_eingabe)
elif not alle_revs:
    fehlermeldung = "Im Projekt gibt es keine Änderungen."
elif beschreibung:
    for b in [x.strip() for x in beschreibung.split(";") if x.strip()]:
        treffer = [r for r in alle_revs if r.Description.strip() == b]
        if not treffer:
            fehlermeldung = "Keine Änderung mit Beschreibung '{}' gefunden.".format(b)
            break
        revs.append(treffer[0])
else:
    revs = auswahlfenster(alle_revs)
    if revs is None:
        fehlermeldung = "Abgebrochen – es wurde nichts geändert."
    elif not revs:
        fehlermeldung = "Keine Änderung angehakt – es wurde nichts geändert."

if fehlermeldung:
    OUT = [fehlermeldung]
else:
    # --- Pläne bestimmen: markierte im Projektbrowser, sonst Filter ---
    markiert = [doc.GetElement(i) for i in uidoc.Selection.GetElementIds()]
    plaene = [e for e in markiert if isinstance(e, ViewSheet)]
    quelle = "Auswahl im Projektbrowser"

    if not plaene:
        plaene = [s for s in FilteredElementCollector(doc).OfClass(ViewSheet)
                  if s.SheetNumber.startswith(nr_filter)]
        quelle = "Filter '{}'".format(nr_filter) if nr_filter else "alle Pläne"

    plaene = [s for s in plaene if not s.IsPlaceholder]

    # --- Filter auf Planstatus (letzte Stelle der Plannummer) ---
    if status_filter:
        plaene = [s for s in plaene
                  if s.SheetNumber.split(TRENNER)[-1] == status_filter]
        quelle += ", Status " + status_filter

    plaene.sort(key=lambda s: s.SheetNumber)

    if ausfuehren:
        TransactionManager.Instance.EnsureInTransaction(doc)

    gesperrt_anzahl = 0

    for plan in plaene:
        name = plan.SheetNumber

        # --- SPERRE: Status auf dem Plan ist schon weiter als der gewählte ---
        # (Reihenfolge V -> F -> B) -> Plan bleibt komplett unverändert
        status_alt = name.split(TRENNER)[-1].upper()
        if status_neu and STATUS_RANG.get(status_alt, -1) > STATUS_RANG[status_neu]:
            gesperrt_anzahl += 1
            protokoll.append("{}: GESPERRT – Status {} ist weiter als {}, Plan bleibt unverändert".format(
                name, status_alt, status_neu))
            continue

        # --- SPERRE: gewählte Änderung ist auf dem Plan schon eingetragen ---
        # (auch über Änderungswolken) -> Plan bleibt komplett unverändert,
        # damit der Index nicht doppelt weitergezählt wird
        auf_plan = plan.GetAllRevisionIds()
        schon_da = [r.Description for r in revs if auf_plan.Contains(r.Id)]
        if schon_da:
            gesperrt_anzahl += 1
            protokoll.append("{}: GESPERRT – Änderung bereits eingetragen ({}), Plan bleibt unverändert".format(
                name, ", ".join(schon_da)))
            continue

        ids = List[ElementId](plan.GetAdditionalRevisionIds())

        # --- Gewählte Änderungen unter "Änderungen auf Plan" ---
        vorhanden = [r.Description for r in revs if ids.Contains(r.Id)]
        fehlend   = [r for r in revs if not ids.Contains(r.Id)]
        teiltexte = []
        if vorhanden:
            teiltexte.append("bereits vorhanden: " + ", ".join(vorhanden))

        # Index wird weitergezählt, sobald mindestens eine Änderung angehakt ist
        # (nur nicht, wenn das Eintragen fehlschlägt)
        index_weiterzaehlen = bool(revs)
        if fehlend and not ausfuehren:
            teiltexte.append("würde ergänzt: " + ", ".join(r.Description for r in fehlend))
        elif fehlend:
            try:
                for r in fehlend:
                    ids.Add(r.Id)
                plan.SetAdditionalRevisionIds(ids)
                teiltexte.append("ergänzt: " + ", ".join(r.Description for r in fehlend))
            except Exception as e:
                teiltexte.append("FEHLER Änderungen: {}".format(e))
                index_weiterzaehlen = False
        text = "Änderungen " + "; ".join(teiltexte)

        # --- Parameter "Datum" ---
        if datum_setzen:
            p = plan.LookupParameter(PARAM_DATUM)
            alt = p.AsString() if p else None
            if p is None:
                text += " | FEHLER Datum: Parameter '{}' fehlt".format(PARAM_DATUM)
            elif p.IsReadOnly or p.StorageType != StorageType.String:
                text += " | FEHLER Datum: Parameter nicht als Text beschreibbar"
            elif alt == datum:
                text += " | Datum bereits " + datum
            elif not ausfuehren:
                text += " | Datum würde {} -> {}".format(alt or "(leer)", datum)
            else:
                try:
                    p.Set(datum)
                    text += " | Datum {} -> {}".format(alt or "(leer)", datum)
                except Exception as e:
                    text += " | FEHLER Datum: {}".format(e)

        # --- Plannummer: Index weiterzählen, Planstatus setzen ---
        # Der Index wird bei jedem Lauf mit angehakter Änderung um einen
        # Buchstaben weitergezählt (gesperrte Pläne wurden oben übersprungen).
        if nr_anpassen:
            teile = plan.SheetNumber.split(TRENNER)
            index_neu = None
            if len(teile) < 3:
                text += " | FEHLER Nr: Format passt nicht"
            else:
                try:
                    if index_weiterzaehlen:
                        index_neu = naechster_index(teile[-2])
                        teile[-2] = index_neu
                    else:
                        text += " | Index in Nr unverändert (Fehler beim Eintragen der Änderungen)"
                    if status_neu:
                        teile[-1] = status_neu
                    neu = TRENNER.join(teile)
                    if neu == plan.SheetNumber:
                        text += " | Nr unverändert"
                    elif not ausfuehren:
                        text += " | Nr würde -> " + neu
                    else:
                        plan.SheetNumber = neu
                        text += " | Nr -> " + neu
                except Exception as e:
                    index_neu = None
                    text += " | FEHLER Nr: {}".format(e)

                # --- Parameter "(6) Index": gleicher Index wie in der Plannummer ---
                if index_neu:
                    p = plan.LookupParameter(PARAM_INDEX)
                    if p is None:
                        text += " | FEHLER Index-Feld: Parameter '{}' fehlt".format(PARAM_INDEX)
                    elif p.IsReadOnly or p.StorageType != StorageType.String:
                        text += " | FEHLER Index-Feld: nicht als Text beschreibbar"
                    elif not ausfuehren:
                        text += " | Index-Feld würde -> " + index_neu
                    else:
                        try:
                            p.Set(index_neu)
                            text += " | Index-Feld -> " + index_neu
                        except Exception as e:
                            text += " | FEHLER Index-Feld: {}".format(e)

        protokoll.append("{}: {}".format(name, text))

    if ausfuehren:
        TransactionManager.Instance.TransactionTaskDone()

    modus = "AUSGEFÜHRT" if ausfuehren else "NUR PRÜFUNG"
    OUT = ["{} | Änderungen: {}".format(modus, ", ".join(r.Description for r in revs)),
           "Datum: {}".format(datum if datum_setzen else "unverändert"),
           "Neuer Planstatus: {} (Eingabe: '{}')".format(status_neu or "unverändert", status_eingabe),
           "Pläne ({}): {}, davon gesperrt: {}".format(quelle, len(plaene), gesperrt_anzahl)] + protokoll
