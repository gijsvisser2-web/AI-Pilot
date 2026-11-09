"""Sessie 3 AI-pilot: test en besluit.

Alle teksten, prompts en codewoorden staan in inhoud_sessie3.yaml.
De app slaat niets op. Invoer blijft alleen in de sessie van de deelnemer.
"""
from datetime import date
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import yaml
from fpdf import FPDF

MAP = Path(__file__).parent
C = yaml.safe_load((MAP / "inhoud_sessie3.yaml").read_text(encoding="utf-8"))
S = C["stappen"]

STAPPEN = [
    "Start",
    "1. Waar sta je?",
    "2. Testpakket",
    "3. Testen in tweetallen",
    "4. Verander 1 ding",
    "5. Pre-mortem",
    "6. Jouw besluit",
    "7. Je eigen proefroute",
    "8. Naar de showcase",
]
LAATSTE = len(STAPPEN) - 1
SLOT_VANAF = 5  # vanaf deze stap is codewoord 2 nodig

st.set_page_config(page_title=C["titel"], page_icon="🧪", layout="centered")
ss = st.session_state
ss.setdefault("stap", 0)
ss.setdefault("code1", False)
ss.setdefault("code2", False)


# ---------- hulpfuncties ----------
def bewaar_tekst(label, k, area=False, **kw):
    ss.setdefault(k, kw.pop("standaard", ""))
    veld = st.text_area if area else st.text_input
    ss[k] = veld(label, value=ss[k], key="w_" + k, **kw)
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


def niet_getest():
    return all(ss.get(f"t{i}_score") == "Niet gedaan" for i in (1, 2, 3))


def tests_tekst():
    if niet_getest():
        return "nog niet getest (" + (ss.get("waarom_niet") or "geen reden gekozen") + ")"
    delen = []
    for i in (1, 2, 3):
        score = ss.get(f"t{i}_score")
        if not score or score == "Niet gedaan":
            continue
        deel = f"test {i}: {score.lower()}"
        if ss.get(f"t{i}_opbrengst"):
            deel += f", leverde op: {ss[f't{i}_opbrengst'].lower()}"
        if ss.get(f"t{i}_herstel", "").strip():
            deel += f", zelf nog doen: {ss[f't{i}_herstel'].strip()}"
        delen.append(deel)
    return "; ".join(delen) or "niet ingevuld"


def tijd(minuten):
    st.caption(f"⏱ {minuten} minuten")


def waarom(s):
    if s.get("waarom"):
        st.caption(f"💡 **Waarom zo?** {s['waarom']}")


def prompt(tekst, label="Prompt voor Copilot"):
    with st.container(border=True):
        st.markdown(f"📋 **{label}**  \n:gray[Kopieer met het icoon rechtsboven in het grijze vak.]")
        st.code(tekst, language=None, wrap_lines=True)


def vet(tekst):
    if tekst:
        st.markdown(f"**{tekst}**")


def navigatie(mag_door=True, reden=""):
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


