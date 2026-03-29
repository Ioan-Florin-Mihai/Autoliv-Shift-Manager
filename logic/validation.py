def _parse_hours(label: str, value: str, allow_empty: bool = False):
    value = value.strip()

    if not value:
        if allow_empty:
            return None
        raise ValueError(f"{label} este obligatoriu.")

    try:
        hours = float(value)
    except ValueError as exc:
        raise ValueError(f"{label} trebuie sa fie un numar.") from exc

    if hours <= 0:
        raise ValueError(f"{label} trebuie sa fie mai mare decat 0.")

    if hours > 12:
        raise ValueError(f"{label} nu poate depasi 12.")

    return int(hours) if hours.is_integer() else hours


def validate_employee_data(
    nume: str,
    prenume: str,
    departament_1: str,
    ore_1_text: str,
    departament_2: str = "",
    ore_2_text: str = "",
):
    nume = nume.strip()
    prenume = prenume.strip()
    departament_1 = departament_1.strip()
    departament_2 = departament_2.strip()

    if not nume or not prenume or not departament_1:
        raise ValueError("Nume, prenume, departament 1 si ore 1 sunt obligatorii.")

    ore_1 = _parse_hours("Ore 1", ore_1_text)

    has_second_assignment = bool(departament_2 or ore_2_text.strip())
    ore_2 = None

    if has_second_assignment:
        if not departament_2:
            raise ValueError("Departament 2 este obligatoriu daca folosesti Ore 2.")
        ore_2 = _parse_hours("Ore 2", ore_2_text)

    total_ore = ore_1 + (ore_2 or 0)
    if total_ore > 12:
        raise ValueError("Totalul de ore nu poate depasi 12.")

    repartizari = [{"departament": departament_1, "ore": ore_1}]
    if has_second_assignment and ore_2 is not None:
        repartizari.append({"departament": departament_2, "ore": ore_2})

    return {
        "nume": nume,
        "prenume": prenume,
        "repartizari": repartizari,
        "ore_totale": total_ore,
        "split_activ": len(repartizari) > 1,
    }
