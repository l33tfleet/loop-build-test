def test_sample_planet_appears_on_home(client, sample_planet_slug):
    assert sample_planet_slug == "earth"
    response = client.get("/")
    assert response.status_code == 200
    assert f"<h2>{sample_planet_slug.capitalize()}</h2>" in response.text
