from btcopilot.familymatch import Status, match


def person(id, name, last=None, gender=None, parents=None, **extra):
    return dict(
        id=id, name=name, last_name=last, gender=gender, parents=parents, **extra
    )


def bond(id, a, b):
    return dict(id=id, person_a=a, person_b=b)


def birth(id, child, year=None, person=None, spouse=None):
    return dict(
        id=id,
        kind="birth",
        child=child,
        person=person,
        spouse=spouse,
        dateTime=year and f"{year}-03-01",
    )


def diagram(people, bonds=(), events=()):
    return dict(people=list(people), pair_bonds=list(bonds), events=list(events))


def harpers(mother="Doris", father="Glenn", sister="Nell", **sister_extra):
    return diagram(
        [
            person(1, "Ruth", "Harper", "female", 10),
            person(2, father, "Harper", "male"),
            person(3, mother, "Harper", "female"),
            person(4, sister, "Harper", "female", 10, **sister_extra),
            person(5, "Amos", "Harper", "male"),
            person(6, "Ida", "Harper", "female"),
        ],
        [bond(10, 2, 3), bond(11, 5, 6)],
    )


def kin(m, x):
    return m.people[x].status, m.people[x].other


def test_anchor_by_full_name_and_parents():
    # R-0853
    m = match(harpers(), harpers())
    assert m.ids == {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}


def test_anchor_on_primary_person():
    # R-0853
    a = diagram(
        [
            person(1, "Ruth", gender="female", parents=10, primary=True),
            person(2, "Glenn"),
            person(3, "Doris"),
        ],
        [bond(10, 2, 3)],
    )
    b = diagram(
        [
            person(7, "Ruthie", gender="female", parents=20, primary=True),
            person(8, "Glenn"),
            person(9, "Doris"),
        ],
        [bond(20, 8, 9)],
    )
    m = match(a, b)
    assert m.ids == {1: 7, 2: 8, 3: 9}


def test_nickname_and_spelling():
    # R-0853
    m = match(
        harpers(father="Wally", sister="Katy"), harpers(father="Walter", sister="Katie")
    )
    assert kin(m, 2) == (Status.Name, 2)
    assert kin(m, 4) == (Status.Name, 4)


def test_other_name_fields_of_an_fd_file():
    # R-0853
    b = harpers(sister="Eleanor")
    b["people"][3] |= dict(nickName="Nell", lastName="Harper", last_name=None)
    b["people"][2] |= dict(birthName="Moss", last_name="Kane")
    a = harpers()
    a["people"][2]["last_name"] = "Moss"
    m = match(a, b)
    assert kin(m, 4) == (Status.Name, 4)
    assert kin(m, 3) == (Status.Name, 3)


def test_alias_is_not_a_name():
    # R-0853
    m = match(harpers(sister="Nell", alias="Joy"), harpers(sister="Joy"))
    assert kin(m, 4) == (Status.Unmatched, None)
    assert m.people[4].candidates == [4]


def test_placeholder_matches_by_position_on_either_side():
    # R-0853
    m = match(harpers(mother="Ruth's mother"), harpers())
    assert kin(m, 3) == (Status.Position, 3)
    m = match(harpers(), harpers(mother=""))
    assert kin(m, 3) == (Status.Position, 3)


def test_parents_found_through_birth_event():
    # R-0853
    a = harpers()
    for p in a["people"]:
        p["parents"] = None
    a["events"] = [
        birth(30, 1, 1950, person=2, spouse=3),
        birth(31, 4, 1953, person=2, spouse=3),
    ]
    a["pair_bonds"] = []
    m = match(a, harpers())
    assert m.ids == {1: 1, 2: 2, 3: 3, 4: 4}


def test_half_sibling_through_another_bond_of_a_parent():
    # R-0853
    def family():
        d = harpers(father="Pop")
        d["people"] += [
            person(7, "Vera", "Lind", "female"),
            person(8, "Hal", "Harper", "male", 12),
        ]
        d["pair_bonds"].append(bond(12, 2, 7))
        return d

    b = family()
    b["people"][1]["name"] = "Glenn"
    m = match(family(), b)
    assert kin(m, 2) == (Status.Unmatched, None)
    assert kin(m, 8) == (Status.Name, 8)


