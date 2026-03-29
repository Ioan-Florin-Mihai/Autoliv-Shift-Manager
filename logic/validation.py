# ============================================================
# MODUL: validation.py
# Contine logica de validare a datelor introduse pentru angajati.
# Separat de UI ca sa poata fi testat independent.
# ============================================================


def _parse_hours(label: str, value: str, allow_empty: bool = False):
    """
    Parseaza si valideaza un camp de ore.
    - label: numele campului (pentru mesaje de eroare)
    - value: textul introdus de utilizator
    - allow_empty: daca True, campul gol returneaza None (optional)
    Returneaza valoarea numerica (int sau float) daca e valida.
    """
    value = value.strip()

    # Camp gol — permis sau obligatoriu
    if not value:
        if allow_empty:
            return None
        raise ValueError(f"{label} este obligatoriu.")

    # Trebuie sa fie numar
    try:
        hours = float(value)
    except ValueError as exc:
        raise ValueError(f"{label} trebuie sa fie un numar.") from exc

    # Validare interval: 0 < ore <= 12
    if hours <= 0:
        raise ValueError(f"{label} trebuie sa fie mai mare decat 0.")
    if hours > 12:
        raise ValueError(f"{label} nu poate depasi 12.")

    # Returnam int daca e un numar intreg (ex: 8.0 → 8), altfel float
    return int(hours) if hours.is_integer() else hours


def validate_employee_data(
    nume: str,
    prenume: str,
    departament_1: str,
    ore_1_text: str,
    departament_2: str = "",
    ore_2_text: str = "",
):
    """
    Valideaza datele complete ale unui angajat inainte de salvare.
    Suporta si angajati cu doua repartizari (split shift).
    Returneaza un dict structurat gata de salvat in JSON.
    Arunca ValueError cu mesaj clar daca ceva e invalid.
    """
    # Curatam spatiile din campurile text
    nume          = nume.strip()
    prenume       = prenume.strip()
    departament_1 = departament_1.strip()
    departament_2 = departament_2.strip()

    # Campurile principale sunt obligatorii
    if not nume or not prenume or not departament_1:
        raise ValueError("Nume, prenume, departament 1 si ore 1 sunt obligatorii.")

    # Validam orele pentru prima repartizare
    ore_1 = _parse_hours("Ore 1", ore_1_text)

    # Detectam daca s-a completat a doua repartizare
    has_second_assignment = bool(departament_2 or ore_2_text.strip())
    ore_2 = None

    if has_second_assignment:
        # Daca s-au introdus ore2 dar nu si departament2, e o eroare
        if not departament_2:
            raise ValueError("Departament 2 este obligatoriu daca folosesti Ore 2.")
        ore_2 = _parse_hours("Ore 2", ore_2_text)

    # Totalul orelor nu poate depasi 12 pe zi
    total_ore = ore_1 + (ore_2 or 0)
    if total_ore > 12:
        raise ValueError("Totalul de ore nu poate depasi 12.")

    # Construim lista de repartizari
    repartizari = [{"departament": departament_1, "ore": ore_1}]
    if has_second_assignment and ore_2 is not None:
        repartizari.append({"departament": departament_2, "ore": ore_2})

    return {
        "nume":        nume,
        "prenume":     prenume,
        "repartizari": repartizari,
        "ore_totale":  total_ore,
        "split_activ": len(repartizari) > 1,  # True daca angajatul lucreaza in 2 departamente
    }
