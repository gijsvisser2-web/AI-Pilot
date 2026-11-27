"""Kickoff-route AI-pilot: van resultaat naar taak.

Alle teksten, prompts en codewoorden staan in inhoud.yaml (of inhoud_<pilot>.yaml).
Kies een andere pilot met ?pilot=<naam> achter de link, bijvoorbeeld ?pilot=hr.
De app slaat niets op. Invoer blijft alleen in de sessie van de deelnemer.
"""
import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yaml
from fpdf import FPDF

MAP = Path(__file__).parent
EXTERN_STANDAARD = "een externe applicatie"
TRAINER_STANDAARD = "Gijs"


# ---------- inhoud laden ----------
def kies_bestand():
    """inhoud_<pilot>.yaml als ?pilot=<pilot> in de link staat en het bestand bestaat, anders inhoud.yaml."""
    try:
        pilot = str(st.query_params.get("pilot", ""))
    except Exception:
        pilot = ""
    pilot = re.sub(r"[^a-z0-9_]", "", pilot.lower())
    bestand = MAP / f"inhoud_{pilot}.yaml"
    return bestand if pilot and bestand.exists() else MAP / "inhoud.yaml"


def vervang(waarde, vast):
    """Vult {extern} en {dataregel} overal in de inhoud in."""
    if isinstance(waarde, str):
        for naam, tekst in vast.items():
            waarde = waarde.replace("{" + naam + "}", tekst)
        return waarde
    if isinstance(waarde, list):
        return [vervang(w, vast) for w in waarde]
    if isinstance(waarde, dict):
        return {k: vervang(w, vast) for k, w in waarde.items()}
    return waarde


def laad():
    ruw = yaml.safe_load(kies_bestand().read_text(encoding="utf-8"))
    extern = (ruw.get("extern") or "").strip() or EXTERN_STANDAARD
    dataregel = (ruw.get("dataregel") or "").replace("{extern}", extern)
    trainer = (ruw.get("trainer") or "").strip() or TRAINER_STANDAARD
    return vervang(ruw, {"dataregel": dataregel, "extern": extern, "trainer": trainer}), extern, trainer


C, EXTERN, TRAINER = laad()
CODES = C.get("codewoorden") or {}  # leeg: geen codewoorden, deelnemers gaan zelf verder
S = C["stappen"]

STAPPEN = [
    "Start",
    "1. Je resultaat",
    "2. Copilot interviewt je",
    "3. Check en kies",
    "4. Je eerste resultaat",
    "5. Je plan",
]
LAATSTE = len(STAPPEN) - 1
SLOT_VANAF = 4  # vanaf deze stap is codewoord 2 nodig

st.set_page_config(page_title=C["titel"], page_icon="📦", layout="centered")
ss = st.session_state
ss.setdefault("stap", 0)
ss.setdefault("code1", False)
ss.setdefault("code2", False)


