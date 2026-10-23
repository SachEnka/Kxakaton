from app.integrations.egrul_nalog import describe_inn, normalize_row
from app.integrations.pb_nalog import normalize_transparent


def test_normalize_public_egrul_row():
    record = normalize_row(
        {
            "c": 'АО "АЛЬФА-БАНК"',
            "g": "ПРЕДСЕДАТЕЛЬ ПРАВЛЕНИЯ: Соколов Андрей Борисович",
            "i": "7728168971",
            "k": "ul",
            "n": 'АКЦИОНЕРНОЕ ОБЩЕСТВО "АЛЬФА-БАНК"',
            "o": "1027700067328",
            "p": "770801001",
            "r": "26.07.2002",
            "rn": "Г.Москва",
        }
    )
    assert record["short_name"] == 'АО "АЛЬФА-БАНК"'
    assert record["director_name"] == "Соколов Андрей Борисович"
    assert record["registration_date"] == "2002-07-26"
    assert record["ogrn"] == "1027700067328"
    assert record["kpp"] == "770801001"
    assert record["legal_form"] == "OOO"
    assert record["region"] == "Г.Москва"
    assert record["status"] == "ACTIVE"


def test_transparent_business_card_uses_published_extract():
    record = normalize_transparent(
        {"namec": 'АО "АЛЬФА-БАНК"', "inn": "7728168971", "pr_liq": "0", "sulst_name_ex": "Действующая организация"},
        {
            "vyp": {
                "НаимЮЛСокр": 'АО "АЛЬФА-БАНК"',
                "АдресРФ": "107078, Г.МОСКВА, УЛ. КАЛАНЧЕВСКАЯ, Д.27",
                "КодОКВЭД": "64.19",
                "НаимОКВЭД": "Денежное посредничество прочее",
                "СумКап": "59587623000",
                "КПП": "770801001",
            },
            "is_p_sschr": False,
            "is_p_arrear": False,
            "is_p_form1": False,
            "masaddress": [],
            "liquidated": False,
        },
    )
    assert "КАЛАНЧЕВСКАЯ" in record["address"]
    assert record["okved"].startswith("64.19")
    assert record["charter_capital"] == 59587623000
    assert record["tax_debt"] is False
    assert record["data_source"] == "pb.nalog.ru"


def test_demo_inn_does_not_call_fns():
    card = describe_inn("7700000001")
    assert card["source"] == "demo"
    assert "Северная лавка" in card["short_name"]
    assert card["found"] is True
