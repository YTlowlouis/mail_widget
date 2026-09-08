from mail_daemon.otp import extract_otp_code


def test_extracts_six_digit_code_near_keyword():
    body = "Bonjour,\n\nVotre code de vérification est : 482913\n\nIl expire dans 10 minutes."
    assert extract_otp_code(body) == "482913"


def test_extracts_code_with_spaces():
    body = "Your one-time code: 482 913. Do not share it."
    assert extract_otp_code(body) == "482913"


def test_extracts_four_digit_code():
    body = "Code OTP: 4829 - ne le partagez avec personne."
    assert extract_otp_code(body) == "4829"


def test_ignores_number_without_nearby_keyword():
    body = "Votre commande n°482913 a été expédiée le 08/09/2026."
    assert extract_otp_code(body) is None


def test_ignores_year_like_number_without_keyword():
    body = "Copyright 2026, tous droits réservés."
    assert extract_otp_code(body) is None


def test_ignores_number_too_long_to_be_a_code():
    body = "Votre code de vérification est 123456789012 pour votre sécurité."
    assert extract_otp_code(body) is None


def test_returns_none_on_empty_body():
    assert extract_otp_code("") is None


def test_picks_first_keyworded_candidate_when_several_numbers_present():
    body = "Référence commande 998877. Votre code de sécurité: 111222. Merci."
    assert extract_otp_code(body) == "111222"
