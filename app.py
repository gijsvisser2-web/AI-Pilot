"""Kickoff-route AI-pilot: van resultaat naar taak.

Alle teksten, prompts en codewoorden staan in inhoud.yaml.
De app slaat niets op. Invoer blijft alleen in de sessie van de deelnemer.
"""
import re
from datetime import date
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import yaml
from fpdf import FPDF

MAP = Path(__file__).parent
C = yaml.safe_load((MAP / "inhoud.yaml").read_text(encoding="utf-8"))
S = C["stappen"]

STAPPEN = [
    "Start",
    "1. Je resultaat",
    "2. Copilot interviewt je",
    "3. Check je tabel",
    "4. Wie doet wat?",
    "5. Kies 1 stap",
    "6. Je eerste resultaat",
    "7. Je plan",
]
LAATSTE = len(STAPPEN) - 1
SLOT_VANAF = 5  # vanaf deze stap is codewoord 2 nodig

st.set_page_config(page_title=C["titel"], page_icon="📦", layout="centered")
ss = st.session_state
ss.setdefault("stap", 0)
ss.setdefault("code1", False)
ss.setdefault("code2", False)


# ---------- hulpfuncties ----------
def bewaar_tekst(label, k, area=False, **kw):
    """Tekstveld waarvan de waarde blijft bestaan als je naar een andere stap gaat."""
    ss.setdefault(k, kw.pop("standaard", ""))
    veld = st.text_area if area else st.text_input
    ss[k] = veld(label, value=ss[k], key="w_" + k, **kw)
    return ss[k].strip()


def bewaar_vinkje(label, k):
    ss.setdefault(k, False)
    ss[k] = st.checkbox(label, value=ss[k], key="w_" + k)
    return ss[k]


def vul_in(tekst, **waarden):
    for naam, waarde in waarden.items():
        tekst = tekst.replace("{" + naam + "}", waarde or f"[{naam}]")
    return tekst


def schoon(tekst):
    """Haalt restjes uit tekst die uit Copilot is gekopieerd."""
    regels = []
    for r in tekst.splitlines():
        s = r.strip()
        if re.fullmatch(r"\+\d+", s) or s == "Bronnen" or s.startswith("Geredeneerd voor"):
            continue
        regels.append(r.rstrip().replace("\t", "  |  "))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(regels)).strip()


def tijd(minuten):
    st.caption(f"⏱ {minuten} minuten")


def waarom(s):
    if s.get("waarom"):
        st.caption(f"💡 **Waarom zo?** {s['waarom']}")


def prompt(tekst, label="Prompt voor Copilot"):
    """Grijs vak met kopieerknop, duidelijk gemarkeerd als prompt."""
    with st.container(border=True):
        st.markdown(f"📋 **{label}**  \n:gray[Kopieer met het icoon rechtsboven in het grijze vak. Plak in Copilot Chat.]")
        st.code(tekst, language=None, wrap_lines=True)


def vinkjes_intro(s, sleutel="vinkjes_intro"):
    if s.get(sleutel):
        st.markdown(f"**{s[sleutel]}**")


def navigatie(mag_door=True, reden=""):
    """Volgende is altijd oranje. Bij klikken leest de app de velden en controleert ze.
    Streamlit leest een tekstveld pas bij Enter of klikken buiten het veld; een klik op de knop telt ook."""
    links, rechts, _ = st.columns([1, 1, 3])
    if ss.stap > 1:
        links.button("Terug", on_click=lambda: ss.update(stap=ss.stap - 1), use_container_width=True)
    if ss.stap < LAATSTE:
        if rechts.button("Volgende", type="primary", use_container_width=True):
            if mag_door:
                ss.stap += 1
                st.rerun()
            else:
                st.error(reden or "Je bent nog niet klaar met deze stap.")


def codewoord_ok(invoer, juist):
    return invoer.strip().upper().replace(" ", "") == juist.strip().upper().replace(" ", "")