def kort(keuze):
    """Eerste woord van een keuze, zoals 'Delen' uit 'Delen: ik deel hem met mijn team'."""
    return (keuze or "").split(":")[0]


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

    g = ss.get
    kop("1. Waar ik sta")
    tekst("Functie: " + g("functie", "") + ", afdeling: " + g("afdeling", ""))
    tekst("Tests sinds sessie 2: " + tests_tekst())
    kop("Instructie versie 0.2", 11)
    tekst(g("instructie", ""), mono=True)
    kop("2. Testpakket")
    tekst("Taak: " + g("taak", ""))
    tekst("Input: " + g("input", ""))
    tekst("Mijn 3 punten: " + g("punten", ""))
    tekst("Mag het: " + (g("kleur") or "-"))
    kop("3. Wat de tester zag")
    tekst("Score van de tester: " + (g("score_t") or "-") + ". Mijn 3 punten erin: " + (g("punten_t") or "-"))
    tekst("Waar de tester aarzelde: " + g("aarzel", ""))
    tekst("Wat de tester zelf nog moest doen: " + g("herstel_t", ""))
    tekst("Het 1 ding van de tester: " + g("ding", ""))
    tekst("Wat ik als tester leerde: " + g("leer", ""))
    kop("4. Versie 0.3")
    tekst("Wat ik aanpaste en waarom: " + g("aanpas", ""))
    tekst(g("v03", ""), mono=True)
    kop("5. Pre-mortem")
    for i in (1, 2, 3):
        tekst(f"Reden {i}: " + g(f"reden{i}", ""))
    tekst("Meest waarschijnlijk: " + (g("meest") or "-"))
    tekst("Wat ik doe om dat te voorkomen: " + g("actie", ""))
    tekst("Wanneer ik hem niet gebruik: " + g("wanneer_niet", ""))
    kop("6. Mijn besluit")
    tekst((g("besluit") or "-") + ". Waarom: " + g("besluit_waarom", ""))
    if g("delen_waar", "").strip():
        tekst("Delen met en waar: " + g("delen_waar", ""))
    if g("stoppen_mee", "").strip():
        tekst("Wat ik meeneem: " + g("stoppen_mee", ""))
    if g("door_wat", "").strip():
        tekst("Nodige koppeling: " + g("door_wat", ""))
    tekst("Dit blijft mensenwerk: " + g("mensenwerk", ""))
    kop("7. Mijn proefroute")
    tekst("Moment 1: " + g("moment1", "") + ". Moment 2: " + g("moment2", ""))
    if g("tester_idee", "").strip():
        tekst("Van mijn tester: " + g("tester_idee", ""))
    for i, v in enumerate(S["proefroute"]["vragen"]):
        tekst(v + " " + g(f"route{i}", ""))
    tekst(f"Eerste experiment ({g('keuze7') or '-'}): als {g('als7', '')}, {S['proefroute']['dan_tekst']}")
    kop("8. Voor de showcase")
    tekst("Mijn werkwijze: " + g("werkwijze", ""))
    tekst("Wat er verandert in mijn werk: " + g("verandert", ""))
    tekst("Mijn besluit: " + g("besluit8", ""))
    tekst(f"Als {g('als8', '')}, dan {g('dan8', '')}.")
    return bytes(pdf.output())


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
    afdeling = bewaar_tekst(C["start"]["afdeling_label"], "afdeling", standaard=C["start"].get("afdeling_standaard", ""))
    st.caption(C["start"]["functie_hulp"])
    code = st.text_input("Codewoord van Gijs", key="w_code1")
    if st.button("Start", type="primary"):
        if not functie or not afdeling:
            st.error("Vul eerst je functie en je afdeling in.")
        elif codewoord_ok(code, C["codewoorden"]["start"]):
            ss.code1 = True
            ss.stap = 1
            st.rerun()
        else:
            st.error("Dit codewoord klopt niet. Vraag het aan Gijs.")