# ---------- hulpfuncties ----------
def script(html):
    """Voert een stukje JavaScript uit. Nieuwe Streamlit: st.iframe. Oude Streamlit: components.html."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=1)
    else:
        components.html(html, height=0)


def bewaar_tekst(label, k, area=False, **kw):
    """Tekstveld waarvan de waarde blijft bestaan als je naar een andere stap gaat.
    Tekstvakken groeien mee met de tekst."""
    ss.setdefault(k, kw.pop("standaard", ""))
    if area:
        kw.setdefault("height", "content")
        ss[k] = st.text_area(label, value=ss[k], key="w_" + k, **kw)
    else:
        ss[k] = st.text_input(label, value=ss[k], key="w_" + k, **kw)
    return ss[k].strip()


def bewaar_vinkje(label, k):
    ss.setdefault(k, False)
    ss[k] = st.checkbox(label, value=ss[k], key="w_" + k)
    return ss[k]


def bewaar_keuze(label, opties, k, horizontal=False):
    ss.setdefault(k, None)
    index = opties.index(ss[k]) if ss[k] in opties else None
    ss[k] = st.radio(label, opties, index=index, key="w_" + k, horizontal=horizontal)
    return ss[k]


def vul_in(tekst, **waarden):
    waarden.setdefault("functie", ss.get("functie", ""))
    waarden.setdefault("afdeling", ss.get("afdeling", ""))
    for naam, waarde in waarden.items():
        tekst = tekst.replace("{" + naam + "}", waarde or f"[{naam}]")
    return tekst


def is_nummer(tekst):
    """True als de stap alleen een nummer is, zoals '2', 'Stap 2' of 'stap 1, 4 en 7'."""
    return bool(re.fullmatch(r"(stap\s*)?[\d\s,.&+\-]*(en\s*[\d\s,.]*)*", tekst.strip().lower())) and any(c.isdigit() for c in tekst)


def regels_schoon(tekst):
    """Regels zonder restjes die uit Copilot zijn meegekopieerd."""
    regels = []
    for r in tekst.splitlines():
        s = r.strip()
        if not s or re.fullmatch(r"\+\d+", s) or s == "Bronnen" or s.startswith("Geredeneerd voor"):
            continue
        regels.append(r.rstrip())
    return regels


def schoon(tekst):
    return "\n".join(r.replace("\t", "  |  ") for r in regels_schoon(tekst)).strip()


def lees_tabel(tekst):
    """Maakt van geplakte tekst uit Copilot een tabel (lijst van rijen).
    Werkt met tabs (kopieerknop van Copilot) en met | (markdown). Geeft None als het geen tabel is.
    Zinnen boven en onder de tabel, zoals "Hier is je tabel:", slaat hij over."""
    regels = regels_schoon(tekst)
    tabelregels = [i for i, r in enumerate(regels) if "\t" in r or "|" in r]
    if not tabelregels:
        return None
    rijen = []
    for r in regels[tabelregels[0]:tabelregels[-1] + 1]:
        s = r.strip()
        if re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?", s):
            continue
        if "\t" in r:
            cellen = [c.strip() for c in r.split("\t")]
        elif "|" in s:
            cellen = [c.strip() for c in s.strip("|").split("|")]
        elif rijen:
            # Een vakje dat over meerdere regels loopt: plak het aan het laatste vakje.
            rijen[-1][-1] = (rijen[-1][-1] + " " + s).strip()
            continue
        else:
            return None
        rijen.append(cellen)
    if len(rijen) < 2 or len(rijen[0]) < 2:
        return None
    n = len(rijen[0])
    return [(r + [""] * n)[:n] for r in rijen]


def toon_tabel(rijen):
    kop = []
    for i, k in enumerate(rijen[0]):
        k = k or f"Kolom {i + 1}"
        while k in kop:
            k += " "
        kop.append(k)
    st.table(pd.DataFrame(rijen[1:], columns=kop).set_index(kop[0]))


def tijd(minuten):
    st.caption(f"⏱ {minuten} minuten")


def waarom(s):
    if s.get("waarom"):
        st.caption(f"💡 **{s.get('waarom_titel', 'Waarom zo?')}** {s['waarom']}")


KOPIEER_UITLEG = "Ga met je muis over het grijze vak. Klik rechtsboven op het kopieericoon."


def prompt(tekst, label="Prompt voor Copilot", plak="Copilot Chat", uitleg=True):
    """Grijs vak met kopieerknop, duidelijk gemarkeerd als prompt.
    uitleg=False: geen kopieeruitleg in het vak, omdat die al 1 keer boven een groep prompts staat."""
    with st.container(border=True):
        if uitleg:
            st.markdown(f"📋 **{label}**  \n:gray[{KOPIEER_UITLEG} Plak in {plak}.]")
        else:
            st.markdown(f"📋 **{label}**")
        st.code(tekst, language=None, wrap_lines=True)


def vet(tekst):
    if tekst:
        st.markdown(f"**{tekst}**")


def navigatie(mag_door=True, reden=""):
    """Volgende is altijd oranje. Bij klikken leest de app de velden en controleert ze."""
    links, rechts, _ = st.columns([1, 1, 3])
    if ss.stap > 1:
        if links.button("Terug", key=f"terug_{ss.stap}", use_container_width=True):
            ss.stap -= 1
            st.rerun()
    if ss.stap < LAATSTE:
        if rechts.button("Volgende", key=f"volgende_{ss.stap}", type="primary", use_container_width=True):
            if mag_door:
                ss.stap += 1
                st.rerun()
            else:
                st.error(reden or "Je bent nog niet klaar met deze stap.")


def codewoord_ok(invoer, juist):
    return invoer.strip().upper().replace(" ", "") == juist.strip().upper().replace(" ", "")


def deel_in_teams(tekst):
    st.markdown("**Deel in Teams**")
    st.caption(f"Kopieer de grijze zin met het icoon rechtsboven en plak hem in de draad in het Teams-kanaal. Je hoeft er niets bij te typen. Een vraag? Steek je hand op of vraag het {TRAINER}.")
    st.code(tekst, language=None, wrap_lines=True)


def is_extern(tool):
    return bool(tool) and tool != "Copilot"


# ---------- pdf ----------
VERVANG = {
    "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...", "•": "-",
    "→": "->", "≥": ">=", "≤": "<=", "€": "EUR ", "✓": "v", "✔": "v", "✅": "v", "❌": "x",
}


def latin(t):
    for a, b in VERVANG.items():
        t = t.replace(a, b)
    # Wat dan nog niet in latin-1 past (zoals emoji), valt weg in plaats van een '?' te worden.
    return t.encode("latin-1", "ignore").decode("latin-1")


def pdf_naam():
    """Unieke naam, zodat niemand in de Teams-map de pdf van een ander overschrijft."""
    def slug(t):
        return re.sub(r"[^a-z0-9]+", "-", (t or "").lower()).strip("-")
    delen = ["kickoff", slug(C["pilot"].replace("AI-pilot", "")), slug(ss.get("functie", ""))[:30], f"{datetime.now():%Y%m%d-%H%M%S}"]
    return "-".join(d for d in delen if d) + ".pdf"


def maak_pdf():
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    w = pdf.w - pdf.l_margin - pdf.r_margin

    def kop(t, grootte=13):
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", grootte)
        pdf.set_text_color(31, 42, 107)
        pdf.multi_cell(w, 7, latin(t), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(27, 31, 59)

    def tekst(t, mono=False):
        pdf.set_font("Courier" if mono else "Helvetica", "", 8 if mono else 11)
        pdf.multi_cell(w, 4.5 if mono else 6, latin(t or "-"), align="L", new_x="LMARGIN", new_y="NEXT")

    def tabel(ruw):
        rijen = lees_tabel(ruw)
        if not rijen:
            tekst(schoon(ruw), mono=True)
            return
        try:
            pdf.set_font("Helvetica", "", 8)
            with pdf.table(line_height=4.5, text_align="LEFT", first_row_as_headings=True) as t:
                for r in rijen:
                    rij = t.row()
                    for c in r:
                        rij.cell(latin(c))
        except Exception:
            tekst(schoon(ruw), mono=True)

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(240, 110, 30)
    pdf.cell(w, 10, latin(f"{C['pilot']}: {C['titel']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(w, 6, latin(f"{C['sessie']}, {date.today():%d-%m-%Y}"), new_x="LMARGIN", new_y="NEXT")

    kop("1. Mijn resultaat")
    tekst("Functie: " + ss.get("functie", "") + ", afdeling: " + ss.get("afdeling", ""))
    tekst(ss.get("resultaat", ""))
    kop("2. Mijn stappen (tabel uit Copilot)")
    tabel(ss.get("tabel", ""))
    kop("3. Mijn gekozen stap")
    tekst("Stap: " + ss.get("stap_keuze", ""))
    tekst("Dit moet de stap opleveren: " + ss.get("oplevert", ""))
    tekst("Dit moet er zeker in staan: " + ss.get("punten", ""))
    if ss.get("idee", "").strip():
        tekst("Idee voor het AI CoE: " + ss.get("idee", ""))
    kop("4. Mijn eerste resultaat")
    tekst("Tool: " + (ss.get("tool") or "-"))
    tekst("Score: " + (ss.get("score") or "-"))
    tekst("Wat ik zelf nog moest doen: " + ss.get("herstel", ""))
    if ss.get("bijsturing", "").strip():
        tekst("Deze bijsturing maakte het verschil: " + ss.get("bijsturing", ""))
    kop("5. Mijn plan")
    for i in range(1, len(S["plan"]["tests"]) + 1):
        tekst(f"Test {i}: " + ss.get(f"test{i}", ""))
    kop("Prompts die ik gebruikte", 11)
    for naam, p in gebruikte_prompts():
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(w, 5, latin(naam), new_x="LMARGIN", new_y="NEXT")
        tekst(p, mono=True)
        pdf.ln(1)
    return bytes(pdf.output())


def eerste_prompt():
    return vul_in(S["eerste"]["prompt"], stap=ss.get("stap_keuze", ""), oplevert=ss.get("oplevert", ""), punten=ss.get("punten", ""))


def gebruikte_prompts():
    return [
        ("Interview", vul_in(S["interview"]["prompt"], resultaat=ss.get("resultaat", ""))),
        ("Eerste resultaat", eerste_prompt()),
    ]


def samenvatting():
    tests = "; ".join(ss.get(f"test{i}", "") for i in range(1, len(S["plan"]["tests"]) + 1))
    return "\n".join(
        [
            f"Resultaat: {ss.get('resultaat', '')}",
            f"Gekozen stap: {ss.get('stap_keuze', '')}",
            f"Dit moet erin staan: {ss.get('punten', '')}",
            f"Tool: {ss.get('tool') or '-'}",
            f"Eerste resultaat: {ss.get('score') or '-'}",
            f"Wat ik zelf nog moest doen: {ss.get('herstel', '')}",
            f"Testmomenten: {tests}",
        ]
    )


# ---------- zijbalk ----------
with st.sidebar:
    st.markdown(f"**{C['pilot']}**  \n{C['sessie']}")
    for i, naam in enumerate(STAPPEN):
        if i < ss.stap:
            st.markdown(f":green[✓ {naam}]")
        elif i == ss.stap:
            st.markdown(f":orange[**● {naam}**]")
        elif (i >= 1 and not ss.code1) or (i >= SLOT_VANAF and not ss.code2):
            st.markdown(f":gray[🔒 {naam}]")
        else:
            st.markdown(f"○ {naam}")
    st.divider()
    for w in C["zijbalk_waarschuwingen"]:
        st.markdown(f":red[{w}]")

# Bij een nieuwe stap naar boven scrollen
if ss.get("_vorige_stap") != ss.stap:
    ss["_vorige_stap"] = ss.stap
    script(
        "<script>/*" + str(ss.stap) + "*/ const d = window.parent.document;"
        " for (const s of ['[data-testid=\"stMain\"]', 'section.main', '[data-testid=\"stAppViewContainer\"]'])"
        " { const e = d.querySelector(s); if (e) e.scrollTo(0, 0); } window.parent.scrollTo(0, 0);</script>"
    )

if ss.stap > 0:
    st.progress(ss.stap / LAATSTE)
    st.caption(f"Deel {ss.stap} van {LAATSTE}")

# ---------- stappen ----------
if ss.stap == 0:
    st.title(C["titel"])
    st.write(C["start"]["tekst"])
    st.info(C["start"]["zo_werk_je"])
    waarom(C["start"])
    st.caption(C["start"]["functie_hulp"])
    functie = bewaar_tekst(C["start"]["functie_label"], "functie")
    afdeling = bewaar_tekst(C["start"]["afdeling_label"], "afdeling", standaard=C["start"].get("afdeling_standaard", ""))
    code = st.text_input(f"Codewoord van {TRAINER}", key="w_code1") if CODES.get("start") else ""
    if st.button("Start", type="primary"):
        if not functie or not afdeling:
            st.error("Vul eerst je functie en je afdeling in.")
        elif not CODES.get("start") or codewoord_ok(code, CODES["start"]):
            ss.code1 = True
            ss.stap = 1
            st.rerun()
        else:
            st.error(f"Dit codewoord klopt niet. Vraag het aan {TRAINER}.")

elif ss.stap == 1:
    s = S["resultaat"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    if s.get("goed_kort"):
        st.info(s["goed_kort"])
    else:
        st.info("**Een goed resultaat**\n" + "\n".join(f"- {x}" for x in s["goed_resultaat"]))
    a, b, c = st.columns(3)
    a.markdown(f"**:orange[{s.get('te_groot_titel', 'Te breed')}]**  \n{s['te_groot']}")
    b.markdown(f"**:orange[{s.get('beter_titel', 'Concreet genoeg')}]**  \n{s['beter']}")
    c.markdown(f"**:orange[{s.get('demos_titel', 'Andere voorbeelden')}]**\n" + "\n".join(f"- {x}" for x in s["demos"]))
    if s.get("beter_waarom"):
        st.caption(s["beter_waarom"])
    res = bewaar_tekst(s["resultaat_label"], "resultaat", area=True)
    with st.expander("🔎 " + s["weet_niet_titel"]):
        st.write(s["weet_niet_tekst"])
        prompt(s["weet_niet_prompt"])
    st.info(f"{s['extern_tekst']}\n\n🔒 **Mag het?** {C['dataregel']}")
    navigatie(bool(res), "Vul in wat je regelmatig oplevert, en voor wie.")

elif ss.stap == 2:
    s = S["interview"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    prompt(vul_in(s["prompt"], resultaat=ss.get("resultaat", "")))
    if s.get("opbouw"):
        st.caption(s["opbouw"])
    waarom(s)
    st.warning(s["waarschuwing"])
    with st.expander(s.get("hulp_titel", "Loopt het gesprek met Copilot anders dan verwacht?")):
        st.info(s.get("hulp_tekst", "Kopieer de prompt die bij jouw situatie past en plak hem in je gesprek met Copilot. Ga daarna verder met het interview.") + " " + KOPIEER_UITLEG)
        for h in s["hulp"]:
            prompt(h["prompt"], h["label"], uitleg=False)
        st.caption(s["terug_tip"])
    navigatie()

elif ss.stap == 3:
    s = S["kies"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])

    st.markdown(f"#### {s['check_titel']}")
    st.write(s["check_tekst"])
    with st.expander(s.get("bijsturen_titel", "Prompts om bij te sturen")):
        st.info(s.get("bijsturen_tekst", "Vul de [haakjes] in voordat je plakt.") + " " + KOPIEER_UITLEG)
        for i, p in enumerate(s["bijsturen"], 1):
            if isinstance(p, dict):
                prompt(p["prompt"], p["label"], uitleg=False)
            else:
                prompt(p, f"Prompt {i}", uitleg=False)
    tabel = bewaar_tekst(s["plak_label"], "tabel", area=True)
    rijen = lees_tabel(tabel) if tabel else None
    if rijen:
        st.caption(s["tabel_ok"])
        toon_tabel(rijen)
    elif tabel:
        st.warning(s.get("geen_tabel", "Dit lijkt geen tabel. Vraag Copilot om alleen de tabel, en kopieer hem met de kopieerknop onder het antwoord."))
        prompt(s.get("geen_tabel_prompt", "Zet je antwoord in een tabel met 3 kolommen: Stap, Gedoe, Kans met Copilot. Maximaal 6 woorden per vakje. Geef alleen de tabel."))
    waarom(s)

    st.markdown(f"#### {s['kies_titel']}")
    st.write(s["kies_intro"])
    links, rechts = st.columns(2)
    links.success(f"**{s['goed_titel']}**\n" + "\n".join(f"- {x}" for x in s["goed"]))
    rechts.warning(f"**{s['niet_titel']}**\n" + "\n".join(f"- {x}" for x in s["niet"]))
    st.markdown(f"**{s['stap_label']}**")
    st.caption(s["stap_hulp"])
    stap = bewaar_tekst(s["stap_label"], "stap_keuze", area=True, label_visibility="collapsed")
    stap_nummer = bool(stap) and is_nummer(stap)
    if stap_nummer:
        st.warning(s["stap_fout"])
    st.markdown(f"**{s['oplevert_label']}**")
    st.caption(s["oplevert_hulp"])
    oplevert = bewaar_tekst(s["oplevert_label"], "oplevert", area=True, label_visibility="collapsed")
    bewaar_tekst(s["idee_label"], "idee", area=True)

    st.markdown(f"#### {s['punten_titel']}")
    st.markdown(f"**{s['punten_label']}**")
    st.caption(s["punten_hulp"])
    punten = bewaar_tekst(s["punten_label"], "punten", area=True, label_visibility="collapsed")
    with st.expander("✂️ " + s["opdelen_titel"]):
        prompt(vul_in(s["opdelen_prompt"], stap=ss.get("stap_keuze", "")))
        st.write(s["opdelen_tekst"])
    navigatie(
        bool(tabel) and bool(stap) and not stap_nummer and bool(oplevert) and bool(punten),
        "Plak je tabel, beschrijf je stap in woorden, vul in wat hij oplevert en schrijf je 3 punten op.",
    )

elif ss.stap == 4 and not ss.code2:
    s = S["wacht"]
    st.markdown("# ⏸")
    st.title(s["titel"])
    st.write(s["tekst"])
    st.info(s["tip"])
    code = st.text_input("Codewoord", key="w_code2") if CODES.get("verder") else ""
    links, rechts, _ = st.columns([1, 1, 3])
    links.button("Terug", key="terug_wacht", on_click=lambda: ss.update(stap=3), use_container_width=True)
    if rechts.button("Verder", type="primary", use_container_width=True):
        if not CODES.get("verder") or codewoord_ok(code, CODES["verder"]):
            ss.code2 = True
            st.rerun()
        else:
            st.error(f"Dit codewoord klopt niet. Wacht op {TRAINER}.")

elif ss.stap == 4:
    s = S["eerste"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    if len(s["tool_opties"]) == 1:  # 1 tool: geen keuze tonen
        tool = ss["tool"] = s["tool_opties"][0]
    else:
        tool = bewaar_keuze(s["tool_label"], s["tool_opties"], "tool", horizontal=True)
        st.caption(s["tool_hulp"])
    punten = bewaar_tekst(s["punten_label"], "punten", area=True)
    plak = f"de AI van {EXTERN}" if is_extern(tool) else "Copilot Chat"
    prompt(eerste_prompt(), f"Prompt voor {tool or 'Copilot'}", plak)
    st.caption(s["opbouw"])
    waarom(s)
    st.warning(s["bronnen_tip"]["extern" if is_extern(tool) else "copilot"])
    st.error(s["klantregel"])
    with st.expander(s["bijsturen_titel"]):
        st.caption(s["bijsturen_tip"])
        for h in s["bijsturen"]:
            prompt(h["prompt"], h["label"], plak)
    bewaar_tekst(s["bijsturing_label"], "bijsturing", area=True)
    st.subheader("Controleer de uitkomst")
    vet(s["controle_intro"])
    for i, t in enumerate(s["controle"]):
        bewaar_vinkje(t, f"e_v{i}")
    keuze = bewaar_keuze("Mijn score", s["scores"], "score")
    herstel = bewaar_tekst(s["herstel_label"], "herstel", area=True)
    if keuze and herstel:
        deel_in_teams(vul_in(s["teams"], stap=ss.get("stap_keuze", ""), tool=tool or "", score=keuze.lower(), herstel=herstel))
    navigatie(bool(tool) and bool(punten) and bool(keuze) and bool(herstel), "Kies je tool, kies een score en vul in wat je zelf nog moest doen.")

elif ss.stap == 5:
    s = S["plan"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    waarom(s)
    for i, label in enumerate(s["tests"], 1):
        bewaar_tekst(label, f"test{i}")
    st.subheader("Bewaar je werk")
    st.write("In de pdf staat alles: je resultaat, je tabel, je gekozen stap met je 3 punten, de tool, je eerste resultaat, je plan en de prompts.")
    st.download_button(
        "⬇ Download alles als pdf",
        data=maak_pdf(),
        file_name=pdf_naam(),
        mime="application/pdf",
        type="primary",
    )
    with st.expander("Of kopieer een korte samenvatting"):
        st.code(samenvatting(), language=None, wrap_lines=True)
    st.success(s["afsluiting"])
    navigatie()