def deel_in_teams(tekst):
    st.markdown("**Deel in Teams**")
    st.caption("Plak deze zin in de draad in het Teams-kanaal. Geen klantgegevens, geen schermafbeeldingen van Copilot.")
    st.code(tekst, language=None, wrap_lines=True)


# ---------- pdf ----------
VERVANG = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...", "•": "-", "→": "->", "≥": ">=", "≤": "<="}


def latin(t):
    for a, b in VERVANG.items():
        t = t.replace(a, b)
    return t.encode("latin-1", "replace").decode("latin-1")


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

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(240, 110, 30)
    pdf.cell(w, 10, latin(f"{C['pilot']}: {C['titel']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(w, 6, latin(f"{C['sessie']}, {date.today():%d-%m-%Y}"), new_x="LMARGIN", new_y="NEXT")

    kop("1. Mijn resultaat")
    tekst("Functie: " + ss.get("functie", ""))
    tekst(ss.get("resultaat", ""))
    kop("2 en 3. Mijn stappen (tabel uit Copilot)")
    tekst(schoon(ss.get("tabel", "")), mono=True)
    kop("4. Wie doet wat")
    tekst("Wat ik anders indeelde dan Copilot, en waarom: " + ss.get("anders", ""))
    kop("5. Mijn gekozen stap")
    tekst(ss.get("stap_keuze", ""))
    tekst("Dit moet de stap opleveren: " + ss.get("oplevert", ""))
    if ss.get("idee", "").strip():
        tekst("Idee voor later: " + ss.get("idee", ""))
    kop("6. Mijn eerste resultaat")
    tekst("Dit moest er zeker in staan: " + ss.get("punten", ""))
    tekst("Score: " + (ss.get("score") or "-"))
    tekst("Wat ik zelf nog moest doen: " + ss.get("herstel", ""))
    if ss.get("bijsturing", "").strip():
        tekst("Deze bijsturing maakte het verschil: " + ss.get("bijsturing", ""))
    kop("7. Mijn plan")
    for i in (1, 2, 3):
        tekst(f"Test {i}: " + ss.get(f"test{i}", ""))
    kop("Prompts die ik gebruikte", 11)
    for naam, p in gebruikte_prompts():
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(w, 5, latin(naam), new_x="LMARGIN", new_y="NEXT")
        tekst(p, mono=True)
        pdf.ln(1)
    return bytes(pdf.output())


def gebruikte_prompts():
    return [
        ("Interview", vul_in(S["interview"]["prompt"], resultaat=ss.get("resultaat", ""), functie=ss.get("functie", ""))),
        ("Wie doet wat", S["wiedoetwat"]["prompt"]),
        ("Eerste resultaat", vul_in(S["eerste"]["prompt"], stap=ss.get("stap_keuze", ""), oplevert=ss.get("oplevert", ""), punten=ss.get("punten", ""), functie=ss.get("functie", ""))),
    ]


def samenvatting():
    return "\n".join(
        [
            f"Resultaat: {ss.get('resultaat', '')}",
            f"Gekozen stap: {ss.get('stap_keuze', '')}",
            f"Anders ingedeeld dan Copilot: {ss.get('anders', '')}",
            f"Eerste resultaat: {ss.get('score') or '-'}",
            f"Wat ik zelf nog moest doen: {ss.get('herstel', '')}",
            f"Testmomenten: {ss.get('test1', '')}; {ss.get('test2', '')}; {ss.get('test3', '')}",
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
    components.html(
        "<script>/*" + str(ss.stap) + "*/ const d = window.parent.document;"
        " for (const s of ['[data-testid=\"stMain\"]', 'section.main', '[data-testid=\"stAppViewContainer\"]'])"
        " { const e = d.querySelector(s); if (e) e.scrollTo(0, 0); } window.parent.scrollTo(0, 0);</script>",
        height=0,
    )

if ss.stap > 0:
    st.progress(ss.stap / LAATSTE)
    st.caption(f"Stap {ss.stap} van {LAATSTE}")

# ---------- stappen ----------
if ss.stap == 0:
    st.title(C["titel"])
    st.write(C["start"]["tekst"])
    st.info(C["start"]["zo_werk_je"])
    waarom(C["start"])
    functie = bewaar_tekst(C["start"]["functie_label"], "functie")
    st.caption(C["start"]["functie_hulp"])
    code = st.text_input("Codewoord van Gijs", key="w_code1")
    if st.button("Start", type="primary"):
        if not functie:
            st.error("Vul eerst je functie in.")
        elif codewoord_ok(code, C["codewoorden"]["start"]):
            ss.code1 = True
            ss.stap = 1
            st.rerun()
        else:
            st.error("Dit codewoord klopt niet. Vraag het aan Gijs.")

elif ss.stap == 1:
    s = S["resultaat"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    st.info("**Een goed resultaat**\n" + "\n".join(f"- {x}" for x in s["goed_resultaat"]))
    a, b, c = st.columns(3)
    a.markdown(f"**:orange[Te groot]**  \n{s['te_groot']}")
    b.markdown(f"**:orange[Beter]**  \n{s['beter']}")
    c.markdown("**:orange[Zoals in de demo's]**  \n" + "  \n".join(s["demos"]))
    st.caption(s["demo_noot"])
    with st.expander("🔎 " + s["weet_niet_titel"]):
        st.write(s["weet_niet_tekst"])
        prompt(s["weet_niet_prompt"])
    res = bewaar_tekst("Wat lever je op, en aan wie?", "resultaat")
    st.info(s["salesforce"])
    vinkjes_intro(s)
    v1 = bewaar_vinkje(s["vinkjes"][0], "r_v1")
    v2 = bewaar_vinkje(s["vinkjes"][1], "r_v2")
    navigatie(bool(res) and v1 and v2, "Vul je resultaat in en zet beide vinkjes.")

elif ss.stap == 2:
    s = S["interview"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    prompt(vul_in(s["prompt"], resultaat=ss.get("resultaat", ""), functie=ss.get("functie", "")))
    st.caption(s["opbouw"])
    waarom(s)
    st.warning(s["waarschuwing"])
    with st.expander("Loop je vast, of stelt Copilot iets anders voor?"):
        st.info(s["terug_tip"])
        st.caption("Gebruik deze prompts alleen als het helpt.")
        for h in s["hulp"]:
            prompt(h["prompt"], h["label"])
    vinkjes_intro(s, "vinkje_intro")
    klaar = bewaar_vinkje(s["vinkje"], "i_klaar")
    navigatie(klaar, "Zet het vinkje als Copilot je tabel heeft gegeven.")

elif ss.stap == 3:
    s = S["check"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    waarom(s)
    vinkjes_intro(s)
    vinkjes = [bewaar_vinkje(t, f"c_v{i}") for i, t in enumerate(s["vinkjes"])]
    st.subheader("Klopt iets niet? Stuur bij")
    for i, p in enumerate(s["bijsturen"], 1):
        prompt(p, f"Prompt {i}: vul de [haakjes] in voor je plakt")
    tabel = bewaar_tekst(s["plak_label"], "tabel", area=True, height=180)
    navigatie(all(vinkjes) and bool(tabel), "Zet de 3 vinkjes en plak je tabel.")

elif ss.stap == 4:
    s = S["wiedoetwat"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    prompt(s["prompt"])
    waarom(s)
    st.subheader("Jouw controle")
    vinkjes_intro(s)
    vinkjes = [bewaar_vinkje(t, f"w_v{i}") for i, t in enumerate(s["vinkjes"])]
    anders = bewaar_tekst(s["anders_label"], "anders", area=True, height=90)
    if anders:
        deel_in_teams(vul_in(s["teams"], anders=anders))
    navigatie(all(vinkjes) and bool(anders), "Zet de 3 vinkjes en schrijf op welke stap je anders indeelde.")

elif ss.stap == 5 and not ss.code2:
    s = S["wacht"]
    st.markdown("# ⏸")
    st.title(s["titel"])
    st.write(s["tekst"])
    st.info(s["tip"])
    code = st.text_input("Codewoord", key="w_code2")
    links, rechts, _ = st.columns([1, 1, 3])
    links.button("Terug", on_click=lambda: ss.update(stap=4), use_container_width=True)
    if rechts.button("Verder", type="primary", use_container_width=True):
        if codewoord_ok(code, C["codewoorden"]["verder"]):
            ss.code2 = True
            st.rerun()
        else:
            st.error("Dit codewoord klopt niet. Wacht op Gijs.")

elif ss.stap == 5:
    s = S["kies"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    waarom(s)
    stap = bewaar_tekst(s["stap_label"], "stap_keuze")
    if "oplevert" not in ss:
        ss["oplevert"] = ss.get("resultaat", "")
    oplevert = bewaar_tekst(s["oplevert_label"], "oplevert")
    st.subheader("Past hij?")
    vinkjes_intro(s)
    vinkjes = [bewaar_vinkje(t, f"k_v{i}") for i, t in enumerate(s["vinkjes"])]
    st.success(s["past_niet"])
    bewaar_tekst(s["idee_label"], "idee")
    navigatie(bool(stap) and bool(oplevert) and all(vinkjes), "Vul je stap in en zet de 3 vinkjes.")

elif ss.stap == 6:
    s = S["eerste"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    punten = bewaar_tekst(s["punten_label"], "punten", area=True, height=90)
    st.caption(s["punten_hulp"])
    prompt(vul_in(s["prompt"], stap=ss.get("stap_keuze", ""), oplevert=ss.get("oplevert", ""), punten=punten, functie=ss.get("functie", "")))
    waarom(s)
    st.warning(s["bronnen_tip"])
    with st.expander(s["bijsturen_titel"]):
        st.caption(s["bijsturen_tip"])
        for h in s["bijsturen"]:
            prompt(h["prompt"], h["label"])
    bewaar_tekst(s["bijsturing_label"], "bijsturing")
    st.subheader("Controleer de uitkomst")
    vinkjes_intro(s)
    for i, t in enumerate(s["controle"]):
        bewaar_vinkje(t, f"e_v{i}")
    ss.setdefault("score", None)
    keuze = st.radio(
        "Mijn score",
        s["scores"],
        index=s["scores"].index(ss.score) if ss.score in s["scores"] else None,
        key="w_score",
    )
    ss.score = keuze
    herstel = bewaar_tekst(s["herstel_label"], "herstel", area=True, height=90)
    if keuze and herstel:
        deel_in_teams(vul_in(s["teams"], stap=ss.get("stap_keuze", ""), score=keuze.lower(), herstel=herstel))
    navigatie(bool(punten) and bool(keuze) and bool(herstel), "Vul je 3 punten in, kies een score en vul in wat je zelf nog moest doen.")

elif ss.stap == 7:
    s = S["plan"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    waarom(s)
    for i in (1, 2, 3):
        bewaar_tekst(f"Test {i}", f"test{i}")
    st.subheader("Bewaar je werk")
    st.write("In de pdf staat alles: je resultaat, je tabel, je indeling, je gekozen stap, je eerste resultaat, je plan en de prompts.")
    st.download_button(
        "⬇ Download alles als pdf",
        data=maak_pdf(),
        file_name=f"kickoff-{date.today():%Y%m%d}.pdf",
        mime="application/pdf",
        type="primary",
    )
    with st.expander("Of kopieer een korte samenvatting"):
        st.code(samenvatting(), language=None, wrap_lines=True)
    st.success(s["afsluiting"])
    navigatie()
