"""Sessie 2 AI-pilot: bouw je werkwijze.

Alle teksten, prompts en codewoorden staan in inhoud_sessie2.yaml.
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
C = yaml.safe_load((MAP / "inhoud_sessie2.yaml").read_text(encoding="utf-8"))
S = C["stappen"]

STAPPEN = [
    "Start",
    "1. Terug naar je tests",
    "2. Ontwerp met Copilot",
    "3. Schrijf je instructie",
    "4. Test",
    "5. Breek je werkwijze",
    "6. Verander 1 ding",
    "7. Bewaar en plan",
]
LAATSTE = len(STAPPEN) - 1
SLOT_VANAF = 4  # vanaf deze stap is codewoord 2 nodig
VELDEN = ["doel", "input", "aanpak", "output"]

st.set_page_config(page_title=C["titel"], page_icon="🛠", layout="centered")
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


def basis():
    return dict(
        functie=ss.get("functie", ""),
        stap=ss.get("stap_keuze", ""),
        oplevert=ss.get("oplevert", ""),
        tests=tests_tekst(),
        herstel=herstel_tekst(),
    )


def niet_getest():
    return all(ss.get(f"t{i}_score") == "Niet gedaan" for i in (1, 2, 3))


def tests_tekst():
    if niet_getest():
        return "Ik heb nog niet getest. Mijn eerste resultaat in de kickoff: " + (ss.get("kickoff_res", "").strip() or "onbekend")
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
    return "; ".join(delen) or "nog niet ingevuld"


def herstel_tekst():
    regels = [ss.get(f"t{i}_herstel", "").strip() for i in (1, 2, 3)]
    regels = [r for r in regels if r]
    return "; ".join(regels) or ss.get("kickoff_res", "").strip()


def instructie(versie=1):
    achter = "" if versie == 1 else "2"
    w = {v: ss.get(v + achter, "").strip() for v in VELDEN}
    return vul_in(S["instructie"]["sjabloon"], functie=ss.get("functie", ""), **w)


def tijd(minuten):
    st.caption(f"⏱ {minuten} minuten")


def waarom(s):
    if s.get("waarom"):
        st.caption(f"💡 **Waarom zo?** {s['waarom']}")


def prompt(tekst, label="Prompt voor Copilot"):
    with st.container(border=True):
        st.markdown(f"📋 **{label}**  \n:gray[Kopieer met het icoon rechtsboven in het grijze vak. Plak in Copilot Chat.]")
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

    kop("1. Mijn stap en mijn tests")
    tekst("Functie: " + ss.get("functie", "") + ", afdeling: " + ss.get("afdeling", ""))
    tekst("Stap: " + ss.get("stap_keuze", ""))
    tekst("Dit moet het opleveren: " + ss.get("oplevert", ""))
    tekst("Tests: " + tests_tekst())
    if niet_getest():
        tekst("Waarom niet getest: " + (ss.get("waarom_niet") or "-"))
    tekst("Hoe verder: " + (ss.get("verder") or "-"))
    kop("2 en 3. Mijn werkwijze")
    tekst("Hulp bij het ontwerp: " + (ss.get("hulp2") or "-"))
    kop("Instructie versie 0.1", 11)
    tekst(instructie(1), mono=True)
    tekst("Mijn controle: " + ss.get("controle", ""))
    tekst("Wanneer ik de uitkomst niet gebruik: " + ss.get("wanneer_niet", ""))
    tekst("Dit blijft mensenwerk: " + ss.get("mensenwerk", ""))
    tekst("Mag het: " + (ss.get("kleur") or "-"))
    kop("4. Test met normale input")
    tekst("Dit moest er zeker in staan: " + ss.get("punten", ""))
    tekst("Score: " + (ss.get("score4") or "-"))
    tekst("Wat ik zelf nog moest doen: " + ss.get("herstel4", ""))
    if ss.get("bijsturing", "").strip():
        tekst("Deze bijsturing maakte het verschil: " + ss.get("bijsturing", ""))
    tekst("Hulp: " + (ss.get("hulp4") or "-"))
    kop("5. Lastige input")
    tekst("Lastig geval: " + ss.get("geval", ""))
    tekst("Wat ging er mis: " + ss.get("mis", ""))
    tekst("Score: " + (ss.get("score5") or "-") + ". Hulp: " + (ss.get("hulp5") or "-"))
    kop("6. Versie 0.2")
    tekst("Wat ik aanpaste en waarom: " + ss.get("aanpas", ""))
    tekst("Versie 0.2 was: " + (ss.get("beter") or "-"))
    tekst(instructie(2), mono=True)
    kop("7. Mijn plan")
    tekst(f"Als {ss.get('als', '')}, dan {ss.get('dan', '')}.")
    tekst("Hier bewaar ik mijn instructie: " + ss.get("bewaarplek", ""))
    for i in (1, 2, 3):
        tekst(f"Test {i}: " + ss.get(f"plan{i}", ""))
    return bytes(pdf.output())


def samenvatting():
    return "\n".join(
        [
            f"Functie: {ss.get('functie', '')}",
            f"Stap: {ss.get('stap_keuze', '')}",
            f"Tests: {tests_tekst()}",
            f"Versie 0.2 was: {ss.get('beter') or '-'}",
            f"Dit blijft mensenwerk: {ss.get('mensenwerk', '')}",
            f"Als {ss.get('als', '')}, dan {ss.get('dan', '')}.",
            f"Instructie versie 0.2: {instructie(2)}",
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
    s = S["tests"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    waarom(s)
    stap = bewaar_tekst(s["stap_label"], "stap_keuze")
    oplevert = bewaar_tekst(s["oplevert_label"], "oplevert")
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
        bewaar_tekst(s["kickoff_label"], "kickoff_res")
    verder = bewaar_keuze("Hoe ga je verder?", s["verder_opties"], "verder")
    if verder == s["verder_opties"][1]:
        st.write(s["aanpassen_tekst"])
        prompt(vul_in(s["aanpassen_prompt"], **basis()))
    elif verder == s["verder_opties"][2]:
        st.write(s["andere_tekst"])
        prompt(vul_in(s["andere_prompt"], **basis()))
    vet(s["vinkjes_intro"])
    klaar = bewaar_vinkje(s["vinkje"], "v1")
    navigatie(bool(stap) and bool(oplevert) and bool(verder) and klaar, "Vul je stap in, kies hoe je verdergaat en zet het vinkje.")

elif ss.stap == 2:
    s = S["ontwerp"]
    st.title(s["titel"])
    tijd(s["tijd"])
    with st.container(border=True):
        st.markdown(f"🎯 **Opdracht:** {s['opdracht']}")
    st.caption(s["tip"])
    b = basis()
    with st.expander("Hulp 1: een paar vragen om op weg te komen"):
        for v in s["hulp1"]:
            st.markdown(f"- {v}")
    with st.expander("Hulp 2: de bouwstenen"):
        for naam, zin in s["hulp2"]:
            st.markdown(f"**{naam}:** {vul_in(zin, **b)}")
    with st.expander("Hulp 3: de hele prompt"):
        prompt(vul_in(s["prompt"], **b))
    waarom(s)
    st.warning(s["waarschuwing"])
    with st.expander("Loop je vast?"):
        for h in s["vastlopen"]:
            prompt(h["prompt"], h["label"])
    hulp = bewaar_keuze("Welke hulp heb je gebruikt?", s["hulp_opties"], "hulp2", horizontal=True)
    vet(s["vinkje_intro"])
    klaar = bewaar_vinkje(s["vinkje"], "v2")
    navigatie(bool(hulp) and klaar, "Kies welke hulp je gebruikte en zet het vinkje.")

elif ss.stap == 3:
    s = S["instructie"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    waarom(s)
    st.caption(s["tip"])
    ingevuld = [bewaar_tekst(label, k, area=True, height=70) for k, label in s["velden"].items()]
    bewaar_tekst(s["controle_label"], "controle")
    bewaar_tekst(s["niet_label"], "wanneer_niet")
    mensenwerk = bewaar_tekst(s["mensenwerk_label"], "mensenwerk")
    prompt(instructie(1), "Jouw instructie, versie 0.1")
    kleur = bewaar_keuze(s["kleur_vraag"], s["kleuren"], "kleur")
    rood_ok = True
    if kleur == s["kleuren"][0]:
        st.success(s["groen"])
    elif kleur == s["kleuren"][1]:
        st.warning(s["oranje"])
        prompt(s["uitzoeken_prompt"], "Zoek het uit met Copilot")
        st.caption(s["uitzoeken_noot"])
        prompt(vul_in(s["verzonnen_prompt"], functie=ss.get("functie", "")), "Maak een verzonnen voorbeeld")
    elif kleur == s["kleuren"][2]:
        st.error(s["rood"])
        prompt(vul_in(s["verzonnen_prompt"], functie=ss.get("functie", "")), "Maak een verzonnen voorbeeld")
        rood_ok = bewaar_vinkje(s["rood_vinkje"], "rood_ok")
    vet(s["vinkje_intro"])
    klaar = bewaar_vinkje(s["vinkje"], "v3")
    navigatie(
        all(ingevuld) and bool(mensenwerk) and bool(kleur) and rood_ok and klaar,
        "Vul doel, input, aanpak, output en mensenwerk in, kies een kleur en zet het vinkje. Bij rood: kies een verzonnen voorbeeld.",
    )

elif ss.stap == 4 and not ss.code2:
    s = S["wacht"]
    st.markdown("# ⏸")
    st.title(s["titel"])
    st.write(s["tekst"])
    st.info(s["tip"])
    prompt(instructie(1), "Jouw instructie, versie 0.1")
    code = st.text_input("Codewoord", key="w_code2")
    links, rechts, _ = st.columns([1, 1, 3])
    links.button("Terug", on_click=lambda: ss.update(stap=3), use_container_width=True)
    if rechts.button("Verder", type="primary", use_container_width=True):
        if codewoord_ok(code, C["codewoorden"]["verder"]):
            ss.code2 = True
            st.rerun()
        else:
            st.error("Dit codewoord klopt niet. Wacht op Gijs.")

elif ss.stap == 4:
    s = S["test"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    punten = bewaar_tekst(s["punten_label"], "punten", area=True, height=90)
    prompt(instructie(1), "Jouw instructie, versie 0.1")
    waarom(s)
    st.warning(s["waarschuwing"])
    st.write(s["bijsturen_tekst"])
    with st.expander(s["bijsturen_titel"]):
        for h in s["bijsturen"]:
            prompt(h["prompt"], h["label"])
    bewaar_tekst(s["bijsturing_label"], "bijsturing")
    hulp = bewaar_keuze("Welke hulp heb je gebruikt?", s["hulp_opties"], "hulp4", horizontal=True)
    st.subheader("Controleer de uitkomst")
    vet(s["vinkjes_intro"])
    for i, t in enumerate(s["controle"]):
        bewaar_vinkje(t, f"c4_{i}")
    score = bewaar_keuze("Mijn score", s["scores"], "score4", horizontal=True)
    herstel = bewaar_tekst(s["herstel_label"], "herstel4", area=True, height=80)
    navigatie(bool(punten) and bool(hulp) and bool(score) and bool(herstel), "Vul je 3 punten in, kies welke hulp je gebruikte, kies een score en vul in wat je zelf nog moest doen.")

elif ss.stap == 5:
    s = S["breek"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    bewaar_tekst(s["geval_label"], "geval", area=True, height=80)
    with st.expander(s["hulp_titel"]):
        prompt(vul_in(s["prompt"], instructie=instructie(1), functie=ss.get("functie", "")))
    st.write(s["daarna"])
    waarom(s)
    mis = bewaar_tekst(s["mis_label"], "mis", area=True, height=80)
    hulp = bewaar_keuze("Welke hulp heb je gebruikt?", s["hulp_opties"], "hulp5", horizontal=True)
    score = bewaar_keuze("Mijn score", s["scores"], "score5", horizontal=True)
    navigatie(bool(mis) and bool(hulp) and bool(score), "Vul in wat er misging, kies welke hulp je gebruikte en kies een score.")

elif ss.stap == 6:
    s = S["verander"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    st.caption(s["velden_noot"])
    for k, label in S["instructie"]["velden"].items():
        if k + "2" not in ss:
            ss[k + "2"] = ss.get(k, "")
        bewaar_tekst(label, k + "2", area=True, height=70)
    aanpas = bewaar_tekst(s["aanpas_label"], "aanpas")
    with st.expander(s["hulp_titel"]):
        prompt(s["hulp_prompt"])
    prompt(instructie(2), "Jouw instructie, versie 0.2")
    vet(s["vinkje_intro"])
    klaar = bewaar_vinkje(s["vinkje"], "v6")
    beter = bewaar_keuze("Was versie 0.2 beter?", s["beter_opties"], "beter", horizontal=True)
    waarom(s)
    navigatie(bool(aanpas) and klaar and bool(beter), "Schrijf op wat je aanpast, test versie 0.2 en kies of hij beter was.")

elif ss.stap == 7:
    s = S["bewaar"]
    st.title(s["titel"])
    tijd(s["tijd"])
    st.write(s["intro"])
    waarom(s)
    st.subheader("Veiligheidscheck")
    vet(s["veilig_intro"])
    veilig = [bewaar_vinkje(t, f"veilig{i}") for i, t in enumerate(s["veilig"])]
    st.caption(s["twijfel"])
    st.subheader("Jouw als-dan-plan")
    st.write(s["plan_intro"])
    als = bewaar_tekst(s["als_label"], "als")
    dan = bewaar_tekst(s["dan_label"], "dan")
    for i, t in enumerate(s["tests"], 1):
        bewaar_tekst(t, f"plan{i}")
    st.subheader("Bewaar je instructie")
    st.write(s["bewaar_tekst"])
    prompt(instructie(2), "Jouw instructie, versie 0.2")
    plek = bewaar_tekst(s["bewaar_label"], "bewaarplek")
    with st.expander(s["agent_titel"]):
        st.write(s["agent_intro"])
        for i, t in enumerate(s["agent_stappen"], 1):
            st.markdown(f"{i}. {t}")
        st.caption(s["agent_noot"])
    st.info(s["na_tests"])
    if all(veilig) and als and dan and plek:
        st.markdown("**Deel in Teams**")
        st.caption("Plak deze zin in de draad in het Teams-kanaal. Geen klantgegevens.")
        st.code(vul_in(s["teams"], doel=ss.get("doel2", ""), beter=(ss.get("beter") or "").lower(), mensenwerk=ss.get("mensenwerk", "")), language=None, wrap_lines=True)
        st.download_button(
            "⬇ Download alles als pdf",
            data=maak_pdf(),
            file_name=f"werkwijze-{date.today():%Y%m%d}.pdf",
            mime="application/pdf",
            type="primary",
        )
        with st.expander("Of kopieer een korte samenvatting"):
            st.code(samenvatting(), language=None, wrap_lines=True)
        st.success(s["afsluiting"])
    else:
        st.caption("Zet de 3 vinkjes van de veiligheidscheck en vul je als-dan-plan en je bewaarplek in. Dan verschijnt de pdf.")
    navigatie()