def same_named_brothers(years=(None, None), kids=()):
    d = harpers()
    d["people"] += [
        person(20, "John", "Harper", "male", 10),
        person(21, "John", "Harper", "male", 10),
    ]
    d["events"] = [birth(40 + i, 20 + i, y) for i, y in enumerate(years) if y]
    for i, (pid, name) in enumerate(kids):
        d["people"] += [
            person(30 + i, name, None, None, 50 + i),
            person(35 + i, "", None, "female"),
        ]
        d["pair_bonds"].append(bond(50 + i, pid, 35 + i))
    return d


def test_same_named_siblings_broken_by_birth_year():
    # R-0853
    m = match(same_named_brothers((1950, 1960)), same_named_brothers((1960, 1950)))
    assert kin(m, 20) == (Status.Name, 21)
    assert kin(m, 21) == (Status.Name, 20)


def test_same_named_siblings_broken_by_their_children():
    # R-0853
    m = match(
        same_named_brothers(kids=[(20, "Amy"), (21, "Ben")]),
        same_named_brothers(kids=[(21, "Amy"), (20, "Ben")]),
    )
    assert kin(m, 20) == (Status.Name, 21)
    assert m.ids[30] == 30


def test_same_named_siblings_left_ambiguous():
    # R-0853, R-0851
    m = match(same_named_brothers(), same_named_brothers())
    assert m.people[20].status is Status.Ambiguous
    assert m.people[20].candidates == [20, 21]


def two_wives(second, kids=True):
    d = harpers()
    d["people"] += [
        person(7, second, None, "female"),
        person(8, "Hal", "Harper", "male", 12 if kids else None),
    ]
    d["pair_bonds"].append(bond(12, 2, 7))
    d["events"] = [
        dict(id=60, kind="married", person=2, spouse=3, dateTime="1948-06-01")
    ]
    return d


def test_first_and_second_wife():
    # R-0853
    m = match(two_wives("Glenn's second wife"), two_wives("Vera"))
    assert kin(m, 3) == (Status.Name, 3)
    assert kin(m, 7) == (Status.Position, 7)
    assert m.pair_bonds == {10: 10, 11: 11, 12: 12}
    assert m.events == {60: 60}


def test_partner_by_position_needs_a_shared_child():
    # R-0853
    m = match(
        two_wives("Glenn's second wife", kids=False), two_wives("Vera", kids=False)
    )
    assert kin(m, 7) == (Status.Unmatched, None)


def test_same_name_in_two_branches():
    # R-0853
    def family():
        d = harpers()
        d["people"][1]["parents"] = 11
        d["people"] += [
            person(20, "John", "Harper", "male", 11),
            person(21, "Ray", "Cole", "male"),
            person(22, "John", "Harper", "male", 13),
        ]
        d["pair_bonds"].append(bond(13, 4, 21))
        return d

    b = family()
    b["people"] = b["people"][:6] + [
        dict(p, id=p["id"] + 100, parents=p["parents"]) for p in b["people"][6:]
    ]
    b["pair_bonds"][2] = bond(13, 4, 121)
    m = match(family(), b)
    assert m.ids[20] == 120
    assert m.ids[22] == 122


def test_full_name_outside_the_walk_needs_evidence():
    # R-0853
    def family(partner):
        d = harpers()
        d["people"] += [
            person(40, "Edna", "Moss", "female"),
            person(41, partner, "Moss", "male"),
        ]
        d["pair_bonds"].append(bond(42, 40, 41))
        return d

    assert match(family("Carl"), family("Carl")).ids[40] == 40
    assert kin(match(family("Carl"), family("Otto")), 40) == (Status.Unmatched, None)


def test_result_is_symmetric():
    # R-0853, R-0851
    a = two_wives("Glenn's second wife")
    a["people"] += [
        person(20, "John", "Harper", "male", 10),
        person(21, "John", "Harper", "male", 10),
    ]
    b = two_wives("Vera")
    b["people"] += [
        person(20, "Jon", "Harper", "male", 10),
        person(21, "John", "Harper", "male", 10),
    ]
    ab, ba = match(a, b), match(b, a)
    assert {v: k for k, v in ab.ids.items()} == ba.ids
    assert {x: pm.status for x, pm in ab.people.items() if pm.other} == {
        pm.other: pm.status for pm in ba.people.values() if pm.other
    }
    assert ba.people[20].candidates == ab.people[20].candidates == [20, 21]
    assert {v: k for k, v in ab.pair_bonds.items()} == ba.pair_bonds
