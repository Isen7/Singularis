"""Browser checks for the static viewer with deterministic archive responses."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[2]
IMAGE = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
         "AAAAC0lEQVR42mP8/x8AAusB9XByuKIAAAAASUVORK5CYII=")


@pytest.fixture(scope="module")
def website():
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        yield page
        browser.close()


def mock_result(count):
    return {
        "detector": "D1", "native_pixels": [58, 59],
        "warning": "Preliminary visual comparison only.", "difference": IMAGE,
        "frames": [
            {"date": f"202{index + 1}-01-01T12:00:00", "image": IMAGE,
             "source": f"https://irsa.ipac.caltech.edu/ibe/cutout?frame={index}",
             "collection": "spherex_dr1", "detector": "D1",
             "observation_id": f"OBS-{index + 1}", "processing_version": "l2b-v1",
             "wavelength_um": 1.25, "masked_fraction": 0.03}
            for index in range(count)
        ],
    }


def search(page, website, count):
    page.route("**/api/search?**", lambda route: route.fulfill(json=mock_result(count)))
    page.goto(website)
    page.locator("#ra").fill("103.795129")
    page.locator("#dec").fill("-33.245147")
    page.locator("#coordinate-form button").click()
    page.wait_for_function("expected => document.querySelector('#frame-count').textContent === String(expected)", arg=count)
    assert page.locator("#frame-count").inner_text() == str(count)


def test_prepared_sample_and_compare(page, website):
    page.goto(website)
    assert "2 observations" in page.locator("#stage-title").inner_text()
    page.locator("#mode-compare").click()
    assert page.locator("#compare-stage").is_visible()
    page.locator("#compare-slider").fill("75")
    assert page.locator("#comparison-line").evaluate("element => element.style.left") == "75%"


def test_five_frame_playback_and_difference(page, website):
    search(page, website, 5)
    assert page.locator("#frame-slider").get_attribute("max") == "4"
    assert page.locator("#frame-index").inner_text() == "1 / 5"
    page.locator("#next").click()
    assert "OBS-2" in page.locator("#obs-id").inner_text()
    page.locator("#frame-slider").fill("4")
    assert "OBS-5" in page.locator("#obs-id").inner_text()
    page.locator("#prev").click()
    assert page.locator("#frame-index").inner_text() == "4 / 5"
    page.locator("#playback-speed").select_option("450")
    page.locator("#play").click()
    assert page.locator("#play").get_attribute("aria-label") == "Pause"
    page.locator("#play").click()
    page.locator("#mode-difference").click()
    assert page.locator("#frame-image").get_attribute("src") == IMAGE
    assert "not a confirmed detection" in page.locator("#interpretation-text").inner_text()


def test_two_frame_search_and_invalid_coordinates(page, website):
    search(page, website, 2)
    assert page.locator("#frame-slider").get_attribute("max") == "1"
    page.locator("#ra").fill("360")
    page.locator("#coordinate-form button").click()
    assert "Enter valid coordinates" in page.locator("#search-status").inner_text()


def test_archive_error_preserves_current_viewer(page, website):
    page.route("**/api/search?**", lambda route: route.fulfill(status=502, json={"error": "Archive temporarily unavailable."}))
    page.goto(website)
    page.locator("#ra").fill("103.795129")
    page.locator("#dec").fill("-33.245147")
    page.locator("#coordinate-form button").click()
    expect(page.locator("#search-status")).to_contain_text("Archive temporarily unavailable.")
    assert "WISE 0855" in page.locator("#stage-title").inner_text()


def test_mobile_viewport(page, website):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(website)
    box = page.locator("#viewer").bounding_box()
    assert box["x"] + box["width"] <= 390
    assert page.locator("#frame-image").is_visible()


def test_sky_map_failure_keeps_viewer_available(page, website):
    page.route("**/AladinLite/api/v3/latest/aladin.js", lambda route: route.abort())
    page.goto(website)
    page.locator("#sky-map-panel summary").click()
    page.wait_for_function("document.querySelector('#sky-map-status').textContent.includes('Sky Map is unavailable')")
    assert "Sky Map is unavailable" in page.locator("#sky-map-status").inner_text()
    assert page.locator("#frame-image").is_visible()


def test_sky_map_coordinates_can_drive_archive_search(page, website):
    mock_aladin = """
    window.A = {
      init: Promise.resolve(),
      aladin: () => ({
        gotoRaDec: (ra, dec) => { window.lastMapCenter = [ra, dec]; },
        addOverlay: () => {},
        on: (name, callback) => { window.mapPositionChanged = callback; }
      }),
      graphicOverlay: () => ({ add: () => {}, removeAll: () => {} }),
      circle: () => ({})
    };
    """
    page.route("**/AladinLite/api/v3/latest/aladin.js", lambda route: route.fulfill(body=mock_aladin, content_type="text/javascript"))
    page.route("**/api/search?**", lambda route: route.fulfill(json=mock_result(2)))
    page.goto(website)
    page.locator("#sky-map-panel summary").click()
    page.wait_for_function("Boolean(window.mapPositionChanged)")
    page.evaluate("window.mapPositionChanged({ra: 103.795129, dec: -33.245147})")
    assert page.locator("#ra").input_value() == "103.795129"
    page.locator("#map-search").click()
    page.wait_for_function("Array.isArray(window.lastMapCenter)")
    page.wait_for_function("document.querySelector('#stage-title').textContent.includes('103.79513')")
    assert page.locator("#frame-count").inner_text() == "2"
    assert page.evaluate("window.lastMapCenter") == [103.795129, -33.245147]