elif ss.stap == 1:
    s = S["waar"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    instructie = bewaar_tekst(s["instructie_label"], "instructie", area=True, height=140)
    for i in (1, 2, 3):
        with st.container(border=True):
            st.markdown(f"**Test {i}**")
            score = bewaar_keuze("Hoe ging het?", s["scores"], f"t{i}_score", horizontal=True)
            if score and score != "Niet gedaan":
                bewaar_keuze("Wat leverde het op?", s["opbrengst"], f"t{i}_opbrengst", horizontal=True)
                bewaar_tekst("Wat moest je zelf nog doen voordat het bruikbaar was?", f"t{i}_herstel")
                bewaar_tekst("Wat pas je aan in je werkwijze?", f"t{i}_aanpas")
    if niet_getest():
        st.info(s["niet_getest"])
        bewaar_keuze("Waarom niet getest?", s["waarom_niet"], "waarom_niet")
    waarom(s)
    vet(s["vinkje_intro"])
    klaar = bewaar_vinkje(s["vinkje"], "v1")
    navigatie(bool(instructie) and klaar, "Plak je instructie en zet het vinkje.")

elif ss.stap == 2:
    s = S["pakket"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    taak = bewaar_tekst(s["taak_label"], "taak")
    invoer = bewaar_tekst(s["input_label"], "input", area=True, height=120)
    punten = bewaar_tekst(s["punten_label"], "punten", area=True, height=80)
    kleur = bewaar_keuze(s["kleur_vraag"], s["kleuren"], "kleur")
    rood_ok = True
    if kleur == s["kleuren"][0]:
        st.success(s["groen"])
    elif kleur == s["kleuren"][1]:
        st.warning(s["oranje"])
    elif kleur == s["kleuren"][2]:
        st.error(s["rood"])
        rood_ok = bewaar_vinkje(s["rood_vinkje"], "rood_ok")
    with st.expander(s["hulp_titel"]):
        prompt(vul_in(s["verzonnen_prompt"]), "Maak een verzonnen versie")
    prompt(vul_in(s["pakket"], instructie=ss.get("instructie", ""), input=invoer), s["pakket_label"])
    waarom(s)
    klaar = bewaar_vinkje(s["vinkje"], "v2")
    navigatie(
        bool(taak) and bool(invoer) and bool(punten) and bool(kleur) and rood_ok and klaar,
        "Vul taak, input en je 3 punten in, kies een kleur en zet het vinkje. Bij rood: gebruik een verzonnen versie.",
    )

elif ss.stap == 3:
    s = S["tweetal"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    with st.container(border=True):
        st.markdown("**Zo verloopt een ronde (15 minuten)**")
        for i, t in enumerate(s["ronde"], 1):
            st.markdown(f"{i}. {t}")
    waarom(s)
    maker, tester = st.tabs(["Ik ben maker", "Ik ben tester"])
    with maker:
        bewaar_tekst(s["aarzel_label"], "aarzel", area=True, height=80)
        score_t = bewaar_keuze("Score van de tester", s["scores"], "score_t", horizontal=True)
        punten_t = bewaar_keuze("Stonden mijn 3 punten erin?", s["punten_opties"], "punten_t", horizontal=True)
        bewaar_tekst(s["herstel_label"], "herstel_t")
        ding = bewaar_tekst(s["ding_label"], "ding")
    with tester:
        bewaar_tekst(s["leer_label"], "leer", area=True, height=80)
    vet(s["vinkje_intro"])
    m = bewaar_vinkje(s["vinkjes"][0], "v3m")
    t = bewaar_vinkje(s["vinkjes"][1], "v3t")
    navigatie(
        bool(score_t) and bool(punten_t) and bool(ding) and m and t,
        "Vul op het tabblad Ik ben maker de score, je 3 punten en het 1 ding in. Zet daarna beide vinkjes.",
    )

elif ss.stap == 4:
    s = S["verander"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    if ss.get("ding"):
        st.info("Het 1 ding van je tester: " + ss["ding"])
    if "v03" not in ss:
        ss["v03"] = ss.get("instructie", "")
    v03 = bewaar_tekst(s["v03_label"], "v03", area=True, height=160)
    aanpas = bewaar_tekst(s["aanpas_label"], "aanpas")
    prompt(v03, "Jouw instructie, versie 0.3")
    waarom(s)
    klaar = bewaar_vinkje(s["vinkje"], "v4")
    navigatie(bool(v03) and bool(aanpas) and klaar, "Pas je instructie aan, schrijf op wat je aanpaste en zet het vinkje.")

elif ss.stap == 5 and not ss.code2:
    s = S["wacht"]
    st.markdown("# ⏸")
    st.title(s["titel"])
    st.write(s["tekst"])
    st.info(s["tip"])
    prompt(ss.get("v03", ""), "Jouw instructie, versie 0.3")
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
    s = S["premortem"]
    st.title(s["titel"])
    tijd(s["tijd"])
    with st.container(border=True):
        st.markdown(f"🔮 **{s['intro']}**")
    redenen = [bewaar_tekst(f"Reden {i}", f"reden{i}") for i in (1, 2, 3)]
    with st.expander(s["hulp_titel"]):
        for h in s["hulp"]:
            st.markdown(f"- {h}")
    meest = bewaar_keuze(s["meest_label"], ["Reden 1", "Reden 2", "Reden 3"], "meest", horizontal=True)
    actie = bewaar_tekst(s["actie_label"], "actie")
    bewaar_tekst(s["niet_label"], "wanneer_niet", area=True, height=80)
    waarom(s)
    navigatie(bool(redenen[0]) and bool(meest) and bool(actie), "Vul minimaal 1 reden in, kies de meest waarschijnlijke en schrijf je actie op.")

elif ss.stap == 6:
    s = S["besluit"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    besluit = bewaar_keuze("Mijn besluit", s["opties"], "besluit")
    reden = bewaar_tekst(s["waarom_label"], "besluit_waarom", area=True, height=80)
    extra_ok = True
    if kort(besluit) == "Delen":
        with st.container(border=True):
            st.markdown("**Veiligheidscheck**")
            veilig = [bewaar_vinkje(t, f"veilig{i}") for i, t in enumerate(s["veilig"])]
            waar = bewaar_tekst(s["delen_label"], "delen_waar")
            st.caption(s["twijfel"])
        extra_ok = all(veilig) and bool(waar)
    elif kort(besluit) == "Stoppen":
        bewaar_tekst(s["stoppen_label"], "stoppen_mee")
    elif kort(besluit) == "Doorverwijzen":
        extra_ok = bool(bewaar_tekst(s["door_label"], "door_wat"))
    mensenwerk = bewaar_tekst(s["mensenwerk_label"], "mensenwerk")
    waarom(s)
    navigatie(
        bool(besluit) and bool(reden) and extra_ok and bool(mensenwerk),
        "Kies je besluit, schrijf op waarom en vul in wat mensenwerk blijft. Bij delen: de veiligheidscheck. Bij doorverwijzen: de koppeling.",
    )

elif ss.stap == 7:
    s = S["proefroute"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    st.subheader(s["deel1"])
    m1 = bewaar_tekst(s["moment1_label"], "moment1")
    bewaar_tekst(s["moment2_label"], "moment2")
    if "tester_idee" not in ss:
        ss["tester_idee"] = ss.get("leer", "")
    bewaar_tekst(s["tester_label"], "tester_idee")
    with st.expander(s["hulp_titel"]):
        prompt(vul_in(s["hulp_prompt"], taak=ss.get("taak", "")))
    st.subheader(s["deel2"])
    st.write(s["deel2_intro"])
    route = [bewaar_tekst(v, f"route{i}", area=True, height=70) for i, v in enumerate(s["vragen"])]
    keuze = bewaar_keuze(s["keuze_label"], ["Moment 1", "Moment 2"], "keuze7", horizontal=True)
    st.markdown("**Mijn als-dan-plan voor dit experiment**")
    als = bewaar_tekst(s["als_label"], "als7")
    st.caption(s["dan_tekst"])
    waarom(s)
    navigatie(
        bool(m1) and all(route) and bool(keuze) and bool(als),
        "Vul minimaal moment 1 in, beantwoord de 5 vragen, kies je eerste taak en vul je als-dan-plan in.",
    )

elif ss.stap == 8:
    s = S["showcase"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    werkwijze = bewaar_tekst(s["werkwijze_label"], "werkwijze")
    verandert = bewaar_tekst(s["verandert_label"], "verandert", area=True, height=80)
    if "besluit8" not in ss:
        ss["besluit8"] = kort(ss.get("besluit"))
    besluit8 = bewaar_tekst(s["besluit_label"], "besluit8")
    st.markdown("**Je als-dan-plan**")
    st.caption(s["plan_intro"])
    als = bewaar_tekst(s["als_label"], "als8")
    dan = bewaar_tekst(s["dan_label"], "dan8")
    waarom(s)
    if werkwijze and verandert and besluit8 and als and dan:
        st.markdown("**Deel in Teams**")
        st.caption("Plak deze zin in de draad in het Teams-kanaal. Geen klantgegevens.")
        st.code(vul_in(s["teams"], werkwijze=werkwijze, besluit=besluit8, mensenwerk=ss.get("mensenwerk", "")), language=None, wrap_lines=True)
        st.download_button(
            "⬇ Download alles als pdf",
            data=maak_pdf(),
            file_name=f"test-en-besluit-{date.today():%Y%m%d}.pdf",
            mime="application/pdf",
            type="primary",
        )
        st.success(s["afsluiting"])
    else:
        st.caption("Vul je 3 zinnen en je als-dan-plan in. Dan verschijnt de pdf.")
    navigatie()
